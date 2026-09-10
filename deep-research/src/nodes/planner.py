"""
Cartographer — Planner Node
"Chart the Territory"

Decomposes the user's Quest into 3–5 focused Waypoints (sub-queries)
that together cover the research space completely.
"""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm_factory import build_llm
from src.state import CartographerState

PLANNER_SYSTEM = """\
You are the Cartographer's Planner. Your job is to chart the territory before the expedition begins.

Given a research Quest, decompose it into 3 to 5 focused sub-queries (Waypoints).
Each Waypoint should:
- Target a distinct, non-overlapping aspect of the Quest
- Be specific enough to yield useful web search results
- Together, the Waypoints should fully cover the Quest

Return ONLY a valid JSON array of strings. No explanation, no markdown, no extra text.

Example output:
["What is X?", "How does X compare to Y?", "What are the limitations of X?", "Recent developments in X 2024–2025"]
"""


async def planner_node(state: CartographerState) -> dict:
    """Decomposes the Quest into Waypoints for parallel exploration."""
    llm = build_llm(streaming=False)  # Planner output is structured JSON — no streaming needed

    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=f"Quest: {state['quest']}"),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        waypoints: list[str] = json.loads(raw)
        if not isinstance(waypoints, list) or not waypoints:
            raise ValueError("Expected a non-empty list")
    except (json.JSONDecodeError, ValueError) as exc:
        # Fallback: treat full response as a single waypoint to avoid hard failure
        waypoints = [state["quest"]]
        print(f"[Planner] Warning: failed to parse waypoints, using Quest as fallback. Error: {exc}")

    trace_entry = {
        "node": "planner",
        "status": "done",
        "message": f"Charted **{len(waypoints)} Waypoints**:\n" + "\n".join(f"  {i+1}. {w}" for i, w in enumerate(waypoints)),
    }

    return {
        "waypoints": waypoints,
        "expedition_count": 0,
        "terrain": [],
        "trace": [trace_entry],
    }
