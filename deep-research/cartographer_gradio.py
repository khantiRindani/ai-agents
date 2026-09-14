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
import time
from src.graph import cartographer
from src.logger import logger

# ── Streaming runner ──────────────────────────────────────────────────────────

async def run_cartographer(quest: str):
    """
    Async generator that yields (expedition_log, treasure_map) tuples
    as the graph runs. Gradio's queue + async generator handles live updates.
    """
    quest_clean = quest.strip()
    if not quest_clean:
        logger.info("[UI] Empty quest submitted.")
        yield "Please enter a Quest to begin.", ""
        return

    t_start = time.perf_counter()
    logger.info(f"[UI] Starting Cartographer quest: {quest_clean!r}")

    expedition_log = ""
    treasure_map = ""
    writer_streaming = False

    initial_state = {
        "quest": quest_clean,
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

    try:
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
            elif kind == "on_chat_model_stream" and metadata.get("langgraph_node") == "writer":
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
                total_duration = time.perf_counter() - t_start
                logger.info(
                    f"[UI] Quest complete in {total_duration:.2f}s | "
                    f"Score: {score:.1f}/10 | Sources: {len(sources)}"
                )
                expedition_log += (
                    f"\n---\n✅ **Expedition complete!** "
                    f"Coverage: **{score:.1f}/10** | "
                    f"Sources: **{len(sources)}** | "
                    f"Time: **{total_duration:.1f}s**"
                )
                yield expedition_log, treasure_map
    except Exception as exc:
        logger.exception(f"[UI] Error during Cartographer execution: {exc}")
        expedition_log += f"\n\n❌ **Error during expedition**: {exc}"
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

:root {
    --bg-page: radial-gradient(circle at 50% -10%, #faf6f0 0%, #f3ede2 55%, #eae1d2 100%);
    --bg-header: linear-gradient(135deg, rgba(255, 252, 245, 0.95) 0%, rgba(246, 239, 226, 0.95) 50%, rgba(254, 243, 199, 0.85) 100%);
    --bg-card: rgba(255, 255, 255, 0.85);
    --bg-card-subtle: rgba(246, 239, 226, 0.7);
    --bg-input: #ffffff;
    --border-accent: rgba(180, 83, 9, 0.35);
    --border-subtle: rgba(180, 83, 9, 0.18);
    --text-primary: #2d2417;
    --text-secondary: #5c4e3a;
    --text-muted: #786954;
    --accent-gold: #b45309;
    --accent-bright: #92400e;
    --badge-bg: rgba(180, 83, 9, 0.1);
    --badge-text: #92400e;
    --badge-border: rgba(180, 83, 9, 0.3);
    --code-bg: rgba(180, 83, 9, 0.06);
    --btn-primary-bg: linear-gradient(135deg, #b45309 0%, #d97706 60%, #f59e0b 100%);
    --btn-primary-text: #ffffff;
    --btn-sec-bg: rgba(180, 83, 9, 0.08);
    --btn-sec-text: #78350f;
    --btn-sec-border: rgba(180, 83, 9, 0.25);
    --scrollbar-thumb: rgba(180, 83, 9, 0.3);
}

.dark, body.dark, .gradio-container.dark {
    --bg-page: radial-gradient(circle at 50% -10%, #1c1813 0%, #0d0c0a 55%, #080706 100%);
    --bg-header: linear-gradient(135deg, rgba(38, 30, 20, 0.85) 0%, rgba(20, 17, 13, 0.95) 50%, rgba(33, 24, 15, 0.85) 100%);
    --bg-card: rgba(20, 16, 12, 0.85);
    --bg-card-subtle: rgba(18, 15, 11, 0.8);
    --bg-input: rgba(24, 20, 15, 0.85);
    --border-accent: rgba(234, 179, 8, 0.32);
    --border-subtle: rgba(245, 158, 11, 0.2);
    --text-primary: #f5eedf;
    --text-secondary: #d1c7b7;
    --text-muted: #9c8e7c;
    --accent-gold: #f59e0b;
    --accent-bright: #fde047;
    --badge-bg: rgba(245, 158, 11, 0.14);
    --badge-text: #fde047;
    --badge-border: rgba(245, 158, 11, 0.35);
    --code-bg: rgba(245, 158, 11, 0.08);
    --btn-primary-bg: linear-gradient(135deg, #b45309 0%, #d97706 60%, #f59e0b 100%);
    --btn-primary-text: #1a1207;
    --btn-sec-bg: rgba(245, 158, 11, 0.08);
    --btn-sec-text: #fde68a;
    --btn-sec-border: rgba(245, 158, 11, 0.25);
    --scrollbar-thumb: rgba(245, 158, 11, 0.35);
}

* { box-sizing: border-box; }

body, .gradio-container {
    background: var(--bg-page) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: var(--text-primary) !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
}

/* Header */
.header-block {
    background: var(--bg-header);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid var(--border-accent);
    border-radius: 20px;
    padding: 36px 44px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 16px 36px -12px rgba(0, 0, 0, 0.35);
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
    background: var(--badge-bg);
    border: 1px solid var(--badge-border);
    color: var(--badge-text);
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
    background: var(--badge-bg);
    border-color: var(--badge-border);
    color: var(--badge-text);
}

.app-title {
    font-family: 'Cinzel', serif !important;
    font-size: 2.7rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.02em !important;
    background: linear-gradient(135deg, #b45309 0%, #d97706 50%, #f59e0b 100%);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    margin: 0 0 10px 0 !important;
}
.dark .app-title {
    background: linear-gradient(135deg, #fef08a 0%, #f59e0b 50%, #d97706 100%);
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
}
.app-subtitle {
    color: var(--text-secondary) !important;
    font-size: 1.02rem !important;
    font-weight: 400 !important;
    max-width: 860px;
    line-height: 1.65;
    margin: 0 !important;
}

/* Input area */
.quest-input textarea {
    background: var(--bg-input) !important;
    border: 1px solid var(--border-accent) !important;
    border-radius: 12px !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 1rem !important;
    line-height: 1.6 !important;
    padding: 14px 16px !important;
    transition: all 0.2s ease !important;
}
.quest-input textarea:focus {
    border-color: var(--accent-gold) !important;
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2), 0 8px 24px rgba(0, 0, 0, 0.15) !important;
}
.quest-input label span {
    color: var(--accent-gold) !important;
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
    background: var(--btn-primary-bg) !important;
    border: 1px solid var(--border-accent) !important;
    color: var(--btn-primary-text) !important;
    box-shadow: 0 4px 16px rgba(217, 119, 6, 0.25) !important;
}
.explore-btn:hover {
    opacity: 0.95 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(245, 158, 11, 0.35) !important;
}
.explore-btn:active { transform: translateY(0) !important; }

.reset-btn {
    background: var(--btn-sec-bg) !important;
    border: 1px solid var(--btn-sec-border) !important;
    color: var(--btn-sec-text) !important;
}
.reset-btn:hover {
    background: var(--btn-sec-bg) !important;
    filter: brightness(1.15) !important;
    transform: translateY(-2px) !important;
}
.reset-btn:active { transform: translateY(0) !important; }

/* Expedition Log */
.expedition-log {
    background: var(--bg-card-subtle) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 14px !important;
    padding: 22px !important;
    height: 520px !important;
    max-height: 520px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    scrollbar-width: thin;
    scrollbar-color: var(--scrollbar-thumb) transparent;
}
.expedition-log::-webkit-scrollbar {
    width: 6px;
}
.expedition-log::-webkit-scrollbar-track {
    background: transparent;
}
.expedition-log::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 8px;
}

.expedition-log .prose {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.86rem !important;
    line-height: 1.75 !important;
    color: var(--text-primary) !important;
}
.expedition-log h3, .expedition-log h4 {
    color: var(--accent-gold) !important;
    margin-top: 14px !important;
    margin-bottom: 8px !important;
}
.expedition-log hr {
    border-color: var(--border-subtle) !important;
    margin: 16px 0 !important;
}

/* Treasure Map */
.treasure-map {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-accent) !important;
    border-radius: 14px !important;
    padding: 28px 32px !important;
    height: 520px !important;
    max-height: 520px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    position: relative;
    scrollbar-width: thin;
    scrollbar-color: var(--scrollbar-thumb) transparent;
}
.treasure-map::-webkit-scrollbar {
    width: 6px;
}
.treasure-map::-webkit-scrollbar-track {
    background: transparent;
}
.treasure-map::-webkit-scrollbar-thumb {
    background: var(--scrollbar-thumb);
    border-radius: 8px;
}

.treasure-map .prose {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.98rem !important;
    line-height: 1.85 !important;
    color: var(--text-primary) !important;
}
.treasure-map h1, .treasure-map h2, .treasure-map h3 {
    color: var(--accent-bright) !important;
    font-family: 'Cinzel', serif !important;
    letter-spacing: 0.01em;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 8px;
    margin-top: 24px;
    margin-bottom: 14px;
}
.treasure-map blockquote {
    border-left: 3px solid var(--accent-gold) !important;
    background: var(--code-bg) !important;
    padding: 12px 18px !important;
    border-radius: 0 8px 8px 0 !important;
    color: var(--text-primary) !important;
}
.treasure-map table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
}
.treasure-map th, .treasure-map td {
    border: 1px solid var(--border-subtle);
    padding: 8px 12px;
}
.treasure-map th {
    background: var(--badge-bg);
    color: var(--accent-gold);
}

/* Panel Header */
.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-subtle);
}
.panel-title {
    font-size: 0.92rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--accent-gold);
}
.log-title { color: var(--accent-gold); }
.map-title { color: var(--accent-bright); }

/* Examples */
#example-quests .label-wrap span {
    color: var(--accent-gold) !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
}
#example-quests button {
    background: var(--btn-sec-bg) !important;
    border: 1px solid var(--btn-sec-border) !important;
    color: var(--btn-sec-text) !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    padding: 6px 12px !important;
    transition: all 0.2s ease !important;
}
#example-quests button:hover {
    filter: brightness(1.15) !important;
    transform: translateY(-1px) !important;
}

/* Footer */
.app-footer {
    text-align: center;
    padding: 26px 0 14px 0;
    color: var(--text-muted);
    font-size: 0.82rem;
}
.app-footer a {
    color: var(--accent-gold);
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
