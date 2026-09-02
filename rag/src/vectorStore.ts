import fs from "fs";
import path from "path";
import { Document } from "@langchain/core/documents";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { GoogleGenerativeAIEmbeddings } from "@langchain/google-genai";
import { config } from "./config.js";

export interface FAQItem {
  id: string;
  intent: string;
  category: string;
  title: string;
  content: string;
}

let vectorStoreInstance: MemoryVectorStore | null = null;

export async function getVectorStore(): Promise<MemoryVectorStore> {
  if (vectorStoreInstance) {
    return vectorStoreInstance;
  }

  // Load dataset
  const kbPath = path.resolve(process.cwd(), "data", "bitext_kb_trimmed.json");
  const rawData = fs.readFileSync(kbPath, "utf-8");
  const items: FAQItem[] = JSON.parse(rawData);

  // Convert to LangChain Document abstractions
  const docs = items.map((item) => {
    return new Document({
      pageContent: `Category: ${item.category}\nTopic: ${item.title}\nPolicy/Resolution: ${item.content}`,
      metadata: {
        id: item.id,
        intent: item.intent,
        category: item.category,
        title: item.title,
      },
    });
  });

  const embeddings = new GoogleGenerativeAIEmbeddings({
    apiKey: config.apiKey,
    model: config.embeddingModel,
  });

  console.log(`[VectorStore] Ingesting ${docs.length} records into MemoryVectorStore...`);
  vectorStoreInstance = await MemoryVectorStore.fromDocuments(docs, embeddings);
  console.log("[VectorStore] Ingestion complete.");

  return vectorStoreInstance;
}
