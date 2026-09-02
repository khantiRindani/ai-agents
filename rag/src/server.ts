import express, { Request, Response } from "express";
import cors from "cors";
import path from "path";
import { config } from "./config.js";
import { askSupportAssistant, initRAGPipeline } from "./ragChain.js";
import { clearSession } from "./memory.js";

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.static(path.resolve(process.cwd(), "src", "public")));

// Chat endpoint with session support
app.post("/api/chat", async (req: Request, res: Response): Promise<void> => {
  try {
    const { message, sessionId } = req.body;
    if (!message || typeof message !== "string") {
      res.status(400).json({ error: "Message is required and must be a string." });
      return;
    }

    const response = await askSupportAssistant(message, sessionId);
    res.json(response);
  } catch (error: any) {
    console.error("[API Error]:", error);
    res.status(500).json({
      error: error?.message || "An unexpected error occurred while processing your request.",
    });
  }
});

// Clear session / reset memory endpoint
app.post("/api/chat/clear", (req: Request, res: Response): void => {
  const { sessionId } = req.body;
  if (sessionId) {
    clearSession(sessionId);
  }
  res.json({ success: true, message: "Session memory cleared." });
});

// Health check endpoint
app.get("/api/health", (_req: Request, res: Response) => {
  res.json({ status: "healthy", timestamp: new Date().toISOString() });
});

// Warm up vector store, model, and chain once at startup
async function startServer() {
  try {
    console.log("[Server] Warming up RAG pipeline (Model + VectorStore + Chain)...");
    await initRAGPipeline();

    app.listen(config.port, () => {
      console.log(`\n Customer Support AI Assistant is running at: http://localhost:${config.port}`);
    });
  } catch (err) {
    console.error("[Server] Failed to initialize:", err);
    process.exit(1);
  }
}

startServer();
