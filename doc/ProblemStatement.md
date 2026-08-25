# AI-Powered Wishlist Conversion Discovery Engine

## Overview

This project will build an AI-powered discovery and insight engine for Myntra to understand why users add fashion products to their wishlist but do not purchase them within 30 days — and how those wishlist motives and barriers compare with competitors such as Nykaa, Ajio, and other fashion/lifestyle platforms.

The core business problem is:

> Why do users wishlist fashion products, yet fail to convert that interest into purchase within 30 days?

A closely related competitive question is:

> Why do people add items to their wishlist on Myntra versus competitors (e.g. Nykaa, Ajio) — and what does that imply for conversion and differentiation?

A wishlist is a strong but incomplete signal of intent. It indicates that a user has discovered and shortlisted products they find relevant, but many wishlisted items never move to purchase. Users also form wishlist habits across multiple platforms; understanding **platform-specific wishlist motives** (assortment, price discovery, brand exclusives, beauty vs apparel focus, sale waiting, etc.) is essential for competitive positioning.

Rather than producing generic summaries or sentiment snapshots, the system should combine:

- a **single-page** experience with a dashboard that quantifies and compares recurring non-conversion reasons **and competitive wishlist motives**, alongside **Ask AI** suggested questions and grounded chat, and
- a grounded AI assistant that answers specific business, research, and competitive questions using evidence retrieved from the underlying corpus.

The engine will analyze large-scale public and research-driven user feedback from sources such as app reviews, Reddit discussions, YouTube comments, social conversations, product reviews, and primary user research inputs — including conversations that explicitly mention **Myntra and/or competitors**. Its purpose is to surface actionable opportunity areas that may influence wishlist-to-purchase conversion and competitive differentiation.

## Objective

Design and implement a lightweight AI-powered discovery engine with two integrated experiences:

### 1. Insight Dashboard + Ask AI (single page)

A **unified single-page experience** that combines:

- the insight dashboard (charts, filters, competitive views), and
- **Ask AI** — suggested questions and the grounded chat assistant

Users should see analytics and Ask AI **on the same page** (e.g. dashboard main canvas + docked Ask AI panel), without navigating to a separate assistant route. Suggested starter questions appear inline so PMs can explore visually and conversationally in one view.

### 2. Grounded AI Assistant (Ask AI)

A chatbot powered by a semantic retrieval and reasoning layer that answers specific questions about wishlist behavior, non-conversion drivers, unmet user needs, and **competitive wishlist comparison** using evidence-backed responses — surfaced as the **Ask AI** panel on the same page as the dashboard.

Together, these should help Myntra:

- analyze user feedback at scale
- identify why users wishlist fashion items
- uncover why wishlisted items are not purchased within 30 days
- detect recurring barriers, uncertainties, and postponement triggers
- **compare wishlist motives and frictions across Myntra and competitors**
- compare patterns across categories, intents, and user segments
- generate structured, PM-usable insights instead of raw summaries



## Target Metric

**Wishlist-to-purchase conversion within 30 days**

Specifically: among users who add fashion products to their wishlist, what share go on to purchase at least one of those wishlisted items within 30 days — and what reasons most plausibly explain non-conversion for the rest?

**Competitive lens (directional, Phase 1):** relative strength of wishlist motives and barriers attributed to Myntra vs named competitors in public evidence — used to prioritize differentiation and conversion opportunities, not as a substitute for internal conversion metrics.

## Target Users

- Growth Product Managers at Myntra
- User Research, Insights, and Analytics teams
- Competitive intelligence / category strategy stakeholders
- Product and business stakeholders responsible for conversion improvement



## Product Approach

The solution should follow a hybrid insight architecture:

### 1. Dashboard Layer (+ Ask AI on one page)

The dashboard should show:

- top reasons for wishlist non-conversion
- variation by category, occasion, price band, intent type, and user segment
- recurring uncertainties such as fit, quality, styling, price sensitivity, trust, and timing
- **competitive wishlist comparison** — motive and barrier distributions for Myntra vs Nykaa, Ajio, and other tagged platforms
- evidence strength and confidence by source (and by platform where tagged)
- emerging themes and opportunity areas over time
- **Ask AI** — suggested questions and grounded chat **on the same page** as the charts (docked panel; not a separate primary route)


### 2. Semantic Analytics Layer

This layer should:

- organize raw feedback into a structured reason taxonomy
- cluster related behaviors and unmet needs
- distinguish high-intent wishlisting from casual bookmarking
- connect conversations to likely stages in the wishlist-to-purchase journey
- **tag platforms mentioned** (Myntra, Nykaa, Ajio, etc.) and classify **wishlist motives** per platform
- support comparative analysis across segments, contexts, **and competitors**



### 3. Grounded RAG Assistant

The chatbot should:

- answer predefined and ad hoc business and competitive questions
- retrieve relevant evidence from the curated corpus (including multi-platform mentions)
- synthesize findings from the dashboard and semantic layer
- provide transparent, explainable answers with supporting source references
- avoid unsupported claims or free-form speculation



## Scope of Work



### 1. Discovery Corpus Definition

Collect and analyze public and research-based conversations relevant to online fashion shopping behavior, including:

- Google Play Store reviews (Myntra and, where relevant, competitor apps)
- Reddit posts and comments
- Primary user research inputs
- Other public sources that discuss wishlist behavior across fashion/lifestyle platforms

The corpus should prioritize signals related to:

- wishlist usage
- purchase hesitation
- delayed decision-making
- fit, size, styling, quality, review trust, and occasion-based uncertainty
- price sensitivity and waiting behavior
- external information seeking and product comparison behavior
- **explicit multi-platform comparison** (e.g. “I wishlist on Myntra for X, on Nykaa for Y, on Ajio for Z”)
- **platform-attributed wishlist motives** (why save here vs elsewhere)



### 2. Discovery Engine Requirements

The engine must help answer questions such as:

- Why do users add fashion products to their wishlist?
- What prevents wishlisted products from being purchased?
- What uncertainties remain after a user has identified a product they like?
- What causes users to postpone the purchase?
- When is the wishlist used for real purchase intent versus casual bookmarking?
- How do users compare shortlisted products?
- What information do users seek outside Myntra before purchasing?
- How do these behaviors vary across categories, intents, and user segments?
- What unmet needs appear repeatedly across conversations?
- **Why do users wishlist on Myntra vs Nykaa, Ajio, or other competitors?**
- **Which wishlist motives are shared across platforms, and which are platform-specific?**
- **Where does Myntra appear stronger or weaker than competitors on wishlist-related frictions?**

These questions should be answerable through:

- dashboard exploration (including competitive comparison views)
- filtered evidence views (including by platform)
- grounded chatbot responses



### 3. Analysis Principles

The workflow should go beyond:

- generic review summarization
- simple sentiment analysis
- anecdotal observations
- single-platform echo chambers without competitive context

Instead, it should:

- identify patterns tied to the wishlist-to-purchase journey
- classify recurring non-conversion reasons into a usable taxonomy
- distinguish stronger signals from weaker or biased ones
- compare behavioral differences across meaningful user groups **and platforms**
- surface the most relevant opportunity areas for product and competitive investigation
- present all insights with evidence and confidence indicators
- treat competitor mentions as **directional public evidence**, with clear platform-attribution confidence



## Key Outputs

The system should produce:

### Dashboard Outputs

- ranked non-conversion reason categories
- segment and category comparisons
- uncertainty and friction heatmaps
- intent-type views such as “active shortlist” vs “passive bookmarking”
- **competitive wishlist motive / barrier comparison** (Myntra vs Nykaa, Ajio, etc.)
- **shared vs platform-specific theme views**
- source-level evidence summaries
- confidence scores and evidence volume indicators (including by platform where available)



### Chat Assistant Outputs

- concise answers to stakeholder questions, including competitive questions
- evidence-backed synthesis across multiple sources and platforms
- drill-down explanations by category, segment, occasion, **or competitor**
- supporting excerpts or references from retrieved conversations
- transparent indication of source and competitive-coverage limitations



## Constraints



### Data and Sources

- Use publicly available user conversations and approved research inputs for this phase
- Do not assume direct integration with Myntra internal behavioral data in the initial version
- Treat public feedback as directional evidence, not absolute truth
- Competitor comparisons are inferred from public mentions, not from competitors’ private analytics
- Design the architecture so it can later incorporate internal event data, funnel metrics, and behavioral signals



### Transparency and Reliability

- Insights must be evidence-backed and explainable
- Outputs should clearly indicate confidence level and source limitations
- Competitive claims must show which platforms were mentioned and how strongly evidence supports the comparison
- The system should avoid overstating conclusions from isolated anecdotes
- The chatbot must remain grounded in retrieved evidence and structured insight layers



## Success Criteria

The discovery engine should:

- identify recurring reasons behind wishlist non-conversion
- distinguish purchase-intent wishlisting from passive bookmarking
- highlight the most plausible opportunity areas tied to the target metric
- compare patterns across sources, categories, and user segments
- **compare wishlist motives and barriers for Myntra vs competitors (Nykaa, Ajio, etc.) with evidence**
- provide a **unified single-page** dashboard + Ask AI experience, including competitive views
- generate credible, PM-usable insights rather than raw summaries


## Summary

The goal is to build a credible, structured, and scalable wishlist conversion insight system for Myntra — including a **competitive analysis lens** on why users wishlist on Myntra versus platforms like Nykaa and Ajio.

By combining a dashboard, a semantic analytics layer, and a grounded RAG assistant, the system should help researchers and product managers understand why wishlist intent often fails to convert into purchase within 30 days, and how those motives and frictions differ across competitors. It should uncover the real frictions, uncertainties, and unmet needs between product interest and purchase, while presenting them in a form that is measurable, explainable, actionable, and competitively aware.
