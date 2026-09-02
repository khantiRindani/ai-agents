# Customer Support AI Assistant (RAG + LangChain + Gemini)

A clean, portfolio-ready **Customer Support AI Assistant** featuring Retrieval-Augmented Generation (RAG) built with **LangChain.js**, **Google Gemini**, and a lightweight **Preact** frontend.

---

## 🌟 Key Architecture & Design Choices

- **Universal / Model-Agnostic LLM Layer**: Chat generation leverages LangChain's universal `initChatModel()` in `src/modelFactory.ts`, allowing models/providers to be swapped dynamically via configuration without modifying business logic.
- **Embeddings Layer Note**: Unlike chat models, LangChain.js does not currently offer a universal `initEmbeddings()` helper in `@langchain/core`, so embeddings are implemented directly via `@langchain/google-genai` (`GoogleGenerativeAIEmbeddings`) adhering to `@langchain/core/embeddings` (`EmbeddingsInterface`).
- **In-Memory Vector Store**: `SimpleMemoryVectorStore` extending `@langchain/core/vectorstores` (`VectorStore`) implementing exact cosine similarity retrieval without external database dependencies.
- **Curated Bitext Knowledge Base**: Compact starter dataset spanning order tracking, cancellations, returns & refunds, payment methods, and shipping policies.
- **Conversational Memory & Reset**: In-memory multi-turn conversation tracking with a "New Chat" session reset.
- **Lightweight Preact Frontend**: Modern UI using Preact + HTM via ESM (no heavy bundler required) with markdown formatting (`marked.js`), preset prompt chips, and cited source drawers.

---

## 🚀 Quickstart

### 1. Configure Environment (`.env`)
```env
API_KEY=your_gemini_api_key_here
PORT=3000
MODEL_PROVIDER=google-genai
CHAT_MODEL=gemini-3.6-flash
EMBEDDING_MODEL=gemini-embedding-001
```

### 2. Run the Development Server
```bash
pnpm dev
# or
npm run dev
```

Visit **http://localhost:3000** in your browser.
