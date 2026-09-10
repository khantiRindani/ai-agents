# Cartographer — Architecture

> *Last updated: 2026-09-06 | Version: v1 MVP*

---

## System Overview

Cartographer is a **stateful multi-agent research pipeline** built on LangGraph. A user submits a natural-language research question (the *Quest*) and receives a cited, structured Markdown report (the *Treasure Map*).

The system is designed around three principles:
1. **Provider-agnostic** — any LangChain `BaseChatModel` can be swapped in via env config
2. **Iterative self-improvement** — a Critic node drives re-search loops until coverage is sufficient
3. **Observable** — every node emits trace events consumed by both the Gradio UI and eval harness

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                      │
│                                                                  │
│   Jupyter Notebook (cartographer.ipynb)                          │
│   Gradio App (cartographer_gradio.py)                            │
│         │  astream_events(v2)                                    │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                      LangGraph Runtime                           │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │ PLANNER  │───►│ EXPLORER │───►│  CRITIC  │───►│  WRITER  │  │
│   └──────────┘    └──────────┘    └────┬─────┘    └──────────┘  │
│                        ▲              │                          │
│                        └──────────────┘                          │
│                     (re-expedition if score < threshold)         │
└─────────────────────────────────────────────────────────────────┘
          │                      │
┌─────────▼──────┐    ┌──────────▼──────────────────────────────┐
│   LLM Layer    │    │          Tool Layer                      │
│                │    │                                          │
│  llm_factory   │    │  tools/search.py → Tavily AsyncClient   │
│  (BaseChatModel│    │  asyncio.gather (parallel per waypoint)  │
│   provider-    │    │  tenacity retry (3 attempts, exp backoff)│
│   agnostic)    │    └──────────────────────────────────────────┘
└────────────────┘
```

---

## Component Breakdown

### LangGraph StateGraph (`src/graph.py`)

The graph is a compiled `StateGraph[CartographerState]` with 4 nodes and 1 conditional edge:

```
Entry ──► planner ──► explorer ──► critic ──┬──(gap)──► explorer
                                            └──(done)─► writer ──► END
```

**Conditional edge logic** (`_should_reexpedite`):
```python
if coverage_score < CRITIC_SCORE_THRESHOLD and expedition_count < MAX_EXPEDITIONS:
    return "explorer"   # re-expedite
return "writer"         # proceed
```

Both thresholds are environment-configurable — no code change needed to tune.

---

### State Schema (`src/state.py`)

`CartographerState` is a `TypedDict` passed between nodes. Two fields use LangGraph's **reducer pattern** (`Annotated[list, operator.add]`) so nodes append rather than overwrite:

| Field | Type | Reducer | Owner |
|---|---|---|---|
| `quest` | `str` | — | Input |
| `waypoints` | `list[str]` | — | Planner |
| `terrain` | `list[SearchResult]` | `operator.add` | Explorer (appends) |
| `coverage_score` | `float` | — | Critic |
| `uncharted_zones` | `list[str]` | — | Critic |
| `expedition_count` | `int` | — | Explorer |
| `treasure_map` | `str` | — | Writer |
| `sources` | `list[Source]` | — | Writer |
| `trace` | `list[dict]` | `operator.add` | All nodes (appends) |

The `operator.add` reducer on `terrain` means re-expeditions **accumulate** results — the Writer always synthesizes the full body of collected evidence.

---

### LLM Factory (`src/llm_factory.py`)

All nodes call `build_llm()` — never instantiate a model directly. This is the single provider-swap point:

```python
# Priority: explicit args → env vars → defaults
build_llm(provider="google", model="gemini-2.0-flash")  # explicit
build_llm()  # reads CARTOGRAPHER_LLM_PROVIDER + CARTOGRAPHER_LLM_MODEL

# To add a new provider: add one elif branch here
```

Streaming is controlled per-call:
- `streaming=False` → Planner, Critic (structured JSON output — streaming not useful)
- `streaming=True` → Writer (token streaming to Gradio)

---

### Search Tool (`src/tools/search.py`)

Tavily is accessed through a thin async abstraction:

```python
await parallel_search(queries=waypoints, max_results_per_query=5)
```

Internals:
- `AsyncTavilyClient` for async-native calls
- `asyncio.gather(*tasks)` — all waypoints searched concurrently
- Per-query `@retry` via tenacity (3 attempts, exponential 2–10s backoff)
- URL deduplication across all results (set-based)
- Sort by Tavily relevance score descending

If any single query fails after 3 retries, it logs a warning and is skipped — the expedition continues with partial results.

---

### Nodes

#### Planner (`src/nodes/planner.py`)
- Uses `streaming=False` — output is structured JSON
- Strips markdown fences from LLM response before JSON parse
- Fallback: if parse fails, uses the raw quest as a single waypoint (graceful degradation)
- Initialises `expedition_count=0` and `terrain=[]` in state

#### Explorer (`src/nodes/explorer.py`)
- Detects re-expedition via `expedition_count > 0 and uncharted_zones`
- First expedition: searches `waypoints`
- Re-expeditions: searches `uncharted_zones` only (targeted gap-filling)
- Returns `terrain` (appended via reducer), increments `expedition_count`

#### Critic (`src/nodes/critic.py`)
- Compacts terrain to ≤ 8,000 chars for context budget management
- LLM returns JSON with `coverage_score`, `uncharted_zones`, `reasoning`
- Fallback: parse error → `coverage_score=7.5`, `uncharted_zones=[]` (safe pass)
- Drives the graph conditional edge via its output values

#### Writer (`src/nodes/writer.py`)
- Uses `streaming=True` — Gradio captures `on_chat_model_stream` events
- Builds a citation index from terrain (dedup by URL, assign `[N]` indices)
- Prompt asks for: Executive Summary → sections per waypoint → Known Unknowns → Sources
- Returns `treasure_map` (full Markdown) and `sources` (deduplicated list)

---

## Streaming Architecture

```
graph.astream_events(initial_state, version="v2")
        │
        ├─ event: on_chain_end  {name: "planner"}
        │         └─► Update Expedition Log with waypoints
        │
        ├─ event: on_chain_end  {name: "explorer"}
        │         └─► Update Expedition Log with result count
        │
        ├─ event: on_chain_end  {name: "critic"}
        │         └─► Update Expedition Log with score + gaps
        │
        ├─ event: on_chat_model_stream   ← Writer LLM tokens
        │         └─► Append token to Treasure Map panel (live)
        │
        ├─ event: on_chain_end  {name: "writer"}
        │         └─► Update Expedition Log (done)
        │
        └─ event: on_chain_end  {name: "LangGraph"}
                  └─► Show final stats (score, source count)
```

Gradio's `queue()` + async generator bridge enables this without websocket setup. The `fn=run_cartographer` is an `async def` generator that `yield`s `(log, map)` tuples on each event.

---

## Data Flow Diagram

```
Quest (str)
    │
    ▼ Planner
waypoints: ["sub-q 1", "sub-q 2", "sub-q 3", "sub-q 4"]
    │
    ▼ Explorer (parallel)
terrain: [
  {url, title, content, score, published_date},  ← from waypoint 1
  {url, title, content, score, published_date},  ← from waypoint 2
  ...                                             ← deduplicated, sorted
]
    │
    ▼ Critic
coverage_score: 6.2  ← below threshold
uncharted_zones: ["cost comparison", "managed vs self-hosted"]
    │
    ▼ Explorer (re-expedition — searches uncharted_zones only)
terrain: [...original..., ...new gap results...]  ← operator.add appends
    │
    ▼ Critic
coverage_score: 8.4  ← above threshold
uncharted_zones: []
    │
    ▼ Writer
treasure_map: "## Executive Summary\n...\n## Section 1\n...[1]...\n## Sources\n[1] ..."
sources: [{url, title, citation_index}, ...]
```

---

## Dependency Graph

```
cartographer_gradio.py
    └── src/graph.py
            ├── src/state.py
            ├── src/nodes/planner.py ──── src/llm_factory.py
            ├── src/nodes/explorer.py ─── src/tools/search.py ── tavily-python
            ├── src/nodes/critic.py ───── src/llm_factory.py
            └── src/nodes/writer.py ───── src/llm_factory.py

src/llm_factory.py
    ├── langchain-google-genai   (default)
    ├── langchain-anthropic      (optional)
    └── langchain-openai         (optional)
```

---

## Environment & Configuration

| Variable | Default | Effect |
|---|---|---|
| `CARTOGRAPHER_LLM_PROVIDER` | `google` | Selects LLM backend |
| `CARTOGRAPHER_LLM_MODEL` | `gemini-2.0-flash` | Model within provider |
| `GOOGLE_API_KEY` | — | Required for Gemini |
| `TAVILY_API_KEY` | — | Required for search |
| `TAVILY_MAX_RESULTS` | `5` | Results per query |
| `MAX_EXPEDITIONS` | `2` | Re-search loop cap |
| `CRITIC_SCORE_THRESHOLD` | `7.0` | Pass/fail coverage boundary |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing (v2) |
| `LANGCHAIN_API_KEY` | — | LangSmith key if tracing enabled |

---

## Sequence Diagram

```
User          Gradio          Graph           Tavily         LLM
 │              │               │               │              │
 │──Quest──────►│               │               │              │
 │              │──astream_ev──►│               │              │
 │              │               │──ainvoke─────────────────────►│ (Planner)
 │              │               │◄─waypoints───────────────────│
 │              │◄──log update──│               │              │
 │              │               │──gather──────►│ (parallel)   │
 │              │               │◄──terrain─────│              │
 │              │◄──log update──│               │              │
 │              │               │──ainvoke─────────────────────►│ (Critic)
 │              │               │◄─score+gaps──────────────────│
 │              │◄──log update──│               │              │
 │              │               │   (if gap: repeat Explorer+Critic)
 │              │               │──ainvoke(stream)─────────────►│ (Writer)
 │◄─map tokens──│◄──tokens──────│◄──stream─────────────────────│
 │              │               │◄─done────────────────────────│
 │◄─final stats─│◄──log update──│               │              │
```
