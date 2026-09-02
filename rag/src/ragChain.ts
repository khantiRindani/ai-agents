import {
  ChatPromptTemplate,
  SystemMessagePromptTemplate,
  HumanMessagePromptTemplate,
  MessagesPlaceholder,
} from "@langchain/core/prompts";
import { StringOutputParser } from "@langchain/core/output_parsers";
import { RunnableSequence } from "@langchain/core/runnables";
import { Document } from "@langchain/core/documents";
import { BaseMessage } from "@langchain/core/messages";
import { config } from "./config.js";
import { getVectorStore } from "./vectorStore.js";
import { getChatModel } from "./modelFactory.js";
import { getSession, addMessageToSession } from "./memory.js";

export interface RAGResponse {
  answer: string;
  sources: {
    id: string;
    category: string;
    title: string;
    excerpt: string;
  }[];
  sessionId: string;
}

const SYSTEM_INSTRUCTION = `You are a helpful, professional Customer Support Assistant.
Answer the customer's question directly based strictly on the provided Context and Conversation History.

Guidelines:
1. Do NOT start responses with generic greetings like "Hello!", "Hi there!", or conversational filler. Answer directly.
2. Be concise, clear, and structured. Use bullet points or short paragraphs where helpful.
3. Ground your response strictly in the provided Context. Never hallucinate policies or facts not in the context.
4. If the context does not contain the answer, state clearly that the information is unavailable and offer contact info for human support (Monday-Friday 8AM-8PM EST, support@example.com).`;

function formatDocs(docs: Document[]): string {
  return docs
    .map((doc, idx) => `[Doc ${idx + 1}] (${doc.metadata.title}):\n${doc.pageContent}`)
    .join("\n\n");
}

let ragChainInstance: RunnableSequence | null = null;
let retrieverInstance: any = null;

/**
 * Initializes the RAG pipeline once at boot (VectorStore retriever + Chat Model + LCEL Chain)
 */
export async function initRAGPipeline(): Promise<{
  chain: RunnableSequence;
  retriever: any;
}> {
  if (ragChainInstance && retrieverInstance) {
    return { chain: ragChainInstance, retriever: retrieverInstance };
  }

  console.log("[RAG] Initializing singleton model, vector store, and LCEL chain...");

  const vectorStore = await getVectorStore();
  retrieverInstance = vectorStore.asRetriever({ k: config.topK });
  const model = await getChatModel();

  const prompt = ChatPromptTemplate.fromMessages([
    SystemMessagePromptTemplate.fromTemplate(SYSTEM_INSTRUCTION),
    new MessagesPlaceholder("history"),
    HumanMessagePromptTemplate.fromTemplate(
      `Context Documents:\n{context}\n\nCustomer Question: {question}`
    ),
  ]);

  ragChainInstance = RunnableSequence.from([
    {
      context: (input: { docs: Document[]; history: BaseMessage[]; question: string }) =>
        formatDocs(input.docs),
      history: (input: { docs: Document[]; history: BaseMessage[]; question: string }) =>
        input.history,
      question: (input: { docs: Document[]; history: BaseMessage[]; question: string }) =>
        input.question,
    },
    prompt,
    model,
    new StringOutputParser(),
  ]);

  console.log("[RAG] Pipeline ready.");
  return { chain: ragChainInstance, retriever: retrieverInstance };
}

export async function askSupportAssistant(question: string, sessionId?: string): Promise<RAGResponse> {
  const currentSessionId = sessionId || `sess_${Date.now()}`;
  const session = getSession(currentSessionId);

  // Get initialized singleton pipeline
  const { chain, retriever } = await initRAGPipeline();

  // Retrieve relevant documents
  const retrievedDocs = await retriever.invoke(question);

  // Invoke stateless chain with dynamic input
  const answer = await chain.invoke({
    docs: retrievedDocs,
    history: session.messages,
    question,
  });

  // Record turn into session memory
  addMessageToSession(currentSessionId, "human", question);
  addMessageToSession(currentSessionId, "ai", answer);

  const sources = retrievedDocs.map((doc: Document) => ({
    id: (doc.metadata.id as string) || "doc",
    category: (doc.metadata.category as string) || "General",
    title: (doc.metadata.title as string) || "Support Document",
    excerpt: doc.pageContent,
  }));

  return {
    answer,
    sources,
    sessionId: currentSessionId,
  };
}
