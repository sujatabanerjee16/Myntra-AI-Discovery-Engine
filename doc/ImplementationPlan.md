# Phase-Wise Implementation Plan

> This plan operationalizes the architecture in [`Architecture.md`](./Architecture.md), grounded in [`context.md`](./context.md) and [`ProblemStatement.md`](./ProblemStatement.md). It sequences the build into phases, each with objectives, tasks, deliverables, and exit criteria. Phases are ordered by dependency; later phases assume earlier ones are complete.

---

## Guiding Principles

- **Thin vertical slice first** — get one end-to-end path (a few sources → insight → answer) working before scaling breadth.
- **Evidence-grounded from day one** — provenance and confidence are built in, not bolted on.
- **Incremental & reproducible** — every pipeline run is versioned and re-runnable.
- **Ship usable increments** — each phase produces something a PM/researcher can look at.

---

## Phase Overview

| Phase | Name | Primary outcome |
| --- | --- | --- |
| 0 | Foundations & Setup | Repo, infra, and schemas ready (incl. platform/competitive fields) |
| 1 | Ingestion Pipeline (thin slice) | Clean, embedded corpus from 1–2 sources with platform tags |
| 2 | Storage & Data Layer | Vector + analytical + document stores wired (platform filters) |
| 3 | Semantic Analytics Layer | Taxonomy, clustering, intent, platform/motive, competitive aggregates, confidence |
| 4 | RAG Assistant | Grounded, cited Q&A over the corpus (incl. competitive questions) |
| 5 | Insight Dashboard + Ask AI (single page) | Ranked reasons, comparisons, heatmaps, competitive views + docked Ask AI |
| 6 | Evaluation & Hardening | Quality, guardrails, observability (incl. competitive claim faithfulness) |
| 7 | Corpus Scale-Out | All sources, competitor connectors, incremental refresh |
| 8 | Extensibility (Future) | Internal data + ground-truth metric |

---

## Phase 0 — Foundations & Setup

**Objective:** Establish the project skeleton so all later work has a home.

**Tasks**
- Initialize repo structure (monorepo: `ingestion/`, `analytics/`, `api/`, `web/`, `docs/`).
- Choose and provision Phase 1 stack: Python, PostgreSQL + pgvector, FastAPI, React.
- Set up environment/config management and secrets handling.
- Define the core data models from `Architecture.md` §5 (`Document`, `Chunk`, `Insight`, `CompetitiveAggregate`, `AnswerTrace`) as schema/migrations — including **platform**, **wishlist_motive**, and **comparison_scope** fields.
- Define the configurable competitor set (default: Nykaa, Ajio) and platform enum.
- Set up linting, formatting, testing, and CI scaffolding.

**Deliverables**
- Running local dev environment; empty DB with migrations applied; CI green.

**Exit criteria**
- A developer can clone, install, run migrations, and start the API/web shells locally.

---

## Phase 1 — Ingestion Pipeline (Thin Slice)

**Objective:** Turn raw feedback from **1–2 sources** into clean, embedded, enriched records with early platform awareness.

**Tasks**
- Implement a common raw ingestion schema and one/two connectors (e.g., Play Store reviews + Reddit).
- Prefer collection of wishlist-related and multi-platform comparison conversations.
- Build pipeline stages: clean/normalize → PII scrub → dedupe → chunk → embed → enrich.
- Enrich with preliminary **platform mention flags** (keyword/NER heuristics for Myntra, Nykaa, Ajio).
- Make runs **idempotent, incremental, and version-tagged**.
- Persist raw + processed docs and chunk lineage to the document store.

**Deliverables**
- A repeatable ingestion job producing embedded, tagged chunks from a sample corpus (with platform hints where present).

**Exit criteria**
- Re-running the pipeline is safe (no duplicates) and produces versioned output with provenance and platform metadata when detectable.

**Dependencies:** Phase 0.

---

## Phase 2 — Storage & Data Layer

**Objective:** Stand up the three stores and connect the pipeline output to them.

**Tasks**
- Configure **vector store** (pgvector) with metadata filtering (source, category, occasion, price band, segment, **platform**).
- Configure **document/metadata store** for raw + processed docs and lineage.
- Configure **analytical store** tables for aggregates powering the dashboard, including **competitive aggregate** tables.
- Implement retrieval primitives (top-k similarity + metadata filters, including platform).

**Deliverables**
- Query-able vector store; documented retrieval API; analytical tables ready to populate (incl. competitive views).

**Exit criteria**
- Given a query embedding + filters (including platform), the system returns relevant chunks with metadata.

**Dependencies:** Phase 1.

---

## Phase 3 — Semantic Analytics Layer

**Objective:** Convert enriched chunks into structured, confidence-scored insight — including competitive wishlist analysis for the AI engine.

**Tasks**
- Implement **taxonomy classification** into non-conversion reason categories (`context.md` §8), including competitive/platform preference.
- Implement **clustering** for emerging themes / unmet needs.
- Implement **intent detection** (active shortlist vs passive bookmarking).
- Implement **journey-stage mapping** and **segment tagging**.
- Implement **platform tagging** (normalize mentions to myntra / nykaa / ajio / other).
- Implement **wishlist-motive classification** (`context.md` §8.1).
- Implement **competitive comparison aggregation**: motive × platform, barrier × platform, shared vs unique themes → `CompetitiveAggregate` records.
- Implement **confidence scoring** (evidence volume + source reliability + agreement + platform-attribution confidence).
- Write structured `Insight` records + aggregates (including competitive) to the analytical store.

**Deliverables**
- Populated `Insight` and `CompetitiveAggregate` records and dashboard-ready aggregates with confidence indicators.

**Exit criteria**
- Every insight is categorized, tagged (incl. platform where applicable), linked to evidence chunks, and confidence-scored; competitive aggregates are queryable.

**Dependencies:** Phase 2.

---

## Phase 4 — Grounded RAG Assistant

**Objective:** Answer business and competitive questions using only retrieved evidence, with citations.

**Tasks**
- Build the **RAG Orchestrator**: query understanding → retrieve → rerank → assemble grounded context → generate.
- Add query understanding for **competitive intents** (e.g. “why wishlist on Myntra vs Nykaa/Ajio”) and platform entity extraction.
- Inject relevant **reason aggregates and competitive aggregates** as additional grounded context.
- Enforce **guardrails**: refuse/flag when evidence is insufficient; require citations; no speculation; no invented competitor metrics.
- Produce `AnswerTrace` records (retrieved chunks, platforms in scope, citations, confidence, limitations).
- Expose assistant endpoints via the API layer.
- Seed/eval against competitive questions in `context.md` §9 (items 10–12).

**Deliverables**
- Working assistant answering the key questions in `context.md` §9 (including competitive) with sources + confidence.

**Exit criteria**
- Answers are grounded (cite retrieved excerpts), competitive claims show platform-tagged evidence, and low-evidence questions are handled honestly.

**Dependencies:** Phase 3.

---

## Phase 5 — Insight Dashboard + Ask AI (Single Page)

**Objective:** Give teams a visual, filterable view of non-conversion insight and competitive wishlist comparison **on the same page as Ask AI** (suggested questions + grounded chat).

**Tasks**
- Build **Insights API** endpoints: ranked reasons, segment/category comparisons, heatmaps, trends, evidence summaries, plus **competitive comparison** (motives/barriers by platform; shared vs unique).
- Build React dashboard: charts, uncertainty/friction heatmaps, intent-type views, filters (category, occasion, price band, segment, **platform**).
- Add a **Competitive Analysis** view: Myntra vs Nykaa vs Ajio (and other) wishlist motive/barrier charts with evidence drill-down.
- **Embed Ask AI on the same page** as the dashboard (docked panel): suggested starter questions + grounded chat with citations — not a separate route/tab as the primary UX.
- Add **drill-down** to source excerpts and **confidence/evidence-volume** indicators.
- On narrow viewports, Ask AI may collapse to a drawer/FAB while remaining part of the same page experience.

**Deliverables**
- Interactive **unified page** covering `context.md` §10.1 outputs, including competitive views and Ask AI.

**Exit criteria**
- A PM can filter, compare segments and platforms, view heatmaps and competitive charts, ask suggested/custom AI questions, and drill down to evidence — **all without leaving the page**.

**Dependencies:** Phase 3 (data) and ideally Phase 4 (assistant backend).

---

## Phase 6 — Evaluation & Hardening

**Objective:** Make the system trustworthy and observable.

**Tasks**
- Define and measure **retrieval relevance**, **grounding faithfulness** (no hallucination), and **taxonomy classification quality**.
- Add eval cases for **competitive claim faithfulness** (platform attribution accuracy; no invented competitor stats).
- Add **observability**: log RAG traces, pipeline run metrics, error tracking.
- Tune reranking, prompts, chunking, and confidence thresholds based on eval results.
- Add cost controls: embedding cache, batch enrichment, retrieval caching.

**Deliverables**
- Evaluation report + dashboards for quality/cost; tuned guardrails and thresholds (incl. competitive).

**Exit criteria**
- Grounding faithfulness and retrieval relevance meet agreed targets; competitive answers remain evidence-bound; traces are auditable.

**Dependencies:** Phases 4–5.

---

## Phase 7 — Corpus Scale-Out

**Objective:** Broaden coverage to all Phase 1 sources (and competitor-aware connectors) with fresh data.

**Tasks**
- Add remaining connectors: YouTube comments, product reviews, social conversations, primary research inputs.
- Ingest **dual research Excel workbooks** (`Myntra Wishlist.xlsx` + `Your Wishlist Habits (Responses).xlsx`) with normalized age segments `age_18_24` and `age_25_35`.
- Prefer survey `age_band` metadata over behavioral segment heuristics during enrichment.
- Add / expand **competitor app connectors** (e.g. Nykaa, Ajio Play Store reviews) where publicly available and in-scope.
- Enable **incremental refresh** scheduling per source.
- Validate dedupe/quality across sources; recompute aggregates, competitive views, and confidence.
- Optionally begin migration path from pgvector to a dedicated vector DB if volume demands.

**Deliverables**
- Full multi-source, multi-platform corpus with scheduled refresh; updated dashboard + assistant coverage.
- Age-cohort comparisons (18–24 vs 25–35) available in segment filters and suggested Ask AI questions.

**Exit criteria**
- All six source types flow through the pipeline and appear in insights with source-level evidence; competitive views have sufficient platform-tagged evidence for directional claims.

**Dependencies:** Phase 6.

---

## Phase 8 — Extensibility (Future / Beyond Phase 1)

**Objective:** Prepare for internal data and ground-truth metrics (per `Architecture.md` §8).

**Tasks**
- Add connectors for Myntra event/funnel/behavioral data into the analytical store.
- Compute **actual wishlist-to-purchase 30-day conversion**; join with public-evidence reasons.
- Expand competitor coverage and refine motive/platform taxonomies as needed.
- Add a **PM feedback loop** to validate/flag insights (including competitive claims) and refine taxonomy + confidence.
- Scale-out: dedicated vector DB + warehouse; move toward streaming ingestion.

**Deliverables**
- Internal-data-aware insights and a measured target metric; richer competitive corpus.

**Exit criteria**
- Public-evidence reasons are corroborated against observed conversion behavior.

**Dependencies:** Phases 1–7; internal data access.

---

## Dependency Flow

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 ─┬─→ Phase 4 ─┐
                                       └─→ Phase 5 ─┴─→ Phase 6 → Phase 7 → Phase 8
```

Phase 4 (assistant) and Phase 5 (dashboard) both depend on Phase 3 and can proceed in parallel once the semantic layer is ready; both feed into Phase 6 hardening.

---

## Milestones

| Milestone | Achieved after | Signals |
| --- | --- | --- |
| **M1 — End-to-end thin slice** | Phase 4 | One question answered with cited evidence from a small corpus |
| **M2 — Usable insight product** | Phase 5 | Unified page: dashboard + Ask AI usable by a PM (incl. basic competitive view) on the sample corpus |
| **M3 — Trustworthy system** | Phase 6 | Meets grounding/retrieval quality targets; competitive claims stay evidence-bound; observable |
| **M4 — Full Phase 1 corpus** | Phase 7 | All six sources live with refresh; competitor-aware coverage sufficient for directional comparisons |
| **M5 — Internal-data ready** | Phase 8 | Ground-truth metric + validated reasons |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Public data is noisy/biased | Misleading insights | Confidence scoring, dedupe, source reliability weighting |
| Sparse multi-platform mentions | Weak competitive views | Competitor connectors in Phase 7; clear coverage limitations in UI/assistant |
| Mis-attributed platform tags | Wrong competitive conclusions | Platform-attribution confidence; human review samples; eval cases |
| Assistant hallucination | Loss of trust | Strict grounding guardrails, citation enforcement, eval on faithfulness |
| Invented competitor metrics | Loss of credibility | Explicit guardrail: no private competitor stats; cite platform-tagged evidence only |
| Taxonomy drift/instability | Inconsistent categorization | Derive from corpus, review, version the taxonomy (incl. motives) |
| Segment inference without internal data | Weak segmentation | Prefer explicit survey age bands (`age_18_24` / `age_25_35`); treat behavioral segments as directional |
| Cost of embeddings/LLM | Budget overrun | Caching, batching, model selection per Architecture §6 |
| Scope creep in Phase 1 | Delivery risk | Thin vertical slice first; defer breadth to Phase 7 |

---

## Cross-Requirement Traceability

| Requirement (context.md) | Delivered in |
| --- | --- |
| Ranked non-conversion reasons | Phase 3 + Phase 5 |
| Segment/category comparisons | Phase 3 (tagging) + Phase 5 (UI) |
| Intent-type views | Phase 3 + Phase 5 |
| Competitive wishlist comparison (Myntra vs Nykaa/Ajio) | Phase 3 (platform/motive + aggregates) + Phases 4–5 |
| Shared vs platform-specific themes | Phase 3 + Phase 5 |
| Unified single-page Dashboard + Ask AI | Phase 5 |
| Evidence-backed grounded answers | Phase 4 |
| Confidence & source limitations | Phase 3 (scoring) + Phases 4/5 (surfacing) |
| Full multi-source / competitor-aware corpus | Phase 7 |
| Internal-data integration + target metric | Phase 8 |

---

## Summary

The plan builds the engine as a **dependency-ordered sequence**: foundations and a thin ingestion slice first (with early platform awareness), then storage, then the semantic analytics core — including **platform tagging, wishlist-motive classification, and competitive aggregates** — followed by the two user experiences (assistant and dashboard) in parallel with competitive Q&A and views, then hardening, corpus/competitor scale-out, and finally extensibility toward internal data and the ground-truth conversion metric. Each phase yields a usable, evidence-grounded increment aligned with the architecture and the competitive analysis capability of the AI-powered engine.
