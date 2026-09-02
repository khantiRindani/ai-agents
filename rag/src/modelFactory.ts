import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { initChatModel } from "langchain/chat_models/universal";
import { config } from "./config.js";

let chatModelInstance: BaseChatModel | null = null;

/**
 * Vendor-agnostic Chat Model factory (Singleton).
 * Initializes model instance once and reuses across API calls.
 */
export async function getChatModel(): Promise<BaseChatModel> {
  if (chatModelInstance) {
    return chatModelInstance;
  }

  chatModelInstance = await initChatModel(config.chatModel, {
    modelProvider: config.modelProvider,
    apiKey: config.apiKey,
    temperature: 0.2,
  });

  return chatModelInstance;
}
