# Project Context: AI-Powered Wishlist Conversion Discovery Engine

> This document expands on [`ProblemStatement.md`](./ProblemStatement.md) and serves as the shared context for anyone (engineers, PMs, researchers, or AI agents) working on this project. It clarifies the domain, goals, architecture, data, and terminology so decisions can be made consistently.

---

## 1. Context at a Glance

| Aspect | Summary |
| --- | --- |
| **Company** | Myntra (online fashion & lifestyle e-commerce) |
| **Domain** | Fashion e-commerce, user behavior analytics, product discovery, competitive insight |
| **Core question** | Why do users wishlist fashion products but fail to purchase within 30 days? |
| **Competitive question** | Why do people wishlist on Myntra vs competitors (Nykaa, Ajio, etc.)? |
| **Target metric** | Wishlist-to-purchase conversion within 30 days (+ directional competitive motive/barrier comparison) |
| **Deliverables** | **Unified single page:** Insight Dashboard + Ask AI (suggested questions + grounded chat), incl. competitive views |
| **Primary users** | Growth PMs, User Research/Insights/Analytics, competitive/category strategy, business stakeholders |
| **Data phase 1** | Public conversations + approved research inputs (no internal behavioral data yet); multi-platform mentions tagged |
| **Guiding principle** | Evidence-backed, explainable insights — not generic summaries or raw sentiment |
| **UX principle** | Dashboard charts and Ask AI live on **one page** so users explore visually and conversationally without context-switching |

---

## 2. Problem Framing

### 2.1 The business problem

A **wishlist** is a strong but incomplete signal of purchase intent. When a user wishlists a product, they have already discovered it and found it relevant enough to shortlist. Yet a large share of wishlisted items never convert to purchase.

Users also wishlist across **multiple fashion/lifestyle platforms**. Motives for saving on Myntra may differ from Nykaa (e.g. beauty/brand discovery), Ajio (e.g. price/value, private labels), or others. Competitive wishlist analysis clarifies where Myntra wins or loses the “save for later” moment.

The project exists to answer:

> Among users who add fashion products to their wishlist, what share purchase at least one wishlisted item within 30 days — and what most plausibly explains non-conversion for the rest?

And, competitively:

> Why do people add items to their wishlist on Myntra versus competitors such as Nykaa and Ajio — which motives and barriers are shared, and which are platform-specific?

### 2.2 Why this is hard

- A wishlist mixes **high-intent shortlisting** with **casual/passive bookmarking**; treating both the same distorts conclusions.
- Non-conversion is driven by **many overlapping frictions** (fit, sizing, price, trust, timing, styling doubt, external comparison).
- Competitive signals are **noisy**: users may mention multiple apps in one conversation; platform attribution is inferred, not observed in private analytics.
- Phase 1 relies on **public/directional evidence**, not ground-truth internal funnel data, so conclusions must carry **confidence and source caveats**.

### 2.3 What "good" looks like

The system should turn scattered feedback into **structured, PM-usable opportunity areas**, each backed by evidence and a confidence indicator, and explorable both visually (dashboard) and conversationally (grounded assistant) — including **side-by-side competitive wishlist motive/barrier views**.

---

## 3. Goals and Non-Goals

### 3.1 Goals

- Identify and rank recurring **non-conversion reasons**.
- Distinguish **purchase-intent wishlisting** from **passive bookmarking**.
- Compare patterns across **categories, occasions, price bands, intent types, and user segments**.
- Compare **wishlist motives and barriers for Myntra vs competitors** (Nykaa, Ajio, and other tagged platforms).
- Surface **shared vs platform-specific** themes that inform differentiation and conversion work.
- Surface the **most plausible opportunity areas** tied to the 30-day conversion metric.
- Provide **evidence-backed, explainable** outputs via a dashboard and a grounded assistant.

### 3.2 Non-Goals (for this phase)

- Direct integration with Myntra internal behavioral/funnel/event data.
- Access to competitors’ private analytics or claimed conversion rates as fact.
- Treating public feedback as absolute ground truth.
- Free-form speculation or unsupported claims from the assistant.
- Generic review summarization, plain sentiment scoring, or anecdote-driven conclusions.

---

## 4. Target Users & Their Jobs-to-be-Done

| User | Primary jobs | What they need from the system |
| --- | --- | --- |
| **Growth Product Manager** | Improve wishlist→purchase conversion | Ranked reasons, opportunity areas, segment & competitive comparisons, confidence signals |
| **User Research / Insights** | Understand user frictions & unmet needs | Evidence excerpts, thematic clusters, drill-downs, source transparency |
| **Analytics teams** | Quantify and monitor patterns over time | Reason distributions, heatmaps, trend/emerging-theme views, platform splits |
| **Competitive / category strategy** | Position Myntra vs peers on wishlist motives | Shared vs unique motives, competitor-attributed barriers, cited evidence |
| **Product/business stakeholders** | Make investment decisions | Concise, credible, PM-usable synthesis with caveats |

---

## 5. Target Metric (Definition)

**Wishlist-to-purchase conversion within 30 days** = share of users who, after adding one or more fashion products to their wishlist, purchase at least one of those wishlisted items within a 30-day window.

- The metric anchors *what counts as success*; the discovery engine explains *why non-conversion happens* for the remaining share.
- Note: in Phase 1 this metric is the **conceptual anchor**, since exact conversion rates require internal data. The engine focuses on the *reasons* behind non-conversion using public evidence.
- **Competitive lens (Phase 1):** directional comparison of wishlist *motives* and *barriers* attributed to Myntra vs named competitors in public evidence — not a claimed competitor conversion rate.

---

## 6. Solution Architecture (Hybrid Insight Architecture)

The system is composed of cooperating layers plus a **unified single-page** user experience (dashboard + Ask AI).

```
                 ┌──────────────────────────────────────────────────────────┐
                 │         Unified single-page user experience               │
                 │   Insight Dashboard  +  Ask AI (suggested Qs + chat)      │
                 └───────────────▲───────────────────────▲──────────────────┘
                                 │                       │
        ┌────────────────────────┴───────────────────────┴────────────────────┐
        │                 Semantic Analytics Layer                             │
        │  reason taxonomy · clustering · intent classification ·              │
        │  journey-stage mapping · segment comparison ·                        │
        │  platform tagging · competitive motive/barrier comparison            │
        └────────────────────────▲─────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┴─────────────────────────────────────────────┐
        │                   Discovery Corpus                                   │
        │  app reviews · Reddit · YouTube · product reviews ·                  │
        │  social conversations · primary research inputs ·                    │
        │  multi-platform / competitor-mention conversations                   │
        └──────────────────────────────────────────────────────────────────────┘
```

### 6.1 Dashboard Layer (+ Ask AI on the same page)

Surfaces quantified, comparable insight **and** Ask AI on one page:

- top reasons for wishlist non-conversion
- variation by category, occasion, price band, intent type, user segment
- recurring uncertainties: fit, quality, styling, price sensitivity, trust, timing
- **competitive wishlist comparison** (Myntra vs Nykaa, Ajio, etc.)
- **shared vs platform-specific** motive and barrier themes
- evidence strength / confidence by source and by platform (when tagged)
- emerging themes and opportunity areas over time
- **Ask AI panel** — suggested starter questions + grounded chat, docked on the same page as the charts (not a separate route)

### 6.2 Semantic Analytics Layer

Transforms raw feedback into structured intelligence:

- organizes feedback into a **reason taxonomy**
- clusters related behaviors and unmet needs
- distinguishes **high-intent wishlisting** vs **casual bookmarking**
- maps conversations to **stages in the wishlist→purchase journey**
- **tags platforms** mentioned (Myntra, Nykaa, Ajio, …) and classifies **wishlist motives** per platform
- supports comparative analysis across segments, contexts, **and competitors**

### 6.3 Grounded RAG Assistant (Ask AI)

Answers questions with retrieved evidence, embedded in the dashboard page:

- answers predefined and ad hoc business **and competitive** questions
- shows **suggested Ask AI questions** next to dashboard insights
- retrieves relevant evidence from the curated corpus (including multi-platform mentions)
- synthesizes findings from the dashboard + semantic layer
- gives transparent, explainable answers **with source references**
- avoids unsupported claims / free-form speculation
- stays on the **same page** as the dashboard so users do not leave their analytics context

### 6.4 Competitive Analysis (AI engine capability)

A first-class capability of the engine, not a separate product:

| Capability | What it does |
| --- | --- |
| **Platform tagging** | Detects mentions of Myntra, Nykaa, Ajio, and other configured competitors in corpus text |
| **Wishlist motive classification** | Labels *why* users save/wishlist on a given platform (assortment, price/sale waiting, brand exclusives, beauty vs apparel focus, trust, UX, etc.) |
| **Barrier comparison** | Aligns non-conversion / hesitation reasons across platforms using the shared taxonomy |
| **Shared vs unique themes** | Surfaces motives/barriers that appear across platforms vs those concentrated on one |
| **Evidence-backed competitive answers** | RAG + aggregates answer “Myntra vs Nykaa/Ajio” questions with citations and confidence |

Default Phase 1 competitor set (configurable): **Nykaa**, **Ajio**, plus an **Other / unspecified** bucket. Expand as corpus coverage grows.
---

## 7. Data & Discovery Corpus

### 7.1 Sources (Phase 1)

- Google Play Store reviews (Myntra and, where relevant, competitor apps)
- Reddit posts and comments
- YouTube comments
- Product reviews
- Social conversations
- Primary user research inputs
- Conversations that explicitly compare or mention multiple fashion/lifestyle platforms

### 7.2 Priority signals to capture

- wishlist usage patterns
- purchase hesitation
- delayed decision-making
- fit, size, styling, quality, review trust, occasion-based uncertainty
- price sensitivity and waiting behavior (e.g., waiting for sale/discount)
- external information seeking and product comparison behavior
- **multi-platform wishlist habits** and **why save here vs elsewhere**
- **platform-attributed motives** (assortment, exclusives, price discovery, category strength, UX, trust)

### 7.3 Data handling principles

- Public feedback is **directional evidence**, not absolute truth.
- Competitor comparisons are inferred from **public mentions**, not from competitors’ private data.
- Architecture must be **extensible** to later incorporate internal event data, funnel metrics, and behavioral signals.
- Every insight should be traceable back to **source excerpts**, including platform attribution where claimed.

---

## 8. Reason Taxonomy (Working Model)

A structured taxonomy is central to the semantic layer. A suggested starting set of non-conversion reason categories (to be refined from the corpus):

| Category | Example signals |
| --- | --- |
| **Fit & Sizing uncertainty** | unsure of size, inconsistent sizing across brands, fear of wrong fit |
| **Price sensitivity / waiting** | waiting for sale, price too high, expecting a discount, comparing prices |
| **Quality & trust doubt** | worried about material/quality, distrust of product photos or reviews |
| **Styling / decision uncertainty** | unsure how to style, indecisive between options, needs validation |
| **Review trust** | too few reviews, conflicting reviews, suspected fake reviews |
| **Timing / occasion** | saving for a future occasion, not needed yet, seasonal timing |
| **External comparison** | checking other apps/sites, seeking opinions outside Myntra |
| **Passive bookmarking** | saving for inspiration, no real intent to buy soon |
| **Logistics / friction** | delivery time, return policy concerns, payment friction |
| **Competitive / platform preference** | preferring another app for wishlist; switching platforms for price, assortment, or category |

> Each item should also carry **intent type** (active shortlist vs passive bookmark), **journey stage**, **segment/category tags**, **platform tags** (Myntra / Nykaa / Ajio / other), optional **wishlist motive** label, and a **confidence/evidence-strength** score.

### 8.1 Wishlist motive tags (competitive lens)

Working set of motive labels used when classifying *why* users wishlist on a platform (orthogonal to non-conversion reasons):

| Motive tag | Example signals |
| --- | --- |
| **Assortment / discovery** | wide catalog, browsing, finding options to save |
| **Price / sale waiting** | save now, buy on discount; price tracking |
| **Brand / exclusive** | brand presence, exclusives, limited drops |
| **Category strength** | “Nykaa for beauty”, “Myntra for apparel”, etc. |
| **Trust / quality** | confidence in returns, authenticity, reviews |
| **UX / convenience** | easier to browse/save; app habit |
| **Social / inspiration** | moodboarding, trend saving, sharing |

These motive tags power **Myntra vs competitor** dashboard charts and competitive RAG answers.

---

## 9. Key Questions the Engine Must Answer

1. Why do users add fashion products to their wishlist?
2. What prevents wishlisted products from being purchased?
3. What uncertainties remain after a user identifies a product they like?
4. What causes users to postpone the purchase?
5. When is the wishlist real purchase intent vs casual bookmarking?
6. How do users compare shortlisted products?
7. What information do users seek outside Myntra before purchasing?
8. How do behaviors vary across categories, intents, and user segments?
9. What unmet needs appear repeatedly across conversations?
10. **Why do users wishlist on Myntra vs Nykaa, Ajio, or other competitors?**
11. **Which wishlist motives are shared across platforms, and which are platform-specific?**
12. **Where does Myntra appear stronger or weaker than competitors on wishlist-related frictions?**

Each should be answerable via **dashboard exploration**, **filtered evidence views** (including by platform), and **grounded chatbot responses**.

---

## 10. Key Outputs

### 10.1 Dashboard + Ask AI outputs (single page)

- ranked non-conversion reason categories
- segment and category comparisons
- uncertainty and friction heatmaps
- intent-type views ("active shortlist" vs "passive bookmarking")
- **competitive wishlist motive / barrier comparison** (Myntra vs Nykaa, Ajio, etc.)
- **shared vs platform-specific theme views**
- source-level evidence summaries
- confidence scores and evidence-volume indicators (including by platform where available)
- **Ask AI suggested questions** visible alongside dashboard charts
- inline grounded chat answers with citations (same page)

### 10.2 Chat assistant outputs (Ask AI panel)

- concise answers to stakeholder questions, including competitive questions
- evidence-backed synthesis across multiple sources and platforms
- drill-down explanations by category, segment, occasion, **or competitor**
- supporting excerpts / references from retrieved conversations
- transparent indication of source and competitive-coverage limitations
- all of the above available **without leaving the dashboard page**
---

## 11. Constraints & Principles

### 11.1 Data & sources

- Use only publicly available conversations + approved research inputs in Phase 1.
- Do not assume internal behavioral data integration yet.
- Treat public feedback as directional, not absolute.
- Competitor comparisons must not invent private competitor metrics.
- Design for future extension to internal event/funnel data.

### 11.2 Transparency & reliability

- Insights must be **evidence-backed and explainable**.
- Outputs must indicate **confidence level and source limitations**.
- Competitive claims must show **which platforms were mentioned** and attribution confidence.
- Avoid overstating conclusions from isolated anecdotes.
- The assistant must stay **grounded** in retrieved evidence and the structured insight layers.

---

## 12. Success Criteria

The discovery engine succeeds if it can:

- identify recurring reasons behind wishlist non-conversion
- distinguish purchase-intent wishlisting from passive bookmarking
- highlight the most plausible opportunity areas tied to the target metric
- compare patterns across sources, categories, and user segments
- **compare wishlist motives and barriers for Myntra vs competitors with cited evidence**
- provide a **unified single-page** dashboard + Ask AI experience (suggested questions + grounded chat alongside charts)
- generate credible, PM-usable insights rather than raw summaries

---

## 13. Assumptions & Open Questions

**Assumptions**

- Public conversations meaningfully reflect real wishlist/purchase behavior.
- A reason taxonomy can be derived and stabilized from the corpus.
- Confidence scoring can be defined from evidence volume + source reliability + agreement.
- Enough public multi-platform mentions exist to support directional competitive comparisons.

**Open questions (to resolve with stakeholders)**

- Which specific product categories/segments are highest priority for Phase 1?
- Which competitors beyond Nykaa and Ajio are in-scope for tagging?
- What defines a "user segment" without internal data (inferred from conversation context)?
- What is the minimum evidence threshold before a reason or competitive claim is shown as "confident"?
- What tech stack / models are preferred for embeddings, retrieval, and the LLM?
- What is the expected refresh cadence of the corpus and dashboard?

---

## 14. Glossary

| Term | Meaning |
| --- | --- |
| **Wishlist** | A user's saved/shortlisted set of products signalling interest |
| **Wishlist-to-purchase conversion (30d)** | Share of wishlisting users who buy ≥1 wishlisted item within 30 days |
| **Non-conversion** | Wishlisted items not purchased within the 30-day window |
| **Active shortlist** | High-intent wishlisting with real purchase consideration |
| **Passive bookmarking** | Low-intent saving (inspiration, later reference) |
| **Reason taxonomy** | Structured classification of why items don't convert |
| **Platform tag** | Inferred platform/app mentioned (Myntra, Nykaa, Ajio, other) |
| **Wishlist motive** | Why a user saves/wishlists on a given platform |
| **Competitive analysis** | Evidence-backed comparison of wishlist motives/barriers across platforms |
| **Semantic Analytics Layer** | Layer that structures, clusters, and classifies raw feedback |
| **RAG** | Retrieval-Augmented Generation; grounding answers in retrieved evidence |
| **Grounded assistant** | Chatbot that answers only from retrieved evidence + insight layers |
| **Confidence indicator** | Signal of how strongly evidence supports a given insight |
| **Opportunity area** | A friction/unmet-need cluster worth product investigation |

---

## 15. Summary

The goal is a **credible, structured, and scalable wishlist conversion insight system** for Myntra, with a built-in **competitive analysis** capability. By combining a **dashboard**, a **semantic analytics layer**, and a **grounded RAG assistant**, the system helps researchers and PMs understand *why wishlist intent often fails to convert into purchase within 30 days*, and *why users wishlist on Myntra versus competitors like Nykaa and Ajio*. It should uncover the real frictions, uncertainties, and unmet needs between product interest and purchase — and present them in a form that is **measurable, explainable, actionable, and competitively aware**.