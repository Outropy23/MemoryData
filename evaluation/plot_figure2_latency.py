#!/usr/bin/env python3
"""
Figure 2 — Latency Distribution Plotter
Generates publication-quality plots from Swarm64 benchmark results.
Cesare Semovigo — Gotham v3 Bridge

Usage:
    python evaluation/plot_figure2_latency.py \
        --results_dir results/swarm64 \
        --output figure2_latency_distribution.png
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

WORKLOAD_IDS = [
    "single_session",
    "multi_session",
    "knowledge_update",
    "long_horizon",
    "adversarial",
]
WORKLOAD_LABELS = [
    "Single\nSession",
    "Multi\nSession",
    "Knowledge\nUpdate",
    "Long\nHorizon",
    "Adversarial",
]
COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


def load_metrics(results_dir: str) -> dict:
    data: dict = {}
    for wid in WORKLOAD_IDS:
        path = os.path.join(results_dir, f"{wid}_metrics.json")
        if os.path.exists(path):
            with open(path) as f:
                data[wid] = json.load(f)
    return data


def plot_figure2(data: dict, output: str) -> None:
    fig = plt.figure(figsize=(18, 10))
    fig.suptitle(
        "Figure 2 — Adam Orchestrator + Swarm64 Backend: Latency Distributions\n"
        "Workloads: MemoryData Benchmark Suite · Cesare Semovigo / Gotham v3",
        fontsize=13,
        fontweight="bold",
        y=0.98,
    )
    gs = gridspec.GridSpec(2, 3, hspace=0.45, wspace=0.35)

    workloads_present = [wid for wid in WORKLOAD_IDS if wid in data]
    labels_present = [WORKLOAD_LABELS[i] for i, wid in enumerate(WORKLOAD_IDS) if wid in data]
    colors_present = [COLORS[i] for i, wid in enumerate(WORKLOAD_IDS) if wid in data]

    # Panel A: Insert latency violin per workload
    ax_insert = fig.add_subplot(gs[0, :2])
    insert_data = [data[wid]["insert_latencies_ms"] for wid in workloads_present]
    vp = ax_insert.violinplot(insert_data, showmedians=True, showextrema=True)
    for i, pc in enumerate(vp["bodies"]):
        pc.set_facecolor(colors_present[i])
        pc.set_alpha(0.7)
    ax_insert.set_xticks(range(1, len(insert_data) + 1))
    ax_insert.set_xticklabels(labels_present)
    ax_insert.set_ylabel("Latency (ms)")
    ax_insert.set_title("(A) Insert Latency Distribution by Workload", fontweight="bold")
    ax_insert.axhline(y=5, color="red", linestyle="--", alpha=0.5, label="5ms SLA")
    ax_insert.legend(fontsize=9)

    # Panel B: Retrieval latency violin
    ax_retrieval = fig.add_subplot(gs[1, :2])
    retrieval_data = [data[wid]["retrieval_latencies_ms"] for wid in workloads_present]
    vp2 = ax_retrieval.violinplot(retrieval_data, showmedians=True, showextrema=True)
    for i, pc in enumerate(vp2["bodies"]):
        pc.set_facecolor(colors_present[i])
        pc.set_alpha(0.7)
    ax_retrieval.set_xticks(range(1, len(retrieval_data) + 1))
    ax_retrieval.set_xticklabels(labels_present)
    ax_retrieval.set_ylabel("Latency (ms)")
    ax_retrieval.set_title("(B) Vector Retrieval Latency Distribution by Workload", fontweight="bold")

    # Panel C: P50 vs P99 insert bar
    ax_bar = fig.add_subplot(gs[0, 2])
    p50s = [data[wid]["insert_p50_ms"] for wid in workloads_present]
    p99s = [data[wid]["insert_p99_ms"] for wid in workloads_present]
    x = np.arange(len(workloads_present))
    ax_bar.bar(x - 0.2, p50s, 0.4, label="P50", color="steelblue", alpha=0.85)
    ax_bar.bar(x + 0.2, p99s, 0.4, label="P99", color="tomato", alpha=0.85)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(labels_present, fontsize=8)
    ax_bar.set_ylabel("ms")
    ax_bar.set_title("(C) Insert P50 vs P99", fontweight="bold")
    ax_bar.legend(fontsize=9)

    # Panel D: P50 vs P99 retrieval bar
    ax_rbar = fig.add_subplot(gs[1, 2])
    rp50s = [data[wid]["retrieval_p50_ms"] for wid in workloads_present]
    rp99s = [data[wid]["retrieval_p99_ms"] for wid in workloads_present]
    ax_rbar.bar(x - 0.2, rp50s, 0.4, label="P50", color="steelblue", alpha=0.85)
    ax_rbar.bar(x + 0.2, rp99s, 0.4, label="P99", color="tomato", alpha=0.85)
    ax_rbar.set_xticks(x)
    ax_rbar.set_xticklabels(labels_present, fontsize=8)
    ax_rbar.set_ylabel("ms")
    ax_rbar.set_title("(D) Retrieval P50 vs P99", fontweight="bold")
    ax_rbar.legend(fontsize=9)

    plt.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    print(f"Figure 2 saved: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", default="results/swarm64")
    parser.add_argument("--output", default="figure2_latency_distribution.png")
    args = parser.parse_args()
    data = load_metrics(args.results_dir)
    if not data:
        print(f"No benchmark results found in {args.results_dir}. Run run_swarm64_benchmark.py first.")
        sys.exit(1)
    plot_figure2(data, args.output)


if __name__ == "__main__":
    main()
