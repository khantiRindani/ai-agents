import dotenv from "dotenv";
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || "3000", 10),
  apiKey: process.env.API_KEY || "",
  modelProvider: process.env.MODEL_PROVIDER || "google-genai",
  chatModel: process.env.CHAT_MODEL || "gemini-3.6-flash",
  embeddingModel: process.env.EMBEDDING_MODEL || "gemini-embedding-001",
  topK: parseInt(process.env.RAG_TOP_K || "3", 10),
};
