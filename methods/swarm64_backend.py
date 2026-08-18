#!/usr/bin/env python3
"""
Swarm64 Accelerated PostgreSQL Backend
Replaces standard vector/SQL backends in OpenDataBox/MemoryData
Compatible with Swarm64 DA 4.0+ (FPGA optional, columnar acceleration mandatory)
ItalyWorld R&D / Cesare Semovigo - Gotham v3 Bridge
"""

import psycopg2
import psycopg2.extras
import numpy as np
import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Swarm64Config:
    host: str = "localhost"
    port: int = 5432
    database: str = "memorydata_swarm64"
    user: str = "adam_agent"
    password: str = ""
    # Swarm64 DA specific
    s64da_enable_columnar: bool = True
    s64da_parallel_workers: int = 64   # up to 64 parallel threads per Swarm64 DA
    s64da_compression_level: int = 5   # 5x-25x compression
    s64da_fpga_enabled: bool = False   # set True if Xilinx Alveo U250 present
    # Vector index config
    vector_dim: int = 1536
    vector_index_type: str = "ivfflat"  # or hnsw via pgvector
    ivfflat_lists: int = 100


class Swarm64MemoryBackend:
    """
    FPGA-accelerated PostgreSQL backend for agent memory.
    Replaces FAISS/ChromaDB/SQLite standard backends with
    a single unified Swarm64-accelerated PostgreSQL cluster.
    """

    DDL_MEMORY_TABLE = """
    CREATE TABLE IF NOT EXISTS agent_memory (
        memory_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id        TEXT NOT NULL,
        module          TEXT NOT NULL CHECK (module IN ('extraction','maintenance','retrieval','storage')),
        content         TEXT NOT NULL,
        embedding       vector({dim}),
        metadata        JSONB,
        entropy_score   FLOAT8 CHECK (entropy_score >= 0 AND entropy_score < 1),
        merkle_hash     TEXT NOT NULL,
        created_at      TIMESTAMPTZ DEFAULT now(),
        updated_at      TIMESTAMPTZ DEFAULT now(),
        worm_sealed     BOOLEAN DEFAULT FALSE
    );
    """

    DDL_COLUMNAR_INDEX = """
    CREATE FOREIGN TABLE IF NOT EXISTS agent_memory_columnar (
        memory_id       UUID,
        agent_id        TEXT,
        module          TEXT,
        entropy_score   FLOAT8,
        created_at      TIMESTAMPTZ
    ) SERVER s64da_server
    OPTIONS (table 'agent_memory', columns 'memory_id,agent_id,module,entropy_score,created_at');
    """

    DDL_WORM_LOG = """
    CREATE TABLE IF NOT EXISTS worm_audit_log (
        log_id          BIGSERIAL PRIMARY KEY,
        memory_id       UUID NOT NULL,
        operation       TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE','SEAL')),
        actor           TEXT NOT NULL,
        payload_hash    TEXT NOT NULL,
        chain_hash      TEXT NOT NULL,
        timestamp_utc   TIMESTAMPTZ DEFAULT now()
    );
    CREATE OR REPLACE FUNCTION enforce_worm()
    RETURNS TRIGGER AS $$
    BEGIN
        IF OLD.worm_sealed THEN
            RAISE EXCEPTION 'WORM violation: memory_id % is sealed and immutable', OLD.memory_id;
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS worm_guard ON agent_memory;
    CREATE TRIGGER worm_guard
        BEFORE UPDATE OR DELETE ON agent_memory
        FOR EACH ROW EXECUTE FUNCTION enforce_worm();
    """

    def __init__(self, config: Optional[Swarm64Config] = None):
        self.cfg = config or Swarm64Config()
        self.conn = None
        self._chain_head_hash = "0" * 64   # genesis hash

    # -------------------------------------------------------------------------
    # Connection & Schema
    # -------------------------------------------------------------------------

    def connect(self) -> None:
        self.conn = psycopg2.connect(
            host=self.cfg.host,
            port=self.cfg.port,
            database=self.cfg.database,
            user=self.cfg.user,
              password=self.cfg.password,
        )
        self.conn.autocommit = False
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            if self.cfg.s64da_enable_columnar:
                cur.execute("CREATE EXTENSION IF NOT EXISTS swarm64da;")
            cur.execute(self.DDL_MEMORY_TABLE.format(dim=self.cfg.vector_dim))
            cur.execute(self.DDL_WORM_LOG)
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS idx_embedding ON agent_memory "
                f"USING ivfflat (embedding vector_cosine_ops) WITH (lists = {self.cfg.ivfflat_lists});"
            )
            if self.cfg.s64da_enable_columnar:
                try:
                    cur.execute(self.DDL_COLUMNAR_INDEX)
                except Exception:
                    pass   # graceful fallback if Swarm64 DA not installed
            self.conn.commit()

    # -------------------------------------------------------------------------
    # Merkle / chain helpers
    # -------------------------------------------------------------------------

    def _compute_merkle_hash(self, content: str, metadata: dict) -> str:
        payload = json.dumps({"content": content, "metadata": metadata}, sort_keys=True)
        leaf = hashlib.sha256(payload.encode()).hexdigest()
        chain = hashlib.sha256((self._chain_head_hash + leaf).encode()).hexdigest()
        self._chain_head_hash = chain
        return chain

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    def insert_memory(
        self,
        agent_id: str,
        module: str,
        content: str,
        embedding: np.ndarray,
        metadata: dict,
        entropy_score: float,
        actor: str = "adam_orchestrator",
    ) -> str:
        merkle_hash = self._compute_merkle_hash(content, metadata)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_memory
                    (agent_id, module, content, embedding, metadata, entropy_score, merkle_hash)
                VALUES (%s, %s, %s, %s::vector, %s, %s, %s)
                RETURNING memory_id;
                """,
                (
                    agent_id, module, content,
                    embedding.tolist(), json.dumps(metadata),
                    entropy_score, merkle_hash,
                ),
            )
            memory_id = str(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO worm_audit_log
                    (memory_id, operation, actor, payload_hash, chain_hash)
                VALUES (%s, 'INSERT', %s, %s, %s);
                """,
                (memory_id, actor, hashlib.sha256(content.encode()).hexdigest(), merkle_hash),
            )
            self.conn.commit()
        return memory_id

    def seal_memory(self, memory_id: str, actor: str = "gotham_v3_supervisor") -> None:
        """WORM-seal a memory entry: makes it permanently immutable."""
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE agent_memory SET worm_sealed = TRUE, updated_at = now() "
                "WHERE memory_id = %s;",
                (memory_id,),
            )
            merkle_hash = self._compute_merkle_hash(f"SEAL:{memory_id}", {"actor": actor})
            cur.execute(
                "INSERT INTO worm_audit_log "
                "    (memory_id, operation, actor, payload_hash, chain_hash) "
                "VALUES (%s, 'SEAL', %s, %s, %s);",
                (memory_id, actor, hashlib.sha256(memory_id.encode()).hexdigest(), merkle_hash),
            )
            self.conn.commit()

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single memory entry by primary key."""
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT memory_id, agent_id, module, content, metadata, "
                "       entropy_score, merkle_hash, created_at, worm_sealed "
                "FROM agent_memory WHERE memory_id = %s;",
                (memory_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def vector_search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        module_filter: Optional[str] = None,
        entropy_max: float = 0.059,
    ) -> List[Dict[str, Any]]:
        """
        Cosine similarity vector search, Swarm64-accelerated via columnar
        pre-filtering on entropy_score and module before embedding scan.
        """
        filters: List[str] = ["entropy_score < %s"]
        params: List[Any] = [entropy_max]

        if module_filter:
            filters.append("module = %s")
            params.append(module_filter)

        where_clause = " AND ".join(filters)
        emb_list = query_embedding.tolist()

        # Parameters order:
        #   1..N  WHERE clause params
        #   N+1   embedding for cosine_similarity column expression
        #   N+2   embedding for ORDER BY clause
        #   N+3   LIMIT
        sql = f"""
            SELECT memory_id, agent_id, module, content, metadata,
                   entropy_score, merkle_hash, created_at,
                   1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM agent_memory
            WHERE {where_clause}
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        query_params = params + [emb_list, emb_list, top_k]

        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, query_params)
            return [dict(r) for r in cur.fetchall()]

    def list_memories(
        self,
        agent_id: str,
        module: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List memories for an agent, newest first."""
        params: List[Any] = [agent_id]
        extra = ""
        if module:
            extra = " AND module = %s"
            params.append(module)
        params += [limit, offset]

        sql = (
            "SELECT memory_id, agent_id, module, content, metadata, "
            "       entropy_score, merkle_hash, created_at, worm_sealed "
            "FROM agent_memory "
            f"WHERE agent_id = %s{extra} "
            "ORDER BY created_at DESC "
            "LIMIT %s OFFSET %s;"
        )
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
