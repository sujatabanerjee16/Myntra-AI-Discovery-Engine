# System Architecture: AI-Powered Wishlist Conversion Discovery Engine

> This document defines the technical architecture for the system described in [`ProblemStatement.md`](./ProblemStatement.md) and [`context.md`](./context.md). It translates the product/insight goals into concrete components, data flows, data models, and technology choices.

---

## 1. Architectural Goals

The architecture must be:

- **Evidence-grounded** — every insight and answer traces back to source excerpts.
- **Explainable** — confidence and source limitations are first-class, not afterthoughts.
- **Competitively aware** — platform tagging and wishlist-motive comparison (Myntra vs Nykaa, Ajio, etc.) are first-class in the AI engine.
- **Modular** — corpus, analytics, and serving layers evolve independently.
- **Extensible** — designed to later ingest internal event/funnel/behavioral data.
- **Reproducible** — pipelines are versioned so results can be re-derived.
- **Lightweight (Phase 1)** — favors managed services and simple, composable parts over heavy infra.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                                │
│                                                                                │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │              Unified single-page Presentation                       │  │
│   │  Dashboard · Competitive Analysis · Discovery Chat (three tabs)     │  │
│   │  Scrape strip + Opportunity Matrix + cited chat                    │  │
│   └───────────▲────────────────────────────────▲───────────────────────┘  │
└──────────────┼────────────────────────────────┼──────────────────────────┘
               │ REST/GraphQL                    │ REST / streaming
┌──────────────┼────────────────────────────────┼──────────────────────────┐
│              │                 APPLICATION / API LAYER │                   │
│   ┌──────────┴───────────┐                   ┌───────────┴───────────────┐│
│   │  Insights API         │                   │   RAG Orchestrator        ││
│   │  (aggregations,        │                   │  (retrieve → rerank →     ││
│   │   metrics, filters,    │                   │   ground → generate;      ││
│   │   competitive views)   │                   │   platform-aware context) ││
│   └──────────▲───────────┘                   └───────────▲───────────────┘│
└──────────────┼──────────────────────────────────────────┼────────────────┘
               │                                          │
┌──────────────┼──────────────────────────────────────────┼────────────────────┐
│              │           SEMANTIC ANALYTICS LAYER        │                     │
│   ┌──────────┴──────────────────────────────────────────┴──────────────┐     │
│   │  Taxonomy classification · clustering · intent detection ·          │     │
│   │  journey-stage mapping · segment tagging · platform tagging ·       │     │
│   │  wishlist-motive classification · competitive comparison ·          │     │
│   │  confidence scoring                                                 │     │
│   └───────────────────────────────▲────────────────────────────────────┘     │
└───────────────────────────────────┼──────────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼──────────────────────────────────────────┐
│                            DATA / STORAGE LAYER                                │
│   ┌───────────────┐  ┌────────────────────┐  ┌───────────────────────────┐    │
│   │ Vector Store   │  │ Analytical Store    │  │ Document / Metadata Store │    │
│   │ (embeddings)   │  │ (aggregates, facts, │  │ (raw + processed docs)    │    │
│   │                │  │  competitive views) │  │                           │    │
│   └───────▲───────┘  └─────────▲──────────┘  └────────────▲──────────────┘    │
└──────────┼───────────────────┼───────────────────────────┼───────────────────┘
           │                   │                           │
┌──────────┴───────────────────┴───────────────────────────┴───────────────────┐
│                            INGESTION PIPELINE                                  │
│  collect → clean/normalize → PII scrub → dedupe → chunk → embed → enrich       │
│  Sources: Play Store (Myntra + competitors) · Reddit · YouTube · reviews ·     │
│  social · research · multi-platform comparison conversations                   │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 Ingestion Pipeline

Responsible for turning raw, heterogeneous public feedback into clean, structured, embeddable records.

**Stages:**

1. **Collection** — connectors per source (Play Store reviews for Myntra and relevant competitor apps, Reddit, YouTube comments, product reviews, social, research inputs). Each connector normalizes into a common raw schema. Prefer collecting conversations that mention wishlist behavior and/or multi-platform comparison.
2. **Cleaning & normalization** — strip markup, normalize unicode/emojis, language detection, optional translation to English.
3. **PII scrubbing** — remove usernames, emails, phone numbers, handles; keep content directional and privacy-safe.
4. **Deduplication** — near-duplicate detection (hashing + embedding similarity) to avoid over-counting.
5. **Chunking** — split long content into retrieval-friendly units while preserving source metadata.
6. **Embedding** — generate vector embeddings per chunk using the **BGE** model.
7. **Enrichment** — attach metadata: source, timestamp, inferred category/occasion/price band, language, quality score, **platform tags** (Myntra, Nykaa, Ajio, other), and preliminary competitive-mention flags.

**Design notes:** pipeline is **idempotent** and **incremental** (re-runnable per source), with each run versioned for reproducibility. Competitor app connectors are optional but recommended so the competitive lens is not limited to incidental mentions in Myntra-only sources.

### 3.2 Data / Storage Layer

| Store | Purpose | Example tech |
| --- | --- | --- |
| **Document/Metadata store** | Raw + processed docs, provenance, chunk lineage | PostgreSQL / MongoDB / object storage |
| **Vector store** | Embeddings + metadata for semantic retrieval | pgvector, Qdrant, Weaviate, Pinecone, or Chroma |
| **Analytical store** | Pre-computed aggregates powering the dashboard | PostgreSQL / DuckDB / warehouse |

> Phase 1 can consolidate on **PostgreSQL + pgvector** to keep infra lightweight; split out a dedicated vector DB later if scale demands.

### 3.3 Semantic Analytics Layer

Transforms enriched chunks into structured insight. Runs as batch/offline jobs and exposes results to the analytical store.

- **Taxonomy classification** — assign each item to non-conversion reason categories (see `context.md` §8).
- **Clustering** — unsupervised grouping of related behaviors/unmet needs to discover emerging themes.
- **Intent detection** — classify **active shortlist** vs **passive bookmarking**.
- **Journey-stage mapping** — map conversations to stages in the wishlist→purchase journey.
- **Segment tagging** — infer category, occasion, price band, and behavioral tags (price / fit / quality). Primary research surveys still carry an **age band** (`age_18_24`, `age_25_35`) on chunks so RAG can use that metadata. The **dashboard does not** expose Age 18–24 vs 25–35 cards or filters — those visuals mixed a 42-person Google Form with 1,217 scrapes.
- **Platform tagging** — detect and normalize platform mentions: `myntra`, `nykaa`, `ajio`, `other` (configurable list).
- **Wishlist-motive classification** — label *why* users wishlist on a platform (see `context.md` §8.1: assortment, price/sale waiting, brand/exclusive, category strength, trust, UX, social/inspiration).
- **Competitive comparison aggregation** — build shared vs platform-specific motive/barrier distributions and evidence-backed competitive insight records.
- **Confidence scoring** — combine evidence volume, source reliability, inter-source agreement, and **platform-attribution confidence** into a confidence indicator per insight.

### 3.4 Application / API Layer

Two backend services (can share a codebase/monorepo):

- **Insights API** — serves dashboard queries: ranked reasons, segment/category comparisons, heatmaps, trends, evidence summaries with confidence, and **competitive wishlist comparison** endpoints (motives/barriers by platform; shared vs unique themes). Mostly reads from the analytical store.
- **RAG Orchestrator** — powers Discovery Chat using a **retrieve → rerank → ground → generate** flow (see §4.2). Understands competitive intents (e.g. “Myntra vs Nykaa wishlist motives”), injects competitive aggregates, and enforces grounding: no answer without retrieved evidence. Every in-scope answer shows **public source chips** (Play Store / Reddit / YouTube / reviews / social) and a **Confidence: N%** badge. Survey/interview lines may inform the answer but do not appear as evidence chips.

### 3.5 Presentation Layer

- **Unified single page, three tabs** — **Dashboard**, **Competitive Analysis**, and **Discovery Chat** share one app so a PM can rank, compare, then ask without leaving the product.
- **Dashboard** — scrape strip (**1,217 shopper comments**: Play Store, Reddit, YouTube, reviews, social), Opportunity Matrix (volume + confidence, filterable by category / source / min-confidence slider), shopper-comment examples, and internal PM calibration. **No Google Form tile. No age-board.** Survey vs scrape never share a KPI.
- **Competitive Analysis** — Myntra vs Nykaa vs Ajio motives and barriers from platform mentions.
- **Discovery Chat** — starter questions + grounded answers. Every in-scope bubble shows the same footer: platform chips + `Confidence: N%`. Evidence drawer lists public comments only.

---

## 4. Key Data Flows

### 4.1 Ingestion → Insight (offline/batch)

```
raw feedback → clean → scrub PII → dedupe → chunk → embed
        → classify (taxonomy) → cluster → detect intent → map journey
        → tag segments → tag platforms → classify wishlist motives
        → aggregate competitive comparisons → score confidence
        → write aggregates + vectors
```

Output: populated **vector store** (for retrieval) and **analytical store** (for dashboard + competitive views).

### 4.2 Question → Grounded Answer (online/RAG)

```
user question
   → query understanding (intent + filters + platform/competitor entities)
   → retrieve top-k chunks from vector store (+ metadata filters, incl. platform)
   → rerank for relevance
   → assemble grounded context (chunks + reason aggregates + competitive aggregates)
   → Groq-hosted LLM (or template fallback) generates answer constrained to retrieved evidence
   → attach public citations + Confidence: N%  (never paste confidence/volume into the prose)
   → return to user
```

**Guardrails:**
- If retrieval yields insufficient evidence, the assistant says so in plain English rather than speculating.
- Answers must cite retrieved excerpts; unsupported claims are disallowed.
- Competitive claims must not invent private competitor metrics; they must cite platform-tagged evidence.
- Aggregated dashboard facts (including competitive aggregates) can be injected as additional grounded context.
- Research/interview Q&A may ground the answer; it must not appear in Show evidence or as a dashboard KPI.

### 4.3 Dashboard query flow (online)

```
user selects category / scrape-source / min-confidence
   → Insights API (or dashboard-bootstrap.json snapshot)
   → Opportunity Matrix + scrape strip + competitive views
   → render
```

Age-band filters are **not** on this path. Confidence slider filters matrix rows client-side and refetches ranked reasons.

### 4.4 Competitive analysis flow (AI engine)

```
platform-tagged chunks + motive/barrier labels
   → competitive aggregates (motive × platform, barrier × platform)
   → shared vs unique theme detection
   → Insights API competitive endpoints + RAG competitive context
   → dashboard competitive views / assistant competitive answers
```

---

## 5. Core Data Models (Conceptual)

### 5.1 `Document` (raw source record)

| Field | Description |
| --- | --- |
| `id` | Unique document id |
| `source` | play_store \| reddit \| youtube \| product_review \| social \| research |
| `source_app` / `source_platform` | Optional origin platform when the connector is app-specific (e.g. Myntra vs Nykaa Play Store) |
| `source_url` / `ref` | Provenance / link |
| `author_hash` | Anonymized author reference |
| `text` | Original text (post-cleaning) |
| `language` | Detected language |
| `created_at` | Original timestamp |
| `ingested_at` | Pipeline run timestamp |
| `run_version` | Pipeline version for reproducibility |

### 5.2 `Chunk` (retrieval unit)

| Field | Description |
| --- | --- |
| `id` | Chunk id |
| `document_id` | Parent document |
| `text` | Chunk text |
| `embedding` | Vector representation |
| `category`, `occasion`, `price_band`, `segment` | Inferred tags |
| `platforms` | List of tagged platforms mentioned (myntra, nykaa, ajio, other) |
| `wishlist_motives` | Motive tags (see `context.md` §8.1), when applicable |
| `quality_score` | Signal strength / reliability |
| `platform_attribution_confidence` | Confidence that platform tags are correctly attributed |

### 5.3 `Insight` (structured analysis)

| Field | Description |
| --- | --- |
| `id` | Insight id |
| `reason_category` | Taxonomy category (fit, price, trust, timing, competitive preference, …) |
| `intent_type` | active_shortlist \| passive_bookmark |
| `journey_stage` | Mapped stage |
| `segment` / `category` | Applicable segment/category |
| `platforms` | Platforms this insight applies to |
| `wishlist_motive` | Optional motive label for competitive lens |
| `comparison_scope` | myntra_only \| competitor_only \| multi_platform \| shared |
| `evidence_chunk_ids` | Supporting chunks |
| `evidence_volume` | Count of supporting items |
| `confidence` | Confidence indicator |
| `sources` | Distinct source types backing it |

### 5.4 `CompetitiveAggregate` (dashboard / RAG context)

| Field | Description |
| --- | --- |
| `platform` | myntra \| nykaa \| ajio \| other |
| `metric_type` | motive \| barrier (reason_category) |
| `label` | Motive or reason label |
| `count` / `share` | Volume and relative share |
| `evidence_volume` | Supporting item count |
| `confidence` | Aggregate confidence |
| `shared_vs_unique` | shared \| unique_to_platform |

### 5.5 `AnswerTrace` (assistant audit)

| Field | Description |
| --- | --- |
| `question` | User question |
| `retrieved_chunk_ids` | Evidence used |
| `platforms_in_scope` | Platforms the question/answer addressed |
| `answer` | Generated answer |
| `citations` | Excerpt references |
| `confidence` | Overall confidence |
| `limitations` | Internal caveat string (not shown in the chat bubble) |

---

## 5.6 Primary research (RAG only — not a dashboard tile)

Research connectors still load **two** Excel workbooks plus interviews:

| Workbook | Role |
| --- | --- |
| `Myntra Wishlist.xlsx` | Myntra-focused wishlist survey |
| `Your Wishlist Habits (Responses).xlsx` | Cross-app wishlist habits survey |

Those rows land as `source=research` with optional `age_band` metadata. They **inform Discovery Chat** when retrieved. They do **not**:

- appear on the scrape strip (that KPI is **1,217 public comments**),
- share a number with Play Store / Reddit counts,
- drive Age 18–24 vs 25–35 cards or a segment dropdown,
- show up as interview Q&A in the evidence drawer.

UI reason labels (dashboard + chat): **Research & Comparison** (taxonomy `external_comparison`), **Proof / Photos** (taxonomy `review_trust`).

---

## 6. Technology Choices (Phase 1 Recommendation)

> These are pragmatic defaults for a lightweight Phase 1; swap per team preference (see open questions in `context.md` §13).

| Concern | Recommendation | Rationale |
| --- | --- | --- |
| Language/runtime | Python | Rich data/ML ecosystem |
| Ingestion | Python scripts / Prefect or simple schedulers | Incremental, versioned runs |
| Embeddings | BGE model (BAAI open-source, e.g. `bge-large-en` / `bge-base-en`) | High-quality open-source embeddings, self-hostable, no per-token cost |
| Vector store | PostgreSQL + pgvector | One DB for vectors + metadata (incl. platform filters) in Phase 1 |
| Analytical store | PostgreSQL (or DuckDB for local) | Simple aggregations |
| RAG orchestration | LangChain / LlamaIndex or custom | Retrieval + grounding scaffolding |
| LLM | Groq (hosted, e.g. Llama-family models) with JSON/structured output | Fast, low-latency grounded generation with citations |
| Backend API | FastAPI | Async, typed, quick to build |
| Dashboard frontend | React + charting lib (Recharts/ECharts) | Interactive visual analytics |
| Chat frontend | React **Discovery Chat** tab on the same app | Starter questions + chips + Confidence: N% |

---

## 7. Cross-Cutting Concerns

- **Explainability & confidence** — surfaced everywhere: dashboard indicators + assistant caveats.
- **Provenance/lineage** — chunk → document → source is always traceable.
- **Privacy** — PII scrubbed at ingestion; only directional, anonymized content stored.
- **Reproducibility** — versioned pipeline runs; insights link to run version.
- **Evaluation** — track retrieval relevance, grounding faithfulness (no hallucination), and taxonomy classification quality.
- **Observability** — log RAG traces (`AnswerTrace`) for audit and quality review.
- **Cost control** — cache embeddings; batch offline enrichment; reuse retrieval results.

---

## 8. Extensibility Roadmap (Beyond Phase 1)

The architecture is deliberately staged so it can grow without redesign:

1. **Internal data integration** — add connectors for Myntra event/funnel/behavioral data into the same analytical store; join public-evidence reasons with observed conversion.
2. **Ground-truth metric** — compute actual wishlist-to-purchase 30-day conversion once internal data is available.
3. **Competitive corpus expansion** — add more competitor apps/marketplaces and refine platform/motive taxonomies as coverage grows.
4. **Feedback loop** — let PMs validate/flag insights (including competitive claims) to refine the taxonomy and confidence scoring.
5. **Scale-out** — migrate from pgvector to a dedicated vector DB and a warehouse if volume grows.
6. **Real-time refresh** — move from batch to streaming ingestion for fresher emerging-theme detection.

---

## 9. Component-to-Requirement Traceability

| Product requirement (context.md) | Architectural component |
| --- | --- |
| Ranked non-conversion reasons | Semantic layer (taxonomy) → analytical store → Insights API → dashboard |
| Category / source / confidence filters | Insights API + client-side confidence slider → Opportunity Matrix |
| Intent-type views | Intent detection → Insight model → dashboard |
| Competitive wishlist comparison (Myntra vs Nykaa/Ajio) | Platform tagging + motive classification → CompetitiveAggregate → Insights API + RAG |
| Shared vs platform-specific themes | Competitive comparison aggregation → Competitive tab + chat |
| Evidence-backed answers | RAG Orchestrator + public citation chips + Confidence: N% |
| Confidence on every answer | `compute_answer_confidence` → chat footer badge (not inline decimals) |
| Future internal-data integration | Extensible ingestion + analytical store (roadmap §8) |

---

## 10. Summary

The system is a **layered, evidence-grounded architecture**: an incremental **ingestion pipeline** feeds a **document/vector/analytical storage layer**, a **semantic analytics layer** structures feedback into a reason taxonomy with platform tags, wishlist motives, and confidence, and two serving paths — an **Insights API** and a **RAG Orchestrator** — power a **three-tab** app: scrape-only **Dashboard**, **Competitive Analysis**, and **Discovery Chat** (public chips + Confidence %). Research stays in the corpus for grounding; it is never mixed into the 1,217-comment scrape KPI. Every layer is modular so Phase 1 can later add internal behavioral data without redesign.
