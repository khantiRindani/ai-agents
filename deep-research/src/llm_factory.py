"""
Cartographer — LLM Factory
Builds a LangChain BaseChatModel from environment config.
Swap providers by changing CARTOGRAPHER_LLM_PROVIDER in .env — no code changes needed.
"""
from __future__ import annotations

import os
from langchain_core.language_models import BaseChatModel


def build_llm(
    provider: str | None = None,
    model: str | None = None,
    streaming: bool = True,
    temperature: float = 0.2,
) -> BaseChatModel:
    """
    Factory that returns a LangChain chat model.

    Priority: explicit args → env vars → defaults (Gemini Flash).

    Args:
        provider:    "google" | "anthropic" | "openai"
        model:       Provider-specific model string
        streaming:   Enable token streaming (default True)
        temperature: Sampling temperature

    Returns:
        Configured BaseChatModel instance
    """
    provider = (provider or os.getenv("CARTOGRAPHER_LLM_PROVIDER", "google")).lower()
    model = model or os.getenv("CARTOGRAPHER_LLM_MODEL")

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.0-flash",
            temperature=temperature,
            streaming=streaming,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-3-haiku-20240307",
            temperature=temperature,
            streaming=streaming,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            temperature=temperature,
            streaming=streaming,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model or "gemma3:4b",
            temperature=temperature,
            streaming=streaming,
            base_url=os.getenv("OLLAMA_API_URL")
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            "Set CARTOGRAPHER_LLM_PROVIDER to 'google', 'anthropic', or 'openai'."
        )
