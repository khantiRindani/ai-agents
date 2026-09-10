# Cartographer — Design Trade-offs

> *Last updated: 2026-09-06 | Version: v1 MVP*

This document records the key design decisions made during v1 development, the alternatives considered, and the rationale for each choice. Intended as a living record — update when decisions change across versions.

---

## 1. LangGraph vs. Plain Async Python

**Decision**: Use LangGraph `StateGraph`

| Option | Pros | Cons |
|---|---|---|
| **LangGraph** | Built-in state management, conditional edges, `astream_events` streaming, easy to visualize graph | Extra dependency, slight learning curve |
| Plain `asyncio` | Zero framework overhead, full control | Manual state passing, no native streaming events, harder to extend |
| LangChain `AgentExecutor` | Familiar, tool-based | Not designed for multi-step stateful loops; less control over node transitions |

**Rationale**: The critic→explorer re-expedition loop requires stateful conditional routing. LangGraph's `add_conditional_edges` expresses this natively and cleanly. The `astream_events` API is a first-class feature that powers the Gradio streaming UI without additional plumbing. The portfolio value of demonstrating LangGraph proficiency also factored in.

---

## 2. Single `CartographerState` vs. Per-Node Output Types

**Decision**: Single shared `TypedDict` state

| Option | Pros | Cons |
|---|---|---|
| **Single shared state** | Simple, all nodes see full context, easy to debug | All fields visible to all nodes (no strict encapsulation) |
| Per-node output types | Stronger encapsulation | More boilerplate; LangGraph still merges into shared state internally |

**Rationale**: For a 4-node pipeline, the overhead of per-node types outweighs the encapsulation benefit. The `TypedDict` with annotated reducers (`operator.add` for `terrain` and `trace`) provides enough type safety while keeping the code readable. Strict encapsulation can be introduced in v2 if the graph grows.

---

## 3. `operator.add` Reducer for Terrain vs. Overwrite

**Decision**: Accumulate terrain across expeditions using `operator.add`

| Option | Pros | Cons |
|---|---|---|
| **Accumulate (operator.add)** | Writer always synthesizes ALL collected evidence; re-expeditions add value | Terrain grows unbounded in theory |
| Overwrite on re-expedition | Simpler state; smaller context | Loses original expedition results; Writer has less material |

**Rationale**: The entire value of re-expeditions is filling *gaps* in the initial terrain. If terrain were overwritten, the Writer would lose high-quality initial results that scored well. Accumulation gives the Writer the richest possible evidence base. The 8,000-char truncation in the Critic prevents context overflow while preserving all results for the Writer.

---

## 4. Tavily (AI-Native) vs. Serper/SerpApi (Raw SERP)

**Decision**: Tavily as sole search provider

| Option | Pros | Cons |
|---|---|---|
| **Tavily** | Returns cleaned, LLM-ready text snippets; no scraping layer needed; AI-native; 1,000 free credits/mo | Proprietary index; less raw control |
| Serper.dev | Cheapest for raw Google SERP data | Returns links only — requires separate scraping/extraction |
| SerpApi | Multi-engine, reliable | 250 free/mo (too low); raw SERP only |
| Exa | Neural/semantic search — good for discovery | Less comprehensive than Tavily for factual queries |

**Rationale**: Tavily's AI-optimized snippets eliminate the need for a scraping layer (reducing complexity significantly). For a research agent that needs LLM-ready context, paying for cleaned content is the right trade. Exa was considered as a secondary but dropped to keep the v1 scope tight — can be added in v2 as a fallback for semantically complex quests.

---

## 5. Streaming: `astream_events` vs. Polling Final State

**Decision**: `astream_events(version="v2")` for full streaming

| Option | Pros | Cons |
|---|---|---|
| **astream_events** | Token-level streaming for Writer; node-level events for Expedition Log; native Gradio async integration | Slightly more complex event parsing |
| `ainvoke` + poll final state | Simpler code | No streaming — user waits for full execution with no feedback |
| `astream` (output-level) | Simpler than astream_events | Returns full node outputs, not individual LLM tokens |

**Rationale**: For a research agent that takes 60–120 seconds, a blank UI while waiting is a poor experience. `astream_events` enables two distinct streaming behaviours simultaneously: node-level progress (Expedition Log) and token-level output (Treasure Map). This required `version="v2"` which is the stable API as of LangGraph 0.2+.

---

## 6. Critic Fallback: Pass vs. Fail on Parse Error

**Decision**: Default to `coverage_score=7.5` (safe pass) on parse error

| Option | Pros | Cons |
|---|---|---|
| **Default pass (7.5)** | Agent always produces a report; avoids infinite error loops | May synthesize a report from insufficient terrain |
| Default fail (< 7.0) | Triggers re-expedition; might recover | Could loop indefinitely if Critic consistently fails |
| Hard failure / exception | Explicit error surface | Poor UX for a portfolio demo |

**Rationale**: The primary failure mode is an LLM occasionally returning malformed JSON. Defaulting to a pass score means the Writer still runs and produces *something*. Since the Critic is evaluating the same terrain each time, a repeated parse failure would loop on the same data anyway. A pass-default breaks the potential infinite loop gracefully. Future mitigation: use structured output (Pydantic) to make parse failures impossible.

---

## 7. LLM-as-Judge: Same Model vs. Separate Judge Model

**Decision**: Same model family for all nodes (Critic uses same `build_llm()` factory)

| Option | Pros | Cons |
|---|---|---|
| **Same model** | Simple; single API key; consistent behaviour | Self-evaluation bias risk — model may overrate its own output |
| Separate judge model | Reduces self-evaluation bias | Two API keys; more complex setup; higher cost |

**Rationale**: For v1 MVP, same-model judging is acceptable. The Critic evaluates *search terrain quality*, not the Writer's output — so self-evaluation bias is lower than if the Writer judged its own report. For the eval harness (`eval_runner.ipynb`), a separate call with `temperature=0.1` is used to make the judge more deterministic. v2 can introduce a different provider for the judge if bias becomes measurable.

---

## 8. Gradio vs. Streamlit for UI

**Decision**: Gradio

| Option | Pros | Cons |
|---|---|---|
| **Gradio** | Native async generator support; `queue()` built in; works inline in Jupyter; fast to set up | Less flexible layout than Streamlit |
| Streamlit | Rich layout options; session state | Streaming requires `st.write_stream`; not notebook-native; separate process |

**Rationale**: Gradio's async generator support (`yield`-based functions) maps directly onto `astream_events` with no adapter layer. The `queue()` mechanism handles backpressure automatically. Running inline in Jupyter (`demo.launch(inline=True)`) is a portfolio advantage — everything lives in one notebook. Streamlit would require a separate server process.

---

## 9. Max Expeditions Cap: 2

**Decision**: `MAX_EXPEDITIONS=2` (configurable via env)

| Option | Reasoning |
|---|---|
| 1 expedition | No re-search; Critic is purely diagnostic — not useful |
| **2 expeditions** | One initial search + one targeted gap-fill covers most cases; keeps latency bounded |
| 3+ expeditions | Marginal quality improvement; 3x–4x API cost; latency becomes unacceptable (>3 min) |

**Rationale**: Empirically, a targeted second expedition typically raises Critic score from 5–6 range to 7–8 range. A third expedition yields diminishing returns. The cap prevents runaway API usage, especially important under free-tier quotas (1,000 Tavily credits/mo).

---

## 10. `docs/spec/` Versioned Specs

**Decision**: Incremental spec files under `docs/spec/v{N}_{label}.md`

| Option | Reasoning |
|---|---|
| Single overwritten spec | Loses history of decisions; no audit trail |
| Git history only | History exists but no structured diff between versions |
| **Versioned spec files** | Explicit SDD evidence; shows spec-driven development; readable alongside code |

**Rationale**: The project guidelines require SDD evidence. Keeping versioned spec files committed alongside code makes the spec-to-implementation traceability explicit and reviewable without needing to dig through git history.
