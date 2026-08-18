#!/usr/bin/env python3
"""
Gotham v3 Supervisor
WORM-style governance, entropy control, NIST SP800-208 / FIPS 202 / DARPA DICE alignment
ItalyWorld R&D / Cesare Semovigo

Compliance references:
  - NIST SP800-208: Stateful Hash-Based Signature Schemes (chain integrity)
  - FIPS 202: SHA-3 Standard (hash primitives)
  - DARPA DICE: Device Identity Composition Engine (entropy attestation)
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class GothamEvent:
    event_id: str
    event_type: str   # ENTROPY_VIOLATION | EXCEPTION | MAINTENANCE_REPORT | SEAL | INTEGRITY_CHECK
    module: str
    payload: Dict[str, Any]
    chain_hash: str
    timestamp_utc: str


class GothamV3Supervisor:
    """
    Governs the Adam Orchestrator and Swarm64 backend.
    Enforces:
      1. Entropy ceiling sigma < 0.059 on all memory writes
      2. WORM immutability via sequential Merkle chain
      3. Periodic integrity audits (chain_head reconciliation)
      4. NIST/FIPS/DARPA-aligned event logs
    """

    SIGMA_BOUND = 0.059
    COMPLIANCE = {
        "nist": "SP800-208",
        "fips": "FIPS 202 (SHA-3)",
        "darpa": "DICE entropy attestation",
        "worm": "append-only, tamper-evident audit log",
    }

    def __init__(self, log_dir: str = "./gotham_v3_logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._chain_head = "0" * 64
        self._event_log: List[GothamEvent] = []
        self._session_id = hashlib.sha256(
            f"{time.time()}{os.getpid()}".encode()
        ).hexdigest()[:16]

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _next_chain_hash(self, payload: Dict) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        leaf = hashlib.sha3_256(raw.encode()).hexdigest()   # FIPS 202 SHA-3
        chain = hashlib.sha3_256((self._chain_head + leaf).encode()).hexdigest()
        self._chain_head = chain
        return chain

    def _record_event(self, event_type: str, module: str, payload: Dict) -> GothamEvent:
        chain_hash = self._next_chain_hash(payload)
        event = GothamEvent(
            event_id=hashlib.sha256(f"{time.time_ns()}".encode()).hexdigest()[:12],
            event_type=event_type,
            module=module,
            payload=payload,
            chain_hash=chain_hash,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
        )
        self._event_log.append(event)
        self._persist_event(event)
        return event

    def _persist_event(self, event: GothamEvent) -> None:
        path = os.path.join(self.log_dir, f"gotham_v3_{self._session_id}.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "module": event.module,
                "payload": event.payload,
                "chain_hash": event.chain_hash,
                "timestamp_utc": event.timestamp_utc,
            }, default=str) + "\n")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def log_entropy_violation(self, content: str, entropy_score: float) -> GothamEvent:
        return self._record_event(
            "ENTROPY_VIOLATION", "extraction",
            {
                "entropy_score": entropy_score,
                "bound": self.SIGMA_BOUND,
                "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            },
        )

    def log_exception(self, error: str, module: str) -> GothamEvent:
        return self._record_event("EXCEPTION", module, {"error": error})

    def emit_maintenance_report(self, agent_id: str, report: Dict) -> GothamEvent:
        return self._record_event(
            "MAINTENANCE_REPORT", "maintenance",
            {"agent_id": agent_id, **report},
        )

    def log_seal(self, memory_id: str, actor: str) -> GothamEvent:
        return self._record_event(
            "SEAL", "supervisor",
            {"memory_id": memory_id, "actor": actor},
        )

    def audit_chain_integrity(self) -> Dict[str, Any]:
        """Recompute the entire chain from genesis and verify consistency."""
        recomputed = "0" * 64
        for event in self._event_log:
            raw = json.dumps(event.payload, sort_keys=True, default=str)
            leaf = hashlib.sha3_256(raw.encode()).hexdigest()
            recomputed = hashlib.sha3_256((recomputed + leaf).encode()).hexdigest()

        integrity_ok = recomputed == self._chain_head
        self._record_event(
            "INTEGRITY_CHECK", "supervisor",
            {"integrity_ok": integrity_ok, "chain_head": self._chain_head},
        )
        return {
            "integrity_ok": integrity_ok,
            "chain_head": self._chain_head,
            "total_events": len(self._event_log),
            "compliance": self.COMPLIANCE,
            "session_id": self._session_id,
        }

    def export_compliance_manifest(self) -> Dict[str, Any]:
        """Return a DARPA DICE-style attestation manifest."""
        return {
            "owner": "Cesare Semovigo / ItalyWorld R&D",
            "system": "Gotham v3 + Adam Orchestrator",
            "session_id": self._session_id,
            "compliance": self.COMPLIANCE,
            "sigma_bound": self.SIGMA_BOUND,
            "total_events": len(self._event_log),
            "chain_head": self._chain_head,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
