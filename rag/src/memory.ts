import { BaseMessage, HumanMessage, AIMessage } from "@langchain/core/messages";

export interface ChatSession {
  id: string;
  messages: BaseMessage[];
  updatedAt: Date;
}

const sessions = new Map<string, ChatSession>();

export function getSession(sessionId: string): ChatSession {
  let session = sessions.get(sessionId);
  if (!session) {
    session = {
      id: sessionId,
      messages: [],
      updatedAt: new Date(),
    };
    sessions.set(sessionId, session);
  }
  return session;
}

export function clearSession(sessionId: string): boolean {
  return sessions.delete(sessionId);
}

export function addMessageToSession(sessionId: string, role: "human" | "ai", text: string): void {
  const session = getSession(sessionId);
  if (role === "human") {
    session.messages.push(new HumanMessage(text));
  } else {
    session.messages.push(new AIMessage(text));
  }
  session.updatedAt = new Date();

  // Keep last 10 messages for context efficiency
  if (session.messages.length > 10) {
    session.messages = session.messages.slice(-10);
  }
}

export function formatHistory(messages: BaseMessage[]): string {
  if (!messages || messages.length === 0) {
    return "No previous conversation.";
  }
  return messages
    .map((msg) => `${msg._getType() === "human" ? "Customer" : "Assistant"}: ${msg.content}`)
    .join("\n");
}
