"""
Cartographer — Critic Node
"Verify the Map"

Acts as LLM-as-judge: scores the coverage of collected terrain (0–10)
and identifies Uncharted Zones (topics still not covered).
Drives the conditional edge: re-expedite or proceed to Writer.
"""
from __future__ import annotations

import json
import os
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm_factory import build_llm
from src.logger import logger
from src.state import CartographerState

CRITIC_SYSTEM = """\
You are the Cartographer's Critic. Your role is to verify whether the collected research terrain
adequately answers the original Quest.

You will receive:
1. The Quest (research question)
2. The Waypoints (sub-queries that guided the search)
3. A summary of the collected terrain (snippets from web search results)

Evaluate coverage across these dimensions:
- Breadth (25%): Are all aspects of the Quest addressed?
- Depth (30%): Are answers nuanced and detailed, not just surface-level?
- Recency (20%): Do sources appear recent and relevant?
- Source Diversity (15%): Are multiple distinct perspectives/sources represented?
- Citation Quality (10%): Are sources credible and varied?

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
  "coverage_score": <float 0.0–10.0>,
  "reasoning": "<1–2 sentence explanation>",
  "uncharted_zones": ["<gap topic 1>", "<gap topic 2>"]
}

Rules:
- coverage_score >= 7.0 means the terrain is sufficient.
- uncharted_zones should be empty [] if score >= 7.0
- uncharted_zones should list 1–3 specific missing topics if score < 7.0
"""


def _extract_critic_json(text: str) -> dict:
    """Extract critic JSON object from LLM response, handling markdown fences and extraneous text."""
    text = text.strip()

    # 1. Direct parse attempt
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 2. Markdown code fence match
    code_block_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        try:
            data = json.loads(code_block_match.group(1).strip())
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # 3. Regex object match
    brace_match = re.search(r"(\{[\s\S]*?\})", text, re.DOTALL)
    if brace_match:
        try:
            data = json.loads(brace_match.group(1).strip())
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    raise ValueError("Could not extract a valid JSON object from Critic response.")


def _build_terrain_summary(state: CartographerState, max_chars: int = 8000) -> str:
    """Compact terrain into a string for the critic prompt (avoid huge context)."""
    lines = []
    total = 0
    for i, r in enumerate(state["terrain"]):
        snippet = f"[{i+1}] {r['title']}\n{r['content'][:300]}\nURL: {r['url']}\n"
        if total + len(snippet) > max_chars:
            lines.append(f"... ({len(state['terrain']) - i} more results truncated)")
            break
        lines.append(snippet)
        total += len(snippet)
    return "\n".join(lines)


async def critic_node(state: CartographerState) -> dict:
    """Scores terrain coverage and identifies gaps."""
    t0 = time.perf_counter()
    logger.info(f"[Critic] Evaluating coverage for quest: {state['quest']!r} (collected {len(state.get('terrain', []))} snippets)")
    llm = build_llm(streaming=False)  # Structured JSON output — no streaming

    terrain_summary = _build_terrain_summary(state)
    waypoints_str = "\n".join(f"- {w}" for w in state["waypoints"])

    messages = [
        SystemMessage(content=CRITIC_SYSTEM),
        HumanMessage(content=(
            f"Quest: {state['quest']}\n\n"
            f"Waypoints:\n{waypoints_str}\n\n"
            f"Collected Terrain:\n{terrain_summary}"
        )),
    ]

    response = await llm.ainvoke(messages)
    raw = response.content.strip()

    try:
        parsed = _extract_critic_json(raw)
        coverage_score = float(parsed.get("coverage_score", 5.0))
        # Bound score between 0.0 and 10.0
        coverage_score = max(0.0, min(10.0, coverage_score))
        uncharted_zones = [str(z).strip() for z in parsed.get("uncharted_zones", []) if str(z).strip()]
        reasoning = str(parsed.get("reasoning", "")).strip()
    except Exception as exc:
        # Safe fallback — assume borderline coverage, don't loop forever
        coverage_score = 7.5
        uncharted_zones = []
        reasoning = "Critic parse error — defaulting to safe pass."
        logger.warning(f"[Critic] JSON parse failed, defaulting to 7.5 pass: {exc}. Raw: {raw[:200]!r}")

    threshold = float(os.getenv("CRITIC_SCORE_THRESHOLD", "7.0"))
    duration_ms = (time.perf_counter() - t0) * 1000
    status_emoji = "✅" if coverage_score >= threshold else "⚠️"
    zone_msg = (
        f"Gaps: {', '.join(uncharted_zones)}" if uncharted_zones else "No gaps detected."
    )

    logger.info(
        f"[Critic] Evaluation complete in {duration_ms:.1f}ms: "
        f"score={coverage_score:.1f}/{threshold:.1f}, gaps={len(uncharted_zones)}, reason={reasoning!r}"
    )

    trace_entry = {
        "node": "critic",
        "status": "pass" if coverage_score >= threshold else "gap",
        "message": (
            f"{status_emoji} **Coverage Score: {coverage_score:.1f}/10** — {reasoning}\n"
            f"{zone_msg}"
        ),
    }

    return {
        "coverage_score": coverage_score,
        "uncharted_zones": uncharted_zones,
        "trace": [trace_entry],
    }
