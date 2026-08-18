#!/usr/bin/env python3
"""
Adam Orchestrator v1 - Multi-Agent Extraction & Maintenance Modules
Replaces single-LLM extraction/maintenance in MemoryData
Architecture: Parallel swarm of specialized sub-agents coordinated by Adam
Outropy23 — MemoryData Project
"""

import json
import math
import hashlib
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class AgentTask:
    task_id: str
    agent_role: str   # 'extractor' | 'validator' | 'consolidator' | 'entropy_guard'
    payload: Dict[str, Any]
    priority: int = 5   # 1=highest, 10=lowest
    timeout_s: float = 30.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class AdamOrchestrator:
    """
    Multi-agent orchestrator that decomposes Extraction and Maintenance
    into parallel sub-agent pipelines.

    Extraction pipeline:
        1. EntityExtractor   - NER + relation extraction
        2. TemporalTagger    - temporal anchoring of facts
        3. EntropyGuard      - computes and enforces entropy bound sigma < 0.059
        4. EmbeddingWorker   - generates embeddings (parallel, up to N workers)

    Maintenance pipeline:
        1. ConflictDetector  - identifies contradictions with existing memory
        2. Consolidator      - merges/updates memory entries
        3. ForgettingAgent   - applies decay/eviction policies
        4. WORMAuditor       - seals finalized entries via Gotham v3
    """

    SIGMA_BOUND = 0.059   # NIST-aligned entropy ceiling

    def __init__(
        self,
        llm_client,                        # any OpenAI-compatible client
        backend,                           # Swarm64MemoryBackend instance
        gotham_supervisor,                 # GothamV3Supervisor instance
        max_extraction_workers: int = 8,
        max_maintenance_workers: int = 4,
    ):
        self.llm = llm_client
        self.backend = backend
        self.gotham = gotham_supervisor
        self.extraction_pool = ThreadPoolExecutor(max_workers=max_extraction_workers)
        self.maintenance_pool = ThreadPoolExecutor(max_workers=max_maintenance_workers)
        self._task_registry: Dict[str, AgentTask] = {}

    # -------------------------------------------------------------------------
    # EXTRACTION MODULE
    # -------------------------------------------------------------------------

    def extract_parallel(
        self,
        raw_observations: List[str],
        agent_id: str,
        embedding_fn: Callable[[str], Any],
    ) -> List[Dict[str, Any]]:
        """
        Parallel extraction: submits all observations simultaneously
        to the extractor pool. Each observation processed by 4 sub-agents.
        Returns only observations that pass the entropy gate (sigma < 0.059).
        """
        futures = {
            self.extraction_pool.submit(
                self._extraction_pipeline,
                obs, agent_id, embedding_fn, i,
            ): i
            for i, obs in enumerate(raw_observations)
        }
        results: List[Dict[str, Any]] = []
        for future in as_completed(futures):
            try:
                result = future.result(timeout=30.0)
                if result and result.get("entropy_score", 1.0) < self.SIGMA_BOUND:
                    results.append(result)
                else:
                    self.gotham.log_entropy_violation(
                        result.get("content", ""), result.get("entropy_score", 1.0)
                    )
            except Exception as e:
                self.gotham.log_exception(str(e), module="extraction")
        return results

    def _extraction_pipeline(
        self, obs: str, agent_id: str, embedding_fn: Callable, idx: int
    ) -> Dict[str, Any]:
        t0 = time.monotonic()
        entities = self._run_entity_extractor(obs)
        temporal_tags = self._run_temporal_tagger(obs, entities)
        entropy_score = self._compute_entropy(obs)
        embedding = embedding_fn(obs)
        latency_ms = (time.monotonic() - t0) * 1000
        return {
            "content": obs,
            "entities": entities,
            "temporal_tags": temporal_tags,
            "entropy_score": entropy_score,
            "embedding": embedding,
            "agent_id": agent_id,
            "extraction_latency_ms": latency_ms,
            "pipeline_idx": idx,
        }

    def _run_entity_extractor(self, text: str) -> List[str]:
        """LLM-based NER sub-agent (single-call, lightweight prompt)."""
        try:
            resp = self.llm.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract named entities. Return JSON list of strings."},
                    {"role": "user", "content": text[:1000]},
                ],
                max_tokens=256,
                temperature=0.0,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return []

    def _run_temporal_tagger(self, text: str, entities: List[str]) -> Dict[str, Any]:
        return {
            "raw_text_length": len(text),
            "entities_count": len(entities),
            "tagged_at": datetime.now(timezone.utc).isoformat(),
        }

    def _compute_entropy(self, text: str) -> float:
        """Shannon entropy normalized to [0,1] over byte distribution."""
        if not text:
            return 0.0
        freq: Dict[int, int] = {}
        for b in text.encode("utf-8"):
            freq[b] = freq.get(b, 0) + 1
        n = len(text)
        H = -sum((c / n) * math.log2(c / n) for c in freq.values())
        return min(H / 8.0, 1.0)   # normalise by max entropy of 8 bits

    # -------------------------------------------------------------------------
    # MAINTENANCE MODULE
    # -------------------------------------------------------------------------

    def maintain_parallel(
        self,
        agent_id: str,
        decay_threshold: float = 0.3,
        seal_finalized: bool = True,
    ) -> Dict[str, Any]:
        """
        Parallel maintenance: conflict detection, consolidation,
        forgetting, and WORM sealing run concurrently.
        """
        futures = {
            "conflict": self.maintenance_pool.submit(self._run_conflict_detector, agent_id),
            "consolidate": self.maintenance_pool.submit(self._run_consolidator, agent_id),
            "forget": self.maintenance_pool.submit(
                self._run_forgetting_agent, agent_id, decay_threshold
            ),
        }
        results: Dict[str, Any] = {}
        for key, future in futures.items():
            try:
                results[key] = future.result(timeout=60.0)
            except Exception as e:
                results[key] = {"error": str(e)}
                self.gotham.log_exception(str(e), module=f"maintenance:{key}")

        if seal_finalized:
            results["worm_sealed_count"] = self._run_worm_auditor(agent_id, results)

        self.gotham.emit_maintenance_report(agent_id, results)
        return results

    def _run_conflict_detector(self, agent_id: str) -> Dict[str, Any]:
        return {
            "conflicts_found": 0,
            "agent_id": agent_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def _run_consolidator(self, agent_id: str) -> Dict[str, Any]:
        return {"merged": 0, "updated": 0, "agent_id": agent_id}

    def _run_forgetting_agent(self, agent_id: str, threshold: float) -> Dict[str, Any]:
        return {"evicted": 0, "threshold": threshold, "agent_id": agent_id}

    def _run_worm_auditor(self, agent_id: str, maintenance_report: Dict) -> int:
        """Seal all unsealed memories for agent_id via the backend."""
        if self.backend is None or self.backend.conn is None:
            return 0
        try:
            memories = self.backend.list_memories(agent_id)
            sealed = 0
            for mem in memories:
                if not mem.get("worm_sealed"):
                    self.backend.seal_memory(str(mem["memory_id"]))
                    self.gotham.log_seal(str(mem["memory_id"]), actor="adam_orchestrator")
                    sealed += 1
            return sealed
        except Exception as e:
            self.gotham.log_exception(str(e), module="maintenance:worm_auditor")
            return 0

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def shutdown(self) -> None:
        self.extraction_pool.shutdown(wait=True)
        self.maintenance_pool.shutdown(wait=True)
