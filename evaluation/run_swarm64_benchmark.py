#!/usr/bin/env python3
"""
MemoryData Benchmark Harness — Swarm64MemoryBackend
Wires evaluation/ scripts against the PostgreSQL + Swarm64 DA backend.
Cesare Semovigo — Gotham v3 Bridge

Usage:
    python evaluation/run_swarm64_benchmark.py \
        --pg_host localhost --pg_port 5432 \
        --pg_db memorydata_swarm64 --pg_user adam_agent --pg_password '' \
        --workloads single_session multi_session knowledge_update long_horizon adversarial \
        --output_dir results/swarm64
"""

import argparse
import json
import os
import sys
import time
import statistics
from pathlib import Path
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from methods.swarm64_backend import Swarm64MemoryBackend, Swarm64Config
from gotham_v3.supervisor import GothamV3Supervisor

WORKLOAD_IDS = [
    "single_session",
    "multi_session",
    "knowledge_update",
    "long_horizon",
    "adversarial",
]


def run_workload(
    workload_id: str,
    backend: Swarm64MemoryBackend,
    gotham: GothamV3Supervisor,
    output_dir: str,
) -> dict:
    print(f"  Running workload: {workload_id} ...", flush=True)
    metrics: dict = {
        "workload": workload_id,
        "insert_latencies_ms": [],
        "retrieval_latencies_ms": [],
    }

    rng = np.random.default_rng(seed=42)
    n_inserts = 200
    n_queries = 50
    dim = 1536

    # INSERT phase
    for i in range(n_inserts):
        emb = rng.standard_normal(dim).astype(np.float32)
        emb /= np.linalg.norm(emb)
        t0 = time.monotonic()
        backend.insert_memory(
            agent_id="bench_agent",
            module="extraction",
            content=f"{workload_id} observation {i}",
            embedding=emb,
            metadata={"workload": workload_id, "idx": i},
            entropy_score=0.03 + (i % 10) * 0.003,  # vary below sigma bound
        )
        metrics["insert_latencies_ms"].append((time.monotonic() - t0) * 1000)

    # RETRIEVAL phase
    for _ in range(n_queries):
        qemb = rng.standard_normal(dim).astype(np.float32)
        qemb /= np.linalg.norm(qemb)
        t0 = time.monotonic()
        backend.vector_search(qemb, top_k=10, module_filter="extraction")
        metrics["retrieval_latencies_ms"].append((time.monotonic() - t0) * 1000)

    metrics["insert_p50_ms"] = statistics.median(metrics["insert_latencies_ms"])
    metrics["insert_p99_ms"] = sorted(metrics["insert_latencies_ms"])[int(0.99 * n_inserts)]
    metrics["retrieval_p50_ms"] = statistics.median(metrics["retrieval_latencies_ms"])
    metrics["retrieval_p99_ms"] = sorted(metrics["retrieval_latencies_ms"])[int(0.99 * n_queries)]
    metrics["timestamp_utc"] = datetime.now(timezone.utc).isoformat()

    gotham.emit_maintenance_report("bench_agent", {"workload": workload_id, "inserts": n_inserts})

    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{workload_id}_metrics.json")
    with open(out_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"    -> insert  p50={metrics['insert_p50_ms']:.2f}ms  p99={metrics['insert_p99_ms']:.2f}ms")
    print(f"    -> retrieval p50={metrics['retrieval_p50_ms']:.2f}ms  p99={metrics['retrieval_p99_ms']:.2f}ms")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="MemoryData Swarm64 Benchmark")
    parser.add_argument("--pg_host", default="localhost")
    parser.add_argument("--pg_port", type=int, default=5432)
    parser.add_argument("--pg_db", default="memorydata_swarm64")
    parser.add_argument("--pg_user", default="adam_agent")
    parser.add_argument("--pg_password", default="")
    parser.add_argument("--workloads", nargs="+", default=WORKLOAD_IDS)
    parser.add_argument("--output_dir", default="results/swarm64")
    args = parser.parse_args()

    cfg = Swarm64Config(
        host=args.pg_host,
        port=args.pg_port,
        database=args.pg_db,
        user=args.pg_user,
        password=args.pg_password,
        s64da_enable_columnar=True,
        s64da_parallel_workers=64,
    )
    backend = Swarm64MemoryBackend(cfg)
    backend.connect()
    gotham = GothamV3Supervisor(
        log_dir=os.path.join(args.output_dir, "gotham_v3_logs")
    )

    all_metrics = []
    print(f"Running {len(args.workloads)} workload(s) against Swarm64 backend ...")
    for wid in args.workloads:
        all_metrics.append(run_workload(wid, backend, gotham, args.output_dir))

    summary_path = os.path.join(args.output_dir, "benchmark_summary.json")
    with open(summary_path, "w") as f:
        json.dump(all_metrics, f, indent=2)

    integrity = gotham.audit_chain_integrity()
    print(f"\nGotham v3 chain integrity: {integrity['integrity_ok']}")
    print(f"Total events logged:        {integrity['total_events']}")
    print(f"Summary written to:         {summary_path}")
    backend.close()


if __name__ == "__main__":
    main()
