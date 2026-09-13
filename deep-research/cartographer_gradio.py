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
        metadata = event.get("metadata", {})

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
        elif kind=="on_chat_model_stream" and metadata.get("langgraph_node") == "writer":
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
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

* { box-sizing: border-box; }

body, .gradio-container {
    background: radial-gradient(circle at 50% -10%, #1c1813 0%, #0d0c0a 55%, #080706 100%) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: #f3ede2 !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
}

/* Header */
.header-block {
    background: linear-gradient(135deg, rgba(38, 30, 20, 0.85) 0%, rgba(20, 17, 13, 0.95) 50%, rgba(33, 24, 15, 0.85) 100%);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(234, 179, 8, 0.28);
    border-radius: 20px;
    padding: 36px 44px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 16px 36px -12px rgba(0, 0, 0, 0.65), inset 0 1px 0 rgba(254, 240, 138, 0.15);
}
.header-block::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at 25% 35%, rgba(245, 158, 11, 0.15) 0%, transparent 55%),
                radial-gradient(ellipse at 75% 65%, rgba(217, 119, 6, 0.12) 0%, transparent 55%);
    pointer-events: none;
}

.badge-row {
    display: flex;
    gap: 10px;
    margin-bottom: 12px;
}
.tag-badge {
    background: rgba(245, 158, 11, 0.14);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #fde047;
    font-size: 0.74rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 999px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.tag-badge.secondary {
    background: rgba(217, 119, 6, 0.15);
    border-color: rgba(217, 119, 6, 0.4);
    color: #fdba74;
}

.app-title {
    font-family: 'Cinzel', serif !important;
    font-size: 2.7rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.02em !important;
    background: linear-gradient(135deg, #fef08a 0%, #f59e0b 50%, #d97706 100%);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    margin: 0 0 10px 0 !important;
}
.app-subtitle {
    color: #d1c7b7 !important;
    font-size: 1.02rem !important;
    font-weight: 400 !important;
    max-width: 860px;
    line-height: 1.65;
    margin: 0 !important;
}

/* Input area */
.quest-input textarea {
    background: rgba(24, 20, 15, 0.85) !important;
    border: 1px solid rgba(245, 158, 11, 0.28) !important;
    border-radius: 12px !important;
    color: #fefce8 !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
    padding: 14px 16px !important;
    transition: all 0.2s ease !important;
}
.quest-input textarea:focus {
    border-color: #f59e0b !important;
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2), 0 8px 24px rgba(0, 0, 0, 0.4) !important;
    background: rgba(28, 23, 17, 0.95) !important;
}
.quest-input label span {
    color: #fde047 !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.04em !important;
}

/* Buttons */
.explore-btn, .reset-btn {
    width: 100% !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    padding: 12px 20px !important;
    min-height: 46px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    cursor: pointer !important;
}

.explore-btn {
    background: linear-gradient(135deg, #b45309 0%, #d97706 60%, #f59e0b 100%) !important;
    border: 1px solid rgba(254, 240, 138, 0.35) !important;
    color: #1a1207 !important;
    box-shadow: 0 4px 16px rgba(217, 119, 6, 0.3) !important;
}
.explore-btn:hover {
    opacity: 0.95 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(245, 158, 11, 0.45) !important;
    color: #0d0903 !important;
}
.explore-btn:active { transform: translateY(0) !important; }

.reset-btn {
    background: rgba(245, 158, 11, 0.08) !important;
    border: 1px solid rgba(245, 158, 11, 0.25) !important;
    color: #fde68a !important;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25) !important;
}
.reset-btn:hover {
    background: rgba(245, 158, 11, 0.16) !important;
    color: #ffffff !important;
    border-color: rgba(245, 158, 11, 0.5) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 18px rgba(245, 158, 11, 0.2) !important;
}
.reset-btn:active { transform: translateY(0) !important; }

/* Expedition Log */
.expedition-log {
    background: rgba(18, 15, 11, 0.7) !important;
    border: 1px solid rgba(245, 158, 11, 0.2) !important;
    border-radius: 14px !important;
    padding: 22px !important;
    height: 520px !important;
    max-height: 520px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    scrollbar-width: thin;
    scrollbar-color: rgba(245, 158, 11, 0.35) rgba(18, 15, 11, 0.6);
}
.expedition-log::-webkit-scrollbar {
    width: 6px;
}
.expedition-log::-webkit-scrollbar-track {
    background: rgba(18, 15, 11, 0.6);
    border-radius: 8px;
}
.expedition-log::-webkit-scrollbar-thumb {
    background: rgba(245, 158, 11, 0.35);
    border-radius: 8px;
}
.expedition-log::-webkit-scrollbar-thumb:hover {
    background: rgba(245, 158, 11, 0.6);
}

.expedition-log .prose {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.86rem !important;
    line-height: 1.75 !important;
    color: #e5dac9 !important;
}
.expedition-log h3, .expedition-log h4 {
    color: #facc15 !important;
    margin-top: 14px !important;
    margin-bottom: 8px !important;
}
.expedition-log hr {
    border-color: rgba(245, 158, 11, 0.2) !important;
    margin: 16px 0 !important;
}

/* Treasure Map */
.treasure-map {
    background: rgba(20, 16, 12, 0.75) !important;
    border: 1px solid rgba(234, 179, 8, 0.28) !important;
    border-radius: 14px !important;
    padding: 28px 32px !important;
    height: 520px !important;
    max-height: 520px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    position: relative;
    scrollbar-width: thin;
    scrollbar-color: rgba(245, 158, 11, 0.35) rgba(20, 16, 12, 0.6);
}
.treasure-map::-webkit-scrollbar {
    width: 6px;
}
.treasure-map::-webkit-scrollbar-track {
    background: rgba(20, 16, 12, 0.6);
    border-radius: 8px;
}
.treasure-map::-webkit-scrollbar-thumb {
    background: rgba(245, 158, 11, 0.35);
    border-radius: 8px;
}
.treasure-map::-webkit-scrollbar-thumb:hover {
    background: rgba(245, 158, 11, 0.6);
}

.treasure-map .prose {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.98rem !important;
    line-height: 1.85 !important;
    color: #f7f1e6 !important;
}
.treasure-map h1, .treasure-map h2, .treasure-map h3 {
    color: #fde047 !important;
    font-family: 'Cinzel', serif !important;
    letter-spacing: 0.01em;
    border-bottom: 1px solid rgba(245, 158, 11, 0.25);
    padding-bottom: 8px;
    margin-top: 24px;
    margin-bottom: 14px;
}
.treasure-map blockquote {
    border-left: 3px solid #f59e0b !important;
    background: rgba(245, 158, 11, 0.08) !important;
    padding: 12px 18px !important;
    border-radius: 0 8px 8px 0 !important;
    color: #fef08a !important;
}
.treasure-map table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
}
.treasure-map th, .treasure-map td {
    border: 1px solid rgba(245, 158, 11, 0.25);
    padding: 8px 12px;
}
.treasure-map th {
    background: rgba(245, 158, 11, 0.12);
    color: #fde047;
}

/* Panel Header */
.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(245, 158, 11, 0.15);
}
.panel-title {
    font-size: 0.92rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    display: flex;
    align-items: center;
    gap: 8px;
}
.log-title { color: #facc15; }
.map-title { color: #fbbf24; }

/* Examples */
#example-quests .label-wrap span {
    color: #fde047 !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
}
#example-quests button {
    background: rgba(245, 158, 11, 0.07) !important;
    border: 1px solid rgba(245, 158, 11, 0.22) !important;
    color: #fde68a !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    padding: 6px 12px !important;
    transition: all 0.2s ease !important;
}
#example-quests button:hover {
    background: rgba(245, 158, 11, 0.18) !important;
    border-color: rgba(245, 158, 11, 0.45) !important;
    color: #ffffff !important;
    transform: translateY(-1px) !important;
}

/* Footer */
.app-footer {
    text-align: center;
    padding: 26px 0 14px 0;
    color: #8c7f6e;
    font-size: 0.82rem;
}
.app-footer a {
    color: #facc15;
    text-decoration: none;
}
.app-footer a:hover { text-decoration: underline; }
"""

EXAMPLE_QUESTS = [
    "What are the trade-offs between vector databases for production RAG systems?",
    "What are the key risks and mitigation strategies for deploying LLMs in healthcare?",
    "How do leading AI companies approach AI safety and alignment in 2025?",
    "What is the current state of quantum computing and its practical applications?",
    "Compare serverless vs. container-based architectures for modern web applications.",
]

with gr.Blocks(title="Cartographer 🗺️ — Deep Research Agent") as demo:

    # ── Header ────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="header-block">
        <div class="badge-row">
            <span class="tag-badge">🧭 LangGraph Agent</span>
            <span class="tag-badge secondary">📜 Cartography Engine</span>
        </div>
        <h1 class="app-title">🗺️ Cartographer</h1>
        <p class="app-subtitle">Autonomous deep research engine. Submit your quest to formulate hypotheses, traverse sources, critique coverage, and chart a synthesized treasure map with verified citations.</p>
    </div>
    """)

    # ── Quest Input ───────────────────────────────────────────────────
    with gr.Row():
        with gr.Column(scale=5):
            quest_input = gr.Textbox(
                label="🧭 The Quest",
                placeholder="What do you want to deeply research? Ask anything complex…",
                lines=3,
                elem_classes=["quest-input"],
            )
        with gr.Column(scale=1, min_width=150):
            explore_btn = gr.Button("🔍 Explore", variant="primary", elem_classes=["explore-btn"])
            clear_btn = gr.Button("🧹 Reset", variant="secondary", elem_classes=["reset-btn"])

    # ── Example Quests ────────────────────────────────────────────────
    gr.Examples(
        examples=[[q] for q in EXAMPLE_QUESTS],
        inputs=[quest_input],
        label="📌 Example Quests",
        elem_id="example-quests",
    )

    gr.HTML("<hr style='border-color: rgba(245,158,11,0.15); margin: 20px 0;'>")

    # ── Output Panels (Fixed Height & Internal Vertical Scroll) ───────
    with gr.Row(equal_height=True):
        with gr.Column(scale=1):
            gr.HTML("""
            <div class="panel-header">
                <span class="panel-title log-title">📍 Expedition Log</span>
                <span style="font-size: 0.75rem; color: #a89f91;">Node Events</span>
            </div>
            """)
            expedition_log = gr.Markdown(
                value="*Awaiting Quest… Click **Explore** or pick an example above.*",
                elem_classes=["expedition-log"],
            )
        with gr.Column(scale=2):
            gr.HTML("""
            <div class="panel-header">
                <span class="panel-title map-title">📜 Treasure Map</span>
                <span style="font-size: 0.75rem; color: #a89f91;">Live Streamed Report</span>
            </div>
            """)
            treasure_map = gr.Markdown(
                value="*The synthesized map with inline citations will stream here as the Writer node executes…*",
                elem_classes=["treasure-map"],
            )

    # ── Footer ────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="app-footer">
        Cartographer • Autonomous Research Agent with LangGraph & Gradio • Grounded in Tavily Search
    </div>
    """)

    # ── Wire up streaming & resets ────────────────────────────────────
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

    def reset_view():
        return "", "*Awaiting Quest…*", "*The map will appear here once the expedition is complete…*"

    clear_btn.click(
        fn=reset_view,
        inputs=[],
        outputs=[quest_input, expedition_log, treasure_map],
    )


if __name__ == "__main__":
    demo.queue()  # Required for streaming
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        css=CUSTOM_CSS,
    )
