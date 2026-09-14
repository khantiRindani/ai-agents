"""
Cartographer — Planner Node
"Chart the Territory"

Decomposes the user's Quest into 3–5 focused Waypoints (sub-queries)
that together cover the research space completely.
"""
from __future__ import annotations

import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm_factory import build_llm
from src.logger import logger
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


def _extract_json_array(text: str) -> list[str]:
    """Extract a JSON list of strings from LLM text, handling markdown fences and surrounding commentary."""
    text = text.strip()

    # 1. Direct parse attempt
    try:
        data = json.loads(text)
        if isinstance(data, list) and data:
            return [str(item).strip() for item in data if str(item).strip()]
    except Exception:
        pass

    # 2. Markdown code fence extraction
    code_block_match = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1).strip())
            if isinstance(data, list) and data:
                return [str(item).strip() for item in data if str(item).strip()]
        except Exception:
            pass

    # 3. Regex bracket match
    bracket_match = re.search(r"(\[[\s\S]*?\])", text, re.DOTALL)
    if bracket_match:
        try:
            data = json.loads(bracket_match.group(1).strip())
            if isinstance(data, list) and data:
                return [str(item).strip() for item in data if str(item).strip()]
        except Exception:
            pass

    raise ValueError("Could not extract a valid JSON array of waypoints from LLM response.")


async def planner_node(state: CartographerState) -> dict:
    """Decomposes the Quest into Waypoints for parallel exploration."""
    t0 = time.perf_counter()
    logger.info(f"[Planner] Starting waypoint planning for quest: {state['quest']!r}")
    llm = build_llm(streaming=False)  # Planner output is structured JSON — no streaming needed

    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=f"Quest: {state['quest']}"),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    try:
        waypoints = _extract_json_array(raw)
    except Exception as exc:
        # Fallback: treat full quest as single waypoint
        waypoints = [state["quest"]]
        logger.warning(f"[Planner] JSON parse failed, falling back to quest as single waypoint. Error: {exc}. Raw: {raw[:200]!r}")

    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info(f"[Planner] Generated {len(waypoints)} waypoints in {duration_ms:.1f}ms: {waypoints}")

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
