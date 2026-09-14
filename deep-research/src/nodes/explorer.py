"""
Cartographer — Explorer Node
"Explore the Terrain"

Runs parallel Tavily searches for each Waypoint (or Uncharted Zone on re-expeditions).
Appends results to state["terrain"] — using operator.add reducer.
"""
from __future__ import annotations

import time

from src.logger import logger
from src.state import CartographerState
from src.tools.search import parallel_search


async def explorer_node(state: CartographerState) -> dict:
    """
    Searches the web for all current Waypoints or Uncharted Zones.
    On first expedition: searches Waypoints.
    On re-expeditions: searches Uncharted Zones to fill coverage gaps.
    """
    t0 = time.perf_counter()
    expedition_count = state.get("expedition_count", 0)
    is_reexpedition = expedition_count > 0 and bool(state.get("uncharted_zones"))

    if is_reexpedition:
        queries = state["uncharted_zones"]
        label = f"Re-Expedition #{expedition_count}"
        log_prefix = "🔁"
    else:
        queries = state["waypoints"]
        label = "Expedition #1"
        log_prefix = "🔍"

    logger.info(f"[Explorer] Starting {label} for {len(queries)} queries: {queries}")
    new_results = await parallel_search(queries)
    duration_ms = (time.perf_counter() - t0) * 1000
    logger.info(f"[Explorer] {label} completed in {duration_ms:.1f}ms with {len(new_results)} new results")

    trace_entry = {
        "node": "explorer",
        "status": "done",
        "message": (
            f"{log_prefix} **{label}** complete — "
            f"searched {len(queries)} {'zone(s)' if is_reexpedition else 'waypoint(s)'}, "
            f"found {len(new_results)} new results"
        ),
    }

    return {
        "terrain": new_results,          # operator.add appends to existing terrain
        "expedition_count": expedition_count + 1,
        "trace": [trace_entry],
    }
