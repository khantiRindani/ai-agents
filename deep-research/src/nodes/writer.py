"""
Cartographer — Writer Node
"Draw the Map"

Synthesizes all terrain into a structured Markdown Treasure Map.
Designed for streaming: uses ainvoke with streaming=True LLM.
The Gradio layer calls graph.astream_events() and captures on_llm_new_token events
from this node to stream tokens to the UI in real time.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm_factory import build_llm
from src.state import CartographerState, Source

WRITER_SYSTEM = """\
You are the Cartographer. Your final task is to draw the Treasure Map — a comprehensive,
well-structured research report that answers the Quest using the collected terrain.

Guidelines:
1. Start with a concise **Executive Summary** (3–5 sentences).
2. Write one section per major theme or waypoint. Use ## headings.
3. Cite sources inline using [N] notation matching the source index provided.
4. End with a **Known Unknowns** section listing any aspects that couldn't be fully researched.
5. End with a **Sources** section listing all cited URLs.
6. Write in clear, professional prose. Be specific, not vague.
7. Aim for depth over brevity — the user wants a thorough report.

The output should be clean Markdown that renders well.
"""


def _build_sources(terrain: list[dict]) -> tuple[str, list[Source]]:
    """Deduplicate terrain by URL, assign citation indices."""
    seen: dict[str, int] = {}
    sources: list[Source] = []
    for r in terrain:
        url = r["url"]
        if url and url not in seen:
            idx = len(sources) + 1
            seen[url] = idx
            sources.append(Source(url=url, title=r.get("title", url), citation_index=idx))

    source_lines = "\n".join(
        f"[{s['citation_index']}] [{s['title']}]({s['url']})" for s in sources
    )
    return source_lines, sources


def _build_terrain_for_writer(terrain: list[dict]) -> str:
    """Format terrain for the writer prompt with citation indices."""
    seen_urls: dict[str, int] = {}
    idx = 1
    lines = []
    for r in terrain:
        url = r["url"]
        if url not in seen_urls:
            seen_urls[url] = idx
            idx += 1
        citation = seen_urls[url]
        lines.append(
            f"[{citation}] Title: {r.get('title', '')}\n"
            f"    Content: {r.get('content', '')[:400]}\n"
            f"    URL: {url}\n"
        )
    return "\n".join(lines)


async def writer_node(state: CartographerState) -> dict:
    """
    Synthesizes the Treasure Map from all collected terrain.
    Uses streaming LLM — Gradio captures tokens via astream_events.
    """
    llm = build_llm(streaming=True)  # Streaming enabled for real-time Gradio output

    source_section, sources = _build_sources(state["terrain"])
    terrain_text = _build_terrain_for_writer(state["terrain"])
    waypoints_str = "\n".join(f"- {w}" for w in state["waypoints"])

    messages = [
        SystemMessage(content=WRITER_SYSTEM),
        HumanMessage(content=(
            f"Quest: {state['quest']}\n\n"
            f"Research Waypoints:\n{waypoints_str}\n\n"
            f"Collected Terrain (with citation indices):\n{terrain_text}\n\n"
            f"Coverage Score: {state.get('coverage_score', 'N/A')}/10\n\n"
            f"Available Sources:\n{source_section}\n\n"
            "Now draw the Treasure Map."
        )),
    ]

    response = await llm.ainvoke(messages)
    treasure_map = response.content
 
    trace_entry = {
        "node": "writer",
        "status": "done",
        "message": f"🗺️ **Treasure Map drawn** — {len(sources)} sources cited, {len(treasure_map)} chars",
    }

    return {
        "treasure_map": treasure_map,
        "sources": sources,
        "trace": [trace_entry],
    }
