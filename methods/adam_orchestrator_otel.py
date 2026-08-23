#!/usr/bin/env python3
"""
Adam Orchestrator v1 — OpenTelemetry Instrumented
Emits OTLP traces + latency histograms for Extraction and Maintenance pipelines.
ItalyWorld R&D / Cesare Semovigo — Gotham v3 Bridge

Instrumentation coverage:
  - Span per extract_parallel() call (root span)
  - Span per _extraction_pipeline() worker (child spans in parallel)
  - Histogram: adam.extraction.latency_ms
  - Histogram: adam.maintenance.latency_ms
  - Counter: adam.entropy_violations_total
  - Gauge: adam.active_workers

Exporter: OTLP/gRPC -> localhost:4317 (override via OTEL_EXPORTER_OTLP_ENDPOINT)
"""

import time
import math
import json
import hashlib
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# OpenTelemetry
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource


def _init_otel(service_name: str = "adam-orchestrator", endpoint: str = "http://localhost:4317") -> None:
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
        "gotham.version": "v3",
        "project": "memorydata-swarm64",
    })
    # Tracer
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(tp)
    # Meter
    reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint, insecure=True), export_interval_millis=5000)
    mp = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(mp)


class AdamOrchestratorOTel:
    """
    Instrumented Adam Orchestrator.
    Drop-in replacement for AdamOrchestrator with full OTel observability.
    """

    SIGMA_BOUND = 0.059

    def __init__(
        self,
        llm_client,
        backend,
        gotham_supervisor,
        max_extraction_workers: int = 8,
        max_maintenance_workers: int = 4,
        otel_endpoint: str = "http://localhost:4317",
    ):
        _init_otel(endpoint=otel_endpoint)
        self.tracer = trace.get_tracer("adam.orchestrator")
        meter = metrics.get_meter("adam.orchestrator")

        # Metrics instruments
        self.extraction_latency = meter.create_histogram(
            name="adam.extraction.latency_ms",
            description="Per-observation extraction pipeline latency",
            unit="ms",
        )
        self.maintenance_latency = meter.create_histogram(
            name="adam.maintenance.latency_ms",
            description="Maintenance round latency",
            unit="ms",
        )
        self.entropy_violations = meter.create_counter(
            name="adam.entropy_violations_total",
            description="Memory insertions rejected for sigma >= 0.059",
        )
        self.active_workers = meter.create_up_down_counter(
            name="adam.active_workers",
            description="Currently active extraction/maintenance workers",
        )

        self.llm = llm_client
        self.backend = backend
        self.gotham = gotham_supervisor
        self.extraction_pool = ThreadPoolExecutor(max_workers=max_extraction_workers)
        self.maintenance_pool = ThreadPoolExecutor(max_workers=max_maintenance_workers)

    # -------------------------------------------------------------------------
    # EXTRACTION MODULE (instrumented)
    # -------------------------------------------------------------------------

    def extract_parallel(
        self,
        raw_observations: List[str],
        agent_id: str,
        embedding_fn: Callable,
    ) -> List[Dict[str, Any]]:
        with self.tracer.start_as_current_span(
            "adam.extract_parallel",
            attributes={
                "agent_id": agent_id,
                "observation_count": len(raw_observations),
                "sigma_bound": self.SIGMA_BOUND,
            },
        ) as root_span:
            self.active_workers.add(len(raw_observations))
            futures = {
                self.extraction_pool.submit(
                    self._extraction_pipeline_otel,
                    obs, agent_id, embedding_fn, i, trace.get_current_span().get_span_context()
                ): i
                for i, obs in enumerate(raw_observations)
            }
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30.0)
                    if result and result.get("entropy_score", 1.0) < self.SIGMA_BOUND:
                        results.append(result)
                    else:
                        self.entropy_violations.add(1, {"agent_id": agent_id})
                        self.gotham.log_entropy_violation(
                            result.get("content", ""), result.get("entropy_score", 1.0)
                        )
                except Exception as e:
                    root_span.record_exception(e)
                    self.gotham.log_exception(str(e), module="extraction")
            self.active_workers.add(-len(raw_observations))
            root_span.set_attribute("accepted_memories", len(results))
            return results

    def _extraction_pipeline_otel(
        self, obs: str, agent_id: str, embedding_fn, idx: int, parent_ctx
    ) -> Dict:
        with self.tracer.start_as_current_span(
            f"adam.extraction.worker",
            context=trace.set_span_in_context(trace.NonRecordingSpan(parent_ctx)),
            attributes={"worker_index": idx, "content_len": len(obs)},
        ) as span:
            t0 = time.monotonic()
            entropy_score = self._compute_entropy(obs)
            embedding = embedding_fn(obs)
            latency_ms = (time.monotonic() - t0) * 1000
            self.extraction_latency.record(latency_ms, {"agent_id": agent_id})
            span.set_attribute("latency_ms", latency_ms)
            span.set_attribute("entropy_score", entropy_score)
            return {
                "content": obs,
                "entropy_score": entropy_score,
                "embedding": embedding,
                "agent_id": agent_id,
                "extraction_latency_ms": latency_ms,
                "pipeline_idx": idx,
            }

    def _compute_entropy(self, text: str) -> float:
        if not text:
            return 0.0
        freq: Dict[int, int] = {}
        for b in text.encode("utf-8"):
            freq[b] = freq.get(b, 0) + 1
        n = len(text)
        H = -sum((c / n) * math.log2(c / n) for c in freq.values())
        return min(H / 8.0, 1.0)

    # -------------------------------------------------------------------------
    # MAINTENANCE MODULE (instrumented)
    # -------------------------------------------------------------------------

    def maintain_parallel(self, agent_id: str, decay_threshold: float = 0.3, seal_finalized: bool = True) -> Dict[str, Any]:
        with self.tracer.start_as_current_span(
            "adam.maintain_parallel",
            attributes={"agent_id": agent_id, "decay_threshold": decay_threshold},
        ) as root_span:
            t0 = time.monotonic()
            futures = {
                "conflict": self.maintenance_pool.submit(self._timed_task, "conflict_detector", agent_id),
                "consolidate": self.maintenance_pool.submit(self._timed_task, "consolidator", agent_id),
                "forget": self.maintenance_pool.submit(self._timed_task, "forgetting_agent", agent_id),
            }
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=60.0)
                except Exception as e:
                    root_span.record_exception(e)
                    results[key] = {"error": str(e)}
            total_ms = (time.monotonic() - t0) * 1000
            self.maintenance_latency.record(total_ms, {"agent_id": agent_id})
            root_span.set_attribute("total_maintenance_ms", total_ms)
            self.gotham.emit_maintenance_report(agent_id, results)
            return results

    def _timed_task(self, task_name: str, agent_id: str) -> Dict:
        with self.tracer.start_as_current_span(
            f"adam.maintenance.{task_name}",
            attributes={"agent_id": agent_id}
        ) as span:
            t0 = time.monotonic()
            time.sleep(0.001)  # placeholder for real task
            ms = (time.monotonic() - t0) * 1000
            span.set_attribute("task_latency_ms", ms)
            return {"task": task_name, "latency_ms": ms, "agent_id": agent_id}

    def shutdown(self) -> None:
        self.extraction_pool.shutdown(wait=True)
        self.maintenance_pool.shutdown(wait=True)
