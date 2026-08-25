# Google Stitch Prompt — Wishlist Intelligence (Unified Single Page)

> Paste the prompt in the `PROMPT` block below into Google Stitch. It supersedes the earlier
> two-screen concept (separate `wishlist_intelligence_insight_dashboard` and
> `wishlist_intelligence_ai_assistant`) with a single **unified page** that matches
> [`doc/Architecture.md`](../doc/Architecture.md) §3.5 / §5 and
> [`doc/ImplementationPlan.md`](../doc/ImplementationPlan.md) Phase 5:
> Insight Dashboard + Competitive Analysis + docked **Ask AI**, all on one page.

---

## PROMPT

Design a **beautiful, modern, flashy analytics web app** called **"Wishlist Intelligence"** — an AI‑powered discovery engine that explains why shoppers add items to their Myntra wishlist but don't buy, and compares wishlist behavior across Myntra vs competitors (Nykaa, Ajio). It is a **single unified page**: an insight dashboard, a competitive analysis section, and a docked **"Ask AI"** assistant panel — no route switching.

### Brand & visual style
- **Brand:** Myntra. Use the Myntra pink→magenta gradient as the hero accent (`#FF3E6C → #D1006C`), on a clean light‑gray canvas (`#F5F6FA`) with pure‑white cards.
- **Feel:** premium fintech‑analytics dashboard — flashy but professional. Rounded 16px cards, soft layered shadows, subtle gradient borders, generous whitespace, smooth micro‑interactions and hover lifts.
- **Typography:** modern geometric sans (Inter / Poppins). Big bold metric numbers, medium section titles, muted gray secondary labels.
- **Accents:** vibrant multi‑stop chart palette (magenta, coral, violet, teal, amber). Rounded pill badges for confidence (green = High, amber = Medium, yellow = Low).
- **Data‑viz first:** every insight pairs a chart with an evidence/confidence indicator.

### Global layout (top → bottom, single scrollable page)
1. **Top nav bar** (white, thin bottom border): Myntra logo + "Wishlist Intelligence" wordmark on the left; center links (Dashboard · Competitive · Ask AI as anchor tabs that scroll to sections); right side search icon, notification bell, user avatar.
2. **Left filter rail** (fixed, ~260px, subtle card) — this is a **single shared, synced filter panel that controls BOTH the dashboard and the Ask AI answers**. Design it once and reuse the exact same visual system in both contexts (same width, spacing, control styles, labels, colors, and iconography). "Filters" heading with:
   - Time Period dropdown (default "Last 30 days").
   - Product Category dropdown + multi‑select list (Women's Apparel, Men's Apparel, Footwear, Accessories, Beauty).
   - Price Band dual‑range slider (₹0 → ₹10,000+) with two numeric inputs.
   - Intent Type segmented pills (High Intent / Medium / Low‑Passive).
   - **Platform** checkboxes with brand chips: Myntra, Nykaa, Ajio, Other.
   - Source checkboxes with small brand icons (Play Store, Reddit, YouTube, Instagram, Product Reviews, Social).
   - Confidence 0–100% slider.
   - **Sync affordance:** a small caption at the bottom of the rail — "Filters apply to charts and Ask AI" — plus a "Reset filters" text button. Selecting a filter visibly narrows the dashboard AND scopes Ask AI's answers, so the two never feel like separate tools.
3. **Main content column** (right of rail) contains all sections below.

### Section A — KPI hero row (4 gradient stat cards)
Four equal cards with big numbers and a small trend delta:
- **Wishlist‑to‑Purchase** — `18.4%` · "Last 30 days" · green `+2.1%`.
- **Active vs Passive Intent** — `62% / 38%`.
- **Total Feedback Analyzed** — `124,832` entries.
- **Top Friction** — "Price Sensitivity 34%" · "Most common reason".
Make one card use the pink→magenta gradient fill (white text) as a hero highlight; the rest white.

### Section B — Non‑Conversion Reasons (with AI Confidence)
A white card titled "Non‑Conversion Reasons (with AI Confidence)". A horizontal bar chart ranking reasons with % values and a confidence pill on the right of each row:
- Price Sensitivity 34% — High Confidence
- Fit & Sizing Issues 22% — High Confidence
- Product Quality Concerns 15% — Medium Confidence
- Styling & Aesthetics 10% — Medium Confidence
- Availability & Stock 9% — Low Confidence
- Shipping & Returns 6% — Low Confidence
- Competitive / Platform Preference 4% — Low Confidence
Bars use the magenta family; each row hover reveals a "View evidence" link.

### Section C — Reasons × Segments heatmap
Beside Section B (two‑column on desktop): a color‑intensity heatmap grid. Rows = reasons (Price, Fit, Quality, Styling); Columns = user segments (High Spenders, Trend Seekers, Bargain Hunters, New Users). Darker magenta = stronger signal. Include a legend.

### Section D — Competitive Analysis (Myntra vs Nykaa vs Ajio) — make this the flashy centerpiece
A prominent full‑width card titled **"Competitive Wishlist Analysis"** with a platform legend (Myntra magenta, Nykaa coral/pink, Ajio violet). Include:
- **"Why users wishlist" grouped bar chart** — wishlist *motives* on the x‑axis (Assortment & Discovery, Price / Sale Waiting, Brand & Exclusive, Category Strength, Trust & Quality, UX & Convenience, Social & Inspiration), grouped bars per platform.
- **"Barriers to purchase" grouped bar chart** — reason categories per platform.
- **Three "Top motives per platform" mini‑cards** (Myntra / Nykaa / Ajio), each showing the platform chip and its top 3 motives with share %.
- A **"Shared vs Unique themes"** strip: shared motives shown as neutral chips, platform‑unique motives shown in the platform's color.
- A concise **"Why they don't purchase" narrative** callout box (soft gradient background) summarizing the top barriers in plain language, with an evidence/confidence footnote.

### Section E — Emerging Themes timeline
A white card "Emerging Themes Timeline (Last 6 Months)": a multi‑line chart (Jan–Jun) with trend labels — Sustainable Materials (+15%), Virtual Try‑On Demand (+22%), Faster Delivery Expectations (+8%). Smooth curved lines with the vibrant palette and a bottom legend.

### Section F — Ask AI (docked assistant panel, right side of the page)
A tall docked panel (right column, ~380px, sticky) titled **"Ask AI — your wishlist insights assistant"** with a subtle gradient header and a small sparkle/AI icon. **Design this panel to be instantly understandable to someone who has never seen the product before.** It contains:

- **A one‑line plain‑language purpose** directly under the title: "Ask questions in everyday language and get answers backed by real shopper feedback — it respects the same filters as your dashboard."
- **Shared‑filter context bar:** directly under the purpose line, show the **currently active filters from the left rail** as small removable chips (e.g. "Footwear ✕", "Myntra ✕", "Last 30 days ✕"), using the **exact same chip/badge styling, colors, and platform brand chips as the filter rail**. Include a caption "Answers are scoped to these filters." Removing a chip here also clears it in the left rail, and vice‑versa — the filter state is one shared source of truth, presented consistently in both places.
- **A friendly welcome / empty state** (shown before any question is asked), so newcomers immediately understand what to do:
  - A large sparkle/chat illustration with a warm heading: "👋 Not sure where to start? Just ask."
  - A short **"What I can do"** helper block with 3 quick value bullets, each with a small icon:
    - "🔎 Explain *why* shoppers don't buy wishlisted items"
    - "⚖️ Compare wishlist behavior across Myntra, Nykaa & Ajio"
    - "📊 Summarize themes by category, price, or shopper segment"
  - A subtle reassurance line: "Every answer cites its sources and shows a confidence score."
- **Suggested question chips** labeled with a small helper caption "Try one of these to get started:" (rounded pills, wrap to multiple rows):
  - "Why did users not convert the 'Summer Dress'?"
  - "Top non‑conversion reasons for footwear"
  - "Why do users wishlist on Myntra vs Nykaa?"
  - "What barriers are unique to Ajio wishlists?"
  - "Analyze sentiment for the 'Athleisure' category"
- **A chat conversation area** (shown after asking): a user bubble (magenta gradient, right‑aligned) asking "What are the main reasons users abandon the 'Nike Air Max' in their wishlists?"; an AI answer bubble (white, left‑aligned) citing evidence inline like `[Reddit #42]` and `[YouTube #15]`, ending with a **Confidence: 88%** pill and a small "View evidence" link.
- **A bottom input bar** with placeholder "Ask anything about wishlist data…", a friendly helper hint below it ("e.g. 'Compare why people wishlist sneakers on Myntra vs Ajio'"), and a magenta gradient send button.
- **A first‑time hint / tooltip** on load: a small dismissible coach‑mark pointing at the input that says "New here? Type a question or tap a suggestion above."
- On narrow/mobile viewports, this panel collapses into a floating action button (FAB) **labeled "Ask AI"** (icon + text, not just an icon, so its purpose is obvious) that opens the assistant as a drawer.

### Section G — Evidence Drawer (slide‑in from right, triggered by citations / "View evidence")
A panel titled "Evidence Drawer" listing source cards, each with: a source icon (Reddit / YouTube / Instagram / Play Store), thread/video/post title, an anonymized quote excerpt, and tag pills (e.g., "Price Sensitivity", "Footwear", "Nykaa"). Include a close (×) button.

### Responsive behavior
- Desktop: 3‑zone layout — left filter rail, center dashboard/competitive content, right docked Ask AI.
- Tablet: Ask AI docks below the dashboard.
- Mobile: single column; filters become a top sheet; Ask AI becomes a FAB + drawer.

### Overall polish
Add tasteful gradient glows behind KPI numbers, animated bar/line reveals on load, hover tooltips on every chart data point, and consistent confidence badges everywhere so the UI feels **evidence‑grounded, explainable, and competitively aware**. Keep it flashy, clean, and delightful.

---

## Notes for regenerating individual screens (optional)
If Stitch struggles with one giant page, generate in two passes and stitch together:
1. **Dashboard + Competitive** (Sections A–E + G) using everything above except Section F.
2. **Ask AI panel** (Section F + G) as a docked/right‑rail component sharing the same brand system.
Keep the brand palette, typography, card radius, and confidence badges identical across both so they compose into one unified page.
