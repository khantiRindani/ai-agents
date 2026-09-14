# Cartographer — Specification v2: Feature Roadmap

| Field | Value |
|---|---|
| **Version** | v2 |
| **Status** | 📋 Planned |
| **Date** | 2026-09-14 |
| **Author** | AI Builder Portfolio |
| **Scope** | Feature extensions beyond the v1 MVP |
| **Predecessor** | [v1_mvp.md](./v1_mvp.md) |

---

## Overview

v1 delivered the core research loop: plan → explore → critique → write, with a streaming Gradio UI. v2 extends Cartographer with **observability**, **output quality**, **export**, and **internationalisation** features — transforming it from a proof-of-concept into a portfolio-grade research tool.

---

## Feature Specifications

---

### F-01: LangSmith Tracing & Observability
**Priority:** 🔴 High

#### Motivation
With v1 the only way to measure latency and token usage is manual timing logged to stdout. LangSmith provides a hosted dashboard with per-step latency, token counts, and run comparison — essential for iterating on prompt quality.

#### Design
- Enable via `.env`:
  ```
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=<key>
  LANGCHAIN_PROJECT=cartographer
  ```
- No code changes required — LangChain/LangGraph natively integrates with LangSmith when env vars are set.
- Captured metrics per run:
  - Per-node latency (Planner, Explorer, Critic, Writer)
  - Total token usage per LLM call (prompt + completion)
  - Coverage score history across re-expedition loops
  - Quest text and final Treasure Map (for prompt debugging)

#### Acceptance Criteria
- Runs appear in the LangSmith project dashboard within 30 seconds of completion
- Token usage and latency are visible per node, not just total
- Tracing is disabled when `LANGCHAIN_TRACING_V2` is unset (zero overhead in off state)

---

### F-02: PII Redaction on Report Output
**Priority:** 🟡 Medium

#### Motivation
Tavily search results may contain personal information (emails, phone numbers, full names in URLs). The Writer synthesises this verbatim into the Treasure Map, which could surface PII the user didn't intend to publish.

#### Design
- Post-process `treasure_map` string before returning from the Writer node.
- Use regex patterns to detect and redact:
  - Email addresses → `[EMAIL REDACTED]`
  - Phone numbers (international formats) → `[PHONE REDACTED]`
  - Social Security / national ID patterns → `[ID REDACTED]`
- Optional: integrate with a dedicated PII detection library (e.g. `scrubadub`, `presidio`) for higher recall.
- Configurable via `CARTOGRAPHER_PII_REDACTION=true` (default: `false`).

#### Acceptance Criteria
- Email addresses in synthesised report are replaced with `[EMAIL REDACTED]`
- No PII redaction when `CARTOGRAPHER_PII_REDACTION=false`
- Redaction does not corrupt Markdown formatting (inline citations, links remain intact)

---

### F-03: Report Export (Markdown / HTML)
**Priority:** 🟢 Low

#### Motivation
The Treasure Map currently lives only inside the Gradio Markdown panel. Users who want to share, file, or print their research report have no native way to do so.

#### Design
- Add an **Export** button to the Gradio UI, visible after a quest completes.
- On click, generate a downloadable file:
  - **Markdown (`.md`)**: Raw treasure map string with a YAML frontmatter header (quest, date, coverage score, sources count).
  - **HTML**: Convert Markdown to styled HTML using `markdown` + `pygments` for syntax highlighting.
- Use Gradio's `gr.DownloadButton` or `gr.File` component to serve the file.
- File naming convention: `cartographer_<slug>_<date>.md` / `.html`

#### Acceptance Criteria
- Export button appears only after a successful expedition
- Downloaded `.md` file renders correctly in any Markdown viewer
- Downloaded `.html` file is self-contained (inline CSS) and renders in a browser without network access
- Export does not block or interrupt the streaming UI

---

### F-04: Source Credibility Scoring
**Priority:** 🟡 Medium

#### Motivation
The Critic currently scores *terrain coverage* but has no visibility into source quality. A high-coverage score built on low-quality sources (e.g. forums, unverified blogs) is misleading.

#### Design
- Extend `SearchResult` with a `credibility_score: float` field.
- Scoring heuristics (applied in the Explorer node post-search):
  - **Domain reputation tier**: Whitelist of high-credibility TLDs and domains (`.gov`, `.edu`, `.org`, major newspapers, peer-reviewed journals) → higher score.
  - **URL depth**: Shallow URLs (homepage-level) score lower than deep article URLs.
  - **Tavily relevance score**: Already available — factor into composite score.
  - **Published date freshness**: Recent articles (< 1 year) score higher.
- Composite `credibility_score = w1 * domain_score + w2 * relevance + w3 * freshness` (weights configurable via env).
- Writer prompt updated to instruct preferential citation of higher-credibility sources.
- Expedition Log and final stats display average credibility score alongside coverage score.

#### Acceptance Criteria
- `SearchResult.credibility_score` is populated for all results
- Writer prompt receives credibility scores and includes a "Reliability" note per source section
- Expedition complete stats show: Coverage score, Sources, Average credibility, Elapsed time

---

### F-05: Multi-Language Quest Support
**Priority:** 🟢 Low

#### Motivation
All prompts and the search pipeline assume English. Non-English quests produce degraded results because Tavily's `advanced` search is biased toward English-language sources, and the prompts are English-only.

#### Design
- **Quest language detection**: Use `langdetect` or `fasttext` to detect the input language on quest submission.
- **Query localisation**: If non-English detected, translate waypoints to the detected language before submitting to Tavily (using an LLM translate step or a lightweight translation API).
- **Prompt localisation**: Critic and Writer system prompts include an explicit `Respond in: {language}` instruction when non-English is detected.
- **Graceful fallback**: If language detection confidence < 0.85, default to English.
- Configurable via `CARTOGRAPHER_MULTILINGUAL=true` (default: `false`).

#### Acceptance Criteria
- A Spanish quest produces a Spanish Treasure Map
- A French quest searches with French-language waypoints
- English behaviour is completely unchanged when feature is disabled
- Language is displayed in the Expedition Log header (e.g. `🌐 Detected: French`)

---

## Summary Table

| Feature | ID | Priority | Complexity | Key Env Var |
|---|---|---|---|---|
| LangSmith Tracing | F-01 | 🔴 High | Low (env-only) | `LANGCHAIN_TRACING_V2` |
| PII Redaction | F-02 | 🟡 Medium | Medium | `CARTOGRAPHER_PII_REDACTION` |
| Report Export | F-03 | 🟢 Low | Medium | — |
| Source Credibility Scoring | F-04 | 🟡 Medium | High | — |
| Multi-Language Support | F-05 | 🟢 Low | High | `CARTOGRAPHER_MULTILINGUAL` |

---

## Implementation Order (Recommended)

1. **F-01 — LangSmith Tracing**: Zero code change, maximum observability gain. Do first to inform all subsequent improvements.
2. **F-02 — PII Redaction**: Self-contained post-processing step. Adds responsible-AI credibility with minimal risk.
3. **F-03 — Report Export**: Pure UI addition. High user-facing value, low risk.
4. **F-04 — Source Credibility Scoring**: Requires `SearchResult` schema extension and Explorer + Writer node changes. Test with existing eval suite.
5. **F-05 — Multi-Language**: Significant pipeline change. Implement last, with dedicated eval cases per language.

---

## Non-Goals for v2

- Real-time news / live event tracking (remains out of scope)
- Authentication and multi-user sessions
- Persistent database storage of quests and reports
- Domain-restricted mode (topic filtering / guardrails)
