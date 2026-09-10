"""
Cartographer — Explorer Node
"Explore the Terrain"

Runs parallel Tavily searches for each Waypoint (or Uncharted Zone on re-expeditions).
Appends results to state["terrain"] — using operator.add reducer.
"""
from __future__ import annotations

from src.state import CartographerState
from src.tools.search import parallel_search


async def explorer_node(state: CartographerState) -> dict:
    """
    Searches the web for all current Waypoints or Uncharted Zones.
    On first expedition: searches Waypoints.
    On re-expeditions: searches Uncharted Zones to fill coverage gaps.
    """
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

    new_results = await parallel_search(queries)

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
