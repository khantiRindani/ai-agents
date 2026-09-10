"""
Cartographer — Gradio UI
🗺️ "Submit your Quest. Receive the Treasure Map."

Streaming architecture:
- graph.astream_events(input, version="v2") streams per-node AND per-token events
- Expedition Log panel: updates after each node completes
- Treasure Map panel: streams tokens live as the Writer node runs
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure src/ is importable when running from project root
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from src.graph import cartographer

# ── Streaming runner ──────────────────────────────────────────────────────────

async def run_cartographer(quest: str):
    """
    Async generator that yields (expedition_log, treasure_map) tuples
    as the graph runs. Gradio's queue + async generator handles live updates.
    """
    if not quest.strip():
        yield "Please enter a Quest to begin.", ""
        return

    expedition_log = ""
    treasure_map = ""
    writer_streaming = False

    initial_state = {
        "quest": quest,
        "waypoints": [],
        "terrain": [],
        "uncharted_zones": [],
        "coverage_score": 0.0,
        "expedition_count": 0,
        "treasure_map": "",
        "sources": [],
        "trace": [],
    }

    # Emit initial status
    expedition_log = "🧭 **Cartographer activated.** Charting the territory…\n\n"
    yield expedition_log, ""

    async for event in cartographer.astream_events(initial_state, version="v2"):
        kind = event["event"]
        name = event.get("name", "")

        # ── Node completed → update Expedition Log ────────────────────
        if kind == "on_chain_end" and name in ("planner", "explorer", "critic", "writer"):
            output = event.get("data", {}).get("output", {})
            trace = output.get("trace", [])
            for entry in trace:
                icon_map = {
                    "planner": "📍",
                    "explorer": "🔍",
                    "critic": "⚖️",
                    "writer": "🗺️",
                }
                icon = icon_map.get(entry.get("node", ""), "•")
                expedition_log += f"{icon} {entry['message']}\n\n"
            yield expedition_log, treasure_map

        # ── LLM streaming tokens (Writer node only) ───────────────────
        elif kind == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content") and chunk.content:
                if not writer_streaming:
                    writer_streaming = True
                    expedition_log += "📝 *Writing Treasure Map…*\n\n"
                treasure_map += chunk.content
                yield expedition_log, treasure_map

        # ── Final state (graph END) ───────────────────────────────────
        elif kind == "on_chain_end" and name == "LangGraph":
            final = event.get("data", {}).get("output", {})
            score = final.get("coverage_score", 0.0)
            sources = final.get("sources", [])
            expedition_log += (
                f"\n---\n✅ **Expedition complete!** "
                f"Coverage: **{score:.1f}/10** | "
                f"Sources: **{len(sources)}**"
            )
            yield expedition_log, treasure_map


def run_sync(quest: str):
    """Sync wrapper for Gradio — delegates to async generator."""
    loop = asyncio.new_event_loop()
    gen = run_cartographer(quest)

    async def collect():
        async for log, map_ in gen:
            yield log, map_

    # Use Gradio's native async support — this wrapper satisfies Gradio's generator interface
    return gen


# ── Gradio UI ─────────────────────────────────────────────────────────────────

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

* { box-sizing: border-box; }

body, .gradio-container {
    background: #0a0e1a !important;
    font-family: 'Inter', sans-serif !important;
}

/* Header */
.header-block {
    background: linear-gradient(135deg, #1a1f35 0%, #0f1424 50%, #1a2040 100%);
    border: 1px solid rgba(99, 179, 237, 0.2);
    border-radius: 16px;
    padding: 32px 40px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.header-block::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 30% 40%, rgba(99, 179, 237, 0.06) 0%, transparent 60%),
                radial-gradient(ellipse at 70% 60%, rgba(167, 139, 250, 0.06) 0%, transparent 60%);
    pointer-events: none;
}

.app-title {
    font-size: 2.4rem !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #63b3ed, #a78bfa, #f6ad55);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    margin: 0 0 8px 0 !important;
}
.app-subtitle {
    color: #718096 !important;
    font-size: 1rem !important;
    font-style: italic !important;
    margin: 0 !important;
}

/* Input area */
.quest-input textarea {
    background: #111827 !important;
    border: 1px solid rgba(99, 179, 237, 0.3) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    transition: border-color 0.2s !important;
}
.quest-input textarea:focus {
    border-color: #63b3ed !important;
    box-shadow: 0 0 0 3px rgba(99, 179, 237, 0.1) !important;
}
.quest-input label {
    color: #a0aec0 !important;
    font-weight: 500 !important;
}

/* Explore button */
.explore-btn {
    background: linear-gradient(135deg, #3182ce, #6b46c1) !important;
    border: none !important;
    border-radius: 10px !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 12px 32px !important;
    transition: opacity 0.2s, transform 0.1s !important;
    cursor: pointer !important;
}
.explore-btn:hover { opacity: 0.9 !important; transform: translateY(-1px) !important; }
.explore-btn:active { transform: translateY(0) !important; }

/* Expedition Log */
.expedition-log textarea, .expedition-log .output-markdown {
    background: #0d1117 !important;
    border: 1px solid rgba(99, 179, 237, 0.15) !important;
    border-radius: 10px !important;
    color: #cbd5e0 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    line-height: 1.7 !important;
}
.expedition-log label, .treasure-map label {
    color: #63b3ed !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* Treasure Map */
.treasure-map textarea, .treasure-map .output-markdown {
    background: #0d1117 !important;
    border: 1px solid rgba(167, 139, 250, 0.2) !important;
    border-radius: 10px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    line-height: 1.8 !important;
}

/* Panel labels */
.panel-label {
    color: #63b3ed;
    font-size: 0.85rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}

/* Example quests */
.example-btn button {
    background: rgba(99, 179, 237, 0.08) !important;
    border: 1px solid rgba(99, 179, 237, 0.2) !important;
    color: #90cdf4 !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    transition: all 0.2s !important;
}
.example-btn button:hover {
    background: rgba(99, 179, 237, 0.15) !important;
    border-color: rgba(99, 179, 237, 0.4) !important;
}

/* General dark overrides */
.gradio-container .prose { color: #e2e8f0 !important; }
.label-wrap span { color: #a0aec0 !important; }
"""

EXAMPLE_QUESTS = [
    "What are the trade-offs between vector databases for production RAG systems?",
    "What are the key risks and mitigation strategies for deploying LLMs in healthcare?",
    "How do leading AI companies approach AI safety and alignment in 2025?",
    "What is the current state of quantum computing and its practical applications?",
    "Compare serverless vs. container-based architectures for modern web applications.",
]

with gr.Blocks(css=CUSTOM_CSS, title="Cartographer 🗺️ — Deep Research Agent") as demo:

    # ── Header ────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="header-block">
        <h1 class="app-title">🗺️ Cartographer</h1>
        <p class="app-subtitle">Submit your Quest. The agent plans, explores, critiques, and draws the Treasure Map.</p>
    </div>
    """)

    # ── Quest Input ───────────────────────────────────────────────────
    with gr.Row():
        with gr.Column(scale=5):
            quest_input = gr.Textbox(
                label="🧭 The Quest",
                placeholder="What do you want to deeply research? Ask anything…",
                lines=2,
                elem_classes=["quest-input"],
            )
        with gr.Column(scale=1, min_width=140):
            explore_btn = gr.Button("🔍 Explore", variant="primary", elem_classes=["explore-btn"])

    # ── Example Quests ────────────────────────────────────────────────
    gr.Examples(
        examples=[[q] for q in EXAMPLE_QUESTS],
        inputs=[quest_input],
        label="📌 Example Quests",
        elem_id="example-quests",
    )

    gr.HTML("<hr style='border-color: rgba(99,179,237,0.1); margin: 16px 0;'>")

    # ── Output Panels ─────────────────────────────────────────────────
    with gr.Row(equal_height=True):
        with gr.Column(scale=1):
            expedition_log = gr.Markdown(
                label="📍 Expedition Log",
                value="*Awaiting Quest…*",
                elem_classes=["expedition-log"],
            )
        with gr.Column(scale=2):
            treasure_map = gr.Markdown(
                label="📜 Treasure Map",
                value="*The map will appear here once the expedition is complete…*",
                elem_classes=["treasure-map"],
            )

    # ── Wire up streaming ─────────────────────────────────────────────
    explore_btn.click(
        fn=run_cartographer,
        inputs=[quest_input],
        outputs=[expedition_log, treasure_map],
    )
    quest_input.submit(
        fn=run_cartographer,
        inputs=[quest_input],
        outputs=[expedition_log, treasure_map],
    )


if __name__ == "__main__":
    demo.queue()  # Required for streaming
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )
