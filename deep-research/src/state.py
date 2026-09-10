"""
Cartographer — State Schema
The shared state object passed between all LangGraph nodes.
All fields are typed; nodes only write to their own output fields.
"""
from __future__ import annotations

from typing import Annotated, TypedDict
import operator


class SearchResult(TypedDict):
    url: str
    title: str
    content: str          # Cleaned snippet from Tavily
    score: float          # Tavily relevance score (0–1)
    published_date: str   # ISO date string or empty


class Source(TypedDict):
    url: str
    title: str
    citation_index: int   # [1], [2], … used inline in the report


class CartographerState(TypedDict):
    # ── Input ────────────────────────────────────────────────────────
    quest: str                                  # User's research question

    # ── Planner output ───────────────────────────────────────────────
    waypoints: list[str]                        # Sub-queries (3–5)

    # ── Explorer output ──────────────────────────────────────────────
    # Annotated with operator.add so each expedition APPENDS results
    terrain: Annotated[list[SearchResult], operator.add]

    # ── Critic output ────────────────────────────────────────────────
    coverage_score: float                       # 0–10
    uncharted_zones: list[str]                  # Gap topics for re-search
    expedition_count: int                       # How many Explorer runs so far

    # ── Writer output ────────────────────────────────────────────────
    treasure_map: str                           # Final Markdown report
    sources: list[Source]                       # Deduplicated cited sources

    # ── Execution trace (for Gradio Expedition Log) ──────────────────
    # Each entry: {"node": str, "message": str, "status": str}
    trace: Annotated[list[dict], operator.add]
