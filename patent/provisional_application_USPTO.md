# UNITED STATES PATENT AND TRADEMARK OFFICE
## PROVISIONAL PATENT APPLICATION

**Title of Invention:**
System and Method for Tamper-Resistant, Entropy-Gated, Hardware-Accelerated Memory Management in Large Language Model Agents

**Applicant:** ItalyWorld R&D Research Team — Ing. Cesare Semovigo
**Filing Basis:** 35 U.S.C. § 111(b)
**Correspondence Address:** [Attorney / Agent Address — to be completed]
**Date Prepared:** 2026-06-30

> ⚠️ LEGAL DISCLAIMER: This document is a technical skeleton prepared for counsel review. It constitutes prior art disclosure establishing earliest possible priority date under 35 U.S.C. § 111(b). It does NOT constitute a filed patent application. Filing requires submission via EFS-Web at https://www.uspto.gov with the applicable fees ($320 micro-entity / $640 small entity as of 2026). A registered patent attorney should review and file this document within 12 months to claim priority.

---

## 1. FIELD OF THE INVENTION

The present invention relates to memory management systems for artificial intelligence agents based on large language models (LLMs), and more particularly to systems and methods that combine hardware-accelerated columnar database backends, entropy-gated memory insertion, WORM-style tamper-evident audit chains, and multi-agent parallel orchestration to provide tamper-resistant, compliance-aligned persistent memory for autonomous AI agents.

---

## 2. BACKGROUND

Existing LLM agent memory systems (see Zhou et al., arXiv:2606.24775, “Are We Ready For An Agent-Native Memory System?”, 2026) decompose memory into four modules: representation/storage, extraction, retrieval/routing, and maintenance. All twelve systems evaluated in said work employ exclusively software-based backends (vector databases, key-value stores, SQL databases) without hardware acceleration, without entropy-based quality control on memory insertion, and without tamper-evident audit mechanisms compliant with NIST, FIPS, or DARPA standards.

There is therefore a need in the art for an agent memory system that:
- Eliminates software-only retrieval bottlenecks via hardware-accelerated columnar query processing;
- Prevents insertion of high-entropy (noisy or adversarially crafted) content via a computable entropy gate;
- Provides cryptographically verifiable tamper-evidence for every memory write operation;
- Supports parallel multi-agent decomposition of extraction and maintenance with centralized compliance enforcement.

---

## 3. SUMMARY OF THE INVENTION

The present invention provides a memory management system for LLM agents comprising three principal components operating in concert:

**Component A — Swarm64-Accelerated PostgreSQL Backend:** A unified columnar database backend executing vector similarity search and SQL analytics via hardware acceleration (optionally FPGA-assisted), replacing fragmented FAISS/ChromaDB/SQLite backends with a single auditable data store.

**Component B — Adam Orchestrator:** A multi-agent parallel orchestration layer that decomposes memory extraction into concurrent sub-agents (entity extraction, temporal tagging, entropy guard, embedding generation) and memory maintenance into concurrent sub-tasks (conflict detection, consolidation, forgetting, WORM auditing), coordinated by a central supervisor enforcing the entropy bound σ < 0.059.

**Component C — Gotham v3 Supervisor:** A governance layer implementing a sequential SHA-3-256 Merkle chain over all memory write operations, providing: (i) WORM immutability via database-trigger enforcement; (ii) entropy attestation aligned with DARPA DICE; (iii) compliance manifest export aligned with NIST SP800-208 and FIPS 202.

---

## 4. DETAILED DESCRIPTION OF PREFERRED EMBODIMENTS

### 4.1 Swarm64-Accelerated Backend (Component A)

In a preferred embodiment, the backend is implemented as a PostgreSQL 16 instance with the Swarm64 DA 4.0 extension installed, enabling columnar storage and parallel query execution on up to 64 concurrent threads. The `pgvector` extension provides IVFFlat-indexed cosine similarity search over 1536-dimensional embeddings. All memory entries are stored in a table `agent_memory` with columns: `memory_id UUID`, `content TEXT`, `embedding vector(1536)`, `entropy_score FLOAT8`, `merkle_hash TEXT`, `worm_sealed BOOLEAN`. A PostgreSQL trigger `enforce_worm()` raises an exception on any `UPDATE` or `DELETE` of a row where `worm_sealed = TRUE`, providing database-level immutability enforcement independent of the application layer.

### 4.2 Adam Orchestrator (Component B)

In a preferred embodiment, the Adam Orchestrator employs Python `ThreadPoolExecutor` pools (8 workers for extraction, 4 for maintenance) to submit all observations or maintenance sub-tasks concurrently. Each extraction worker executes a four-stage pipeline: (1) LLM-based named entity recognition; (2) temporal tagging; (3) Shannon entropy computation normalized to [0,1]; (4) vector embedding generation. Workers whose entropy score meets or exceeds σ = 0.059 have their output rejected and logged as `ENTROPY_VIOLATION` events by the Gotham v3 Supervisor rather than inserted into the database.

### 4.3 Gotham v3 Supervisor (Component C)

In a preferred embodiment, the Gotham v3 Supervisor maintains a sequential Merkle chain:

    chain[i] = SHA3-256( chain[i-1] || SHA3-256( serialize(payload[i]) ) )

where `SHA3-256` is the FIPS 202-compliant hash function and `serialize()` produces a canonical JSON representation sorted by key. The chain head `chain[n]` serves as a compact cryptographic commitment over all n memory writes. Verification is performed by `audit_chain_integrity()` which recomputes the chain from genesis and compares to the stored head; any alteration of any payload is detected with probability 1 - 2^{-256}. Events are persisted to an append-only JSONL file constituting the WORM audit log.

---

## 5. CLAIMS

> Note: Claims are optional in provisional applications per 35 U.S.C. § 111(b)(2) but are included here to establish claim scope for priority purposes. Non-provisional claims should be drafted by registered patent counsel.

**Claim 1 (System — Independent):** A memory management system for large language model agents comprising:
(a) a hardware-accelerated columnar database backend configured to execute parallel vector similarity search and SQL analytics on agent memory entries;
(b) an entropy-gated insertion module configured to compute a Shannon entropy score for each candidate memory entry and reject entries whose entropy score meets or exceeds a predetermined entropy bound σ;
(c) a tamper-evident audit chain constructed as a sequential hash chain over all accepted memory write operations, wherein each chain link is computed as H(chain[i-1] || H(payload[i])) using a cryptographically secure hash function H;
(d) a write-once, read-many (WORM) immutability enforcement mechanism configured to prevent modification or deletion of sealed memory entries at the database layer.

**Claim 2 (Method — Independent):** A method for tamper-resistant agent memory maintenance comprising:
(a) decomposing maintenance operations into a plurality of parallel sub-agent tasks executing concurrently;
(b) for each accepted memory write, generating a hash chain link using a FIPS 202-compliant hash function;
(c) enforcing write-once immutability of sealed memory entries via a database-layer trigger;
(d) generating and exporting a compliance manifest identifying the chain head, total event count, session identifier, and alignment with at least one of NIST SP800-208, FIPS 202, or DARPA DICE standards.

**Claim 3 (System — Dependent on Claim 1):** The system of Claim 1, further comprising a parallel extraction pipeline comprising at least:
(a) an entity extraction sub-agent performing named entity recognition on raw observations;
(b) a temporal tagging sub-agent anchoring extracted entities to temporal references;
(c) an entropy guard sub-agent computing a normalized Shannon entropy score for each observation;
(d) an embedding generation sub-agent generating a vector representation of each observation;
wherein sub-agents (a) through (d) execute concurrently and their outputs are aggregated by a central orchestrator that enforces the entropy bound σ prior to memory insertion.

---

## 6. ABSTRACT

A memory management system and method for large language model (LLM) agents providing tamper-resistant, entropy-gated, hardware-accelerated persistent memory. The system comprises: (A) a Swarm64-accelerated PostgreSQL backend with pgvector cosine similarity indexing and WORM-enforced immutability triggers; (B) an Adam Orchestrator multi-agent parallel pipeline for extraction (8 concurrent workers) and maintenance (4 concurrent workers) with Shannon entropy gating (sigma < 0.059); (C) a Gotham v3 Supervisor implementing a sequential FIPS 202 SHA-3-256 Merkle chain over all memory writes, aligned with NIST SP800-208 and DARPA DICE. The system eliminates the single-LLM extraction bottleneck, provides cryptographically verifiable tamper-evidence with P(undetected alteration) < 2^{-256}, and reduces agent memory infrastructure cost via hardware acceleration.

---

## 7. DRAWINGS REFERENCE

- Figure 1: System architecture overview (Adam Orchestrator + Gotham v3 + Swarm64 PostgreSQL)
- Figure 2: Latency distribution plots (insert and retrieval) across 5 MemoryData workloads (generated by `evaluation/plot_figure2_latency.py`)
- Figure 3: Merkle chain structure and tamper-detection proof diagram

---

## 8. PRIOR ART DISTINGUISHED

Zhou et al. (arXiv:2606.24775, 2026): Evaluates 12 memory systems; none employs hardware-accelerated columnar backends, entropy-gated insertion, or WORM Merkle chain governance. The present invention is novel over all 12 evaluated systems and the two reference baselines.

Swarm64 DA (PostgreSQL extension, Swarm64 GmbH, 2020): Provides hardware acceleration for PostgreSQL; does not address LLM agent memory, entropy gating, or WORM governance.

pgvector (open source extension): Provides vector similarity search for PostgreSQL; does not address entropy gating, WORM audit chains, or multi-agent orchestration.

---

## 9. FILING INSTRUCTIONS FOR COUNSEL

1. Review and finalize claims with registered patent attorney.
2. Prepare formal drawings (Figures 1-3) per USPTO 37 CFR 1.84.
3. File via USPTO EFS-Web: https://www.uspto.gov/patents/apply/applying-online
4. Select application type: Provisional Application (35 U.S.C. § 111(b))
5. Fee: $320 (micro-entity) / $640 (small entity) / $1,600 (large entity) — verify current fee schedule at USPTO.
6. Retain filing receipt as proof of priority date.
7. File non-provisional application within 12 months of provisional filing date to claim priority benefit.

---

*Document prepared by Perplexity AI for ItalyWorld R&D / Ing. Cesare Semovigo — 2026-06-30*
*This is a technical disclosure document, not legal advice. Consult a registered patent attorney.*
