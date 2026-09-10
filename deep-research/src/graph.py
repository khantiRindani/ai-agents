"""
Cartographer — LangGraph StateGraph
Wires all nodes together with conditional edges for the critic re-expedition loop.

Graph topology:
    planner → explorer → critic ──(score < threshold AND expeditions < max)──► explorer
                                └──(score >= threshold OR expeditions >= max)──► writer → END
"""
from __future__ import annotations

import os

from langgraph.graph import StateGraph, END

from src.state import CartographerState
from src.nodes.planner import planner_node
from src.nodes.explorer import explorer_node
from src.nodes.critic import critic_node
from src.nodes.writer import writer_node


def _should_reexpedite(state: CartographerState) -> str:
    """
    Conditional edge: decides whether to re-expedite or proceed to the writer.

    Returns:
        "explorer" — if coverage is low and max expeditions not reached
        "writer"   — if coverage is sufficient or max expeditions reached
    """
    score = state.get("coverage_score", 0.0)
    count = state.get("expedition_count", 0)
    threshold = float(os.getenv("CRITIC_SCORE_THRESHOLD", "7.0"))
    max_expeditions = int(os.getenv("MAX_EXPEDITIONS", "2"))

    if score < threshold and count < max_expeditions and state.get("uncharted_zones"):
        return "explorer"
    return "writer"


def build_graph() -> StateGraph:
    """Builds and compiles the Cartographer LangGraph."""
    graph = StateGraph(CartographerState)

    # Register nodes
    graph.add_node("planner", planner_node)
    graph.add_node("explorer", explorer_node)
    graph.add_node("critic", critic_node)
    graph.add_node("writer", writer_node)

    # Entry point
    graph.set_entry_point("planner")

    # Edges
    graph.add_edge("planner", "explorer")
    graph.add_edge("explorer", "critic")

    # Conditional: critic → explorer (re-expedite) OR critic → writer (done)
    graph.add_conditional_edges(
        "critic",
        _should_reexpedite,
        {
            "explorer": "explorer",
            "writer": "writer",
        },
    )

    graph.add_edge("writer", END)

    return graph.compile()


# Singleton — import this in the notebook and Gradio app
cartographer = build_graph()
