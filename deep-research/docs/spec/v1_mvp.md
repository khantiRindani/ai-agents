# Cartographer — Specification v1: MVP

| Field | Value |
|---|---|
| **Version** | v1 |
| **Status** | ✅ Implemented |
| **Date** | 2026-09-06 |
| **Author** | AI Builder Portfolio |
| **Scope** | MVP — core research loop + Gradio UI + eval harness |

---

## 1. Problem Statement

Answering a complex research question on the web is time-consuming and fragmented. Users must manually:
1. Decompose the question into sub-topics
2. Run multiple searches
3. Evaluate source quality
4. Synthesize conflicting information into a coherent answer

**Cartographer** automates this entire workflow as an agentic loop, returning a cited, structured research report (the *Treasure Map*) for any open-ended question (the *Quest*).

---

## 2. Goals

### Must-Have (MVP)
- [ ] Accept a natural-language research question as input
- [ ] Automatically decompose into 3–5 focused sub-queries
- [ ] Run parallel web searches per sub-query
- [ ] Score research coverage using an LLM-as-judge rubric
- [ ] Automatically re-search to fill identified coverage gaps (max 2 iterations)
- [ ] Synthesize a structured, cited Markdown report
- [ ] Stream the report output to a Gradio UI in real time
- [ ] Run an eval suite of 5 curated test cases with pass/fail thresholds

### Nice-to-Have (future iterations)
- LangSmith tracing integration
- PII redaction on report output
- PDF/HTML export of Treasure Map
- Multi-language quest support
- Source credibility scoring per domain

### Non-Goals (explicit out-of-scope for v1)
- Real-time news / live event tracking
- Authentication and multi-user support
- Persistent storage of past quests/reports
- Domain-restricted mode (topic filtering)

---

## 3. User Stories

### US-01: Research a complex topic
> As a user, I want to type a research question and receive a comprehensive, cited report,
> so that I don't have to manually search, read, and synthesize multiple sources.

**Acceptance Criteria:**
- Report contains ≥ 5 cited sources
- Report is structured into sections with an executive summary
- Report is produced within 60–120 seconds

### US-02: Observe the research process
> As a user, I want to see what the agent is doing in real time,
> so I can understand how the Treasure Map was constructed.

**Acceptance Criteria:**
- Expedition Log shows each node step with status and summary
- Treasure Map streams token-by-token as it is written
- Coverage score is visible in the final status

### US-03: Trigger deeper research automatically
> As a user, I want the agent to recognize when initial results are insufficient
> and automatically search further, without requiring my input.

**Acceptance Criteria:**
- Critic node scores coverage 0–10
- If score < 7.0 AND expeditions < 2, Explorer re-runs on identified gaps
- Re-expedition is visible in the Expedition Log

### US-04: Switch LLM providers without code changes
> As a developer, I want to swap the LLM backend via environment config,
> so the system is not locked to any single provider.

**Acceptance Criteria:**
- `CARTOGRAPHER_LLM_PROVIDER` env var selects between `google`, `anthropic`, `openai`
- `CARTOGRAPHER_LLM_MODEL` selects the specific model
- No Python code change required

---

## 4. Functional Specification

### 4.1 Input
- **Quest**: Free-text research question (1–3 sentences)
- **Constraints**: No file upload, no conversation history in v1

### 4.2 Graph Flow

```
Quest
 │
 ▼
[Planner]     → Decomposes Quest into 3–5 Waypoints (JSON list)
 │
 ▼
[Explorer]    → Parallel Tavily searches per Waypoint
 │             Returns: snippets, URLs, Tavily relevance scores
 ▼
[Critic]      → LLM-as-judge coverage scoring
 │             Produces: coverage_score (0–10), uncharted_zones
 │
 ├── score < 7.0 AND expedition_count < 2 ──► [Explorer] (re-expedition)
 │
 └── score ≥ 7.0 OR expedition_count = 2 ──► [Writer]
                                               │
                                               ▼
                                          Treasure Map
                                          (Markdown, streaming)
```

### 4.3 State Schema

```python
class CartographerState(TypedDict):
    quest: str                          # Input
    waypoints: list[str]                # Planner output
    terrain: Annotated[list[SearchResult], operator.add]  # Accumulated results
    coverage_score: float               # Critic output
    uncharted_zones: list[str]          # Critic: gap topics
    expedition_count: int               # Loop counter
    treasure_map: str                   # Writer output
    sources: list[Source]               # Cited sources
    trace: Annotated[list[dict], operator.add]  # Execution log
```

### 4.4 Node Specifications

#### Planner Node
- **Model**: Configurable (default: Gemini Flash, `streaming=False`)
- **Input**: `quest`
- **Prompt strategy**: System prompt instructs JSON array output of 3–5 sub-queries
- **Fallback**: If JSON parse fails, uses the full quest as a single waypoint
- **Output**: `waypoints`, `expedition_count=0`, `terrain=[]`

#### Explorer Node
- **Tool**: Tavily `AsyncTavilyClient`, `search_depth="advanced"`
- **Pattern**: `asyncio.gather` for parallel per-waypoint searches
- **Retry**: `tenacity` — 3 attempts, exponential backoff (2–10s)
- **Dedup**: Results deduplicated by URL; sorted by Tavily relevance score
- **On re-expedition**: Queries `uncharted_zones` instead of `waypoints`
- **Output**: Appends to `terrain` (via `operator.add` reducer)

#### Critic Node
- **Model**: Configurable (default: Gemini Flash, `streaming=False`)
- **Input**: `quest`, `waypoints`, `terrain` (compact summary, max 8000 chars)
- **Prompt strategy**: 5-dimension rubric → structured JSON output
- **Threshold**: `CRITIC_SCORE_THRESHOLD` env var (default: 7.0)
- **Fallback**: If JSON parse fails, defaults `coverage_score=7.5` (safe pass)
- **Output**: `coverage_score`, `uncharted_zones`

#### Writer Node
- **Model**: Configurable (default: Gemini Flash, `streaming=True`)
- **Input**: full state
- **Prompt strategy**: Instructs structured Markdown with inline citations `[N]`
- **Streaming**: Enabled — Gradio captures `on_chat_model_stream` events
- **Output**: `treasure_map`, `sources` (deduplicated, indexed)

### 4.5 Streaming Contract

```
graph.astream_events(state, version="v2")
│
├── on_chain_end {name: "planner"}   → update Expedition Log
├── on_chain_end {name: "explorer"}  → update Expedition Log
├── on_chain_end {name: "critic"}    → update Expedition Log
├── on_chat_model_stream             → append token to Treasure Map panel
├── on_chain_end {name: "writer"}    → update Expedition Log (final entry)
└── on_chain_end {name: "LangGraph"} → display final stats
```

---

## 5. Non-Functional Requirements

| Requirement | Target | Notes |
|---|---|---|
| End-to-end latency | < 120s per quest | Includes 2 search rounds + LLM synthesis |
| Search concurrency | Parallel (all waypoints at once) | `asyncio.gather` |
| Max search retries | 3 per query | `tenacity` exponential backoff |
| LLM provider | Provider-agnostic | `BaseChatModel` interface |
| Free-tier search | Tavily 1,000 credits/mo | ~50–100 quests/mo |
| Critic loop limit | max 2 re-expeditions | Prevents infinite loops |
| Context limit | 8,000 char terrain summary for Critic | Avoid context overflow |

---

## 6. Eval Specification

### Test Suite
- 5 curated quests across diverse domains
- Each test case specifies: expected topic coverage, min source count, min weighted score

### Judge Rubric (LLM-as-judge)

| Dimension | Weight | Criteria |
|---|---|---|
| Breadth | 25% | All expected topics present in report |
| Depth | 30% | Nuanced analysis, not just surface facts |
| Recency | 20% | Sources appear current (≤ 2 years) |
| Source Diversity | 15% | Multiple domains/perspectives |
| Citation Quality | 10% | Credible, accessible URLs |

### Pass Criteria
- `weighted_score ≥ min_coverage_score` (per test case, default 7.0)
- `len(sources) ≥ min_sources` (per test case, default 5)

---

## 7. Security & Hygiene

- API keys managed via `.env` (never hardcoded)
- `.env` excluded from git via `.gitignore`
- `.env.example` committed as template
- No user data persisted in v1
- Critic and Writer prompts include no user PII passthrough risk (quest is user-provided text only)

---

## 8. Open Items for v2

| Item | Priority | Notes |
|---|---|---|
| LangSmith tracing | High | Step latency, token usage dashboards |
| PII redaction on output | Medium | Scrub any leaked personal info from web snippets |
| Report export (PDF/HTML) | Low | Nice portfolio demo |
| Source credibility scoring | Medium | Domain reputation heuristics |
| Multi-language support | Low | Non-English quests |
