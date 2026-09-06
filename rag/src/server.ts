import express, { Request, Response } from "express";
import cors from "cors";
import path from "path";
import rateLimit from "express-rate-limit";
import { config } from "./config.js";
import { askSupportAssistant, initRAGPipeline } from "./ragChain.js";
import { clearSession, createSession, getAllSessions, getSessionHistory } from "./memory.js";

import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicDir = path.resolve(__dirname, "public");

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.static(publicDir));

app.get("/", (_req: Request, res: Response) => {
  res.sendFile(path.join(publicDir, "index.html"));
});

// Rate limiting middleware
const chatLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute window
  max: 10, // max 10 requests per window
  message: { error: "Too many requests. Please try again later." },
});

// Chat endpoint with session support & rate limiting
app.post("/api/chat", chatLimiter, async (req: Request, res: Response): Promise<void> => {
  try {
    const { message, sessionId } = req.body;
    if (!message || typeof message !== "string") {
      res.status(400).json({ error: "Message is required and must be a string." });
      return;
    }

    if (message.length > 200) {
      res.status(400).json({ error: "Message exceeds maximum length of 200 characters." });
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

// Get all sessions
app.get("/api/sessions", (req: Request, res: Response) => {
  res.json({ sessions: getAllSessions() });
});

// Create new session directly
app.post("/api/sessions", (req: Request, res: Response) => {
  const { sessionId } = req.body || {};
  const session = createSession(sessionId);
  res.json({
    session: {
      id: session.id,
      updatedAt: session.updatedAt,
      preview: "New Chat",
    },
  });
});

// Get session history
app.get("/api/sessions/:id", (req: Request, res: Response) => {
  const history = getSessionHistory(req.params.id);
  res.json({ history });
});

// Delete a session
app.delete("/api/sessions/:id", (req: Request, res: Response) => {
  clearSession(req.params.id);
  res.json({ success: true, message: "Session deleted." });
});

// Clear session / reset memory endpoint (Legacy / alias)
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
