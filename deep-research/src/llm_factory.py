"""
Cartographer — LLM Factory
Builds a LangChain BaseChatModel from environment config.
Swap providers by changing CARTOGRAPHER_LLM_PROVIDER in .env — no code changes needed.
"""
from __future__ import annotations

import os
from langchain_core.language_models import BaseChatModel

from src.logger import logger


def build_llm(
    provider: str | None = None,
    model: str | None = None,
    streaming: bool = True,
    temperature: float = 0.2,
) -> BaseChatModel:
    """
    Factory that returns a LangChain chat model.

    Priority: explicit args → env vars → defaults (Gemini Flash or Ollama if configured).

    Args:
        provider:    "google" | "anthropic" | "openai" | "ollama"
        model:       Provider-specific model string
        streaming:   Enable token streaming (default True)
        temperature: Sampling temperature

    Returns:
        Configured BaseChatModel instance
    """
    provider = (provider or os.getenv("CARTOGRAPHER_LLM_PROVIDER", "google")).strip().lower()
    model = model or os.getenv("CARTOGRAPHER_LLM_MODEL")
    if model:
        # Strip any trailing comments if present in env (e.g. "model"#comment)
        model = model.split("#")[0].strip().strip('"').strip("'")

    logger.debug(f"[LLMFactory] Building LLM: provider={provider}, model={model}, streaming={streaming}, temp={temperature}")

    if provider == "google":
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY is not set. Add it to your .env file or choose another provider.")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model or "gemini-2.0-flash",
            temperature=temperature,
            streaming=streaming,
            google_api_key=api_key,
        )

    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-3-haiku-20240307",
            temperature=temperature,
            streaming=streaming,
            anthropic_api_key=api_key,
        )

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is not set. Add it to your .env file.")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            temperature=temperature,
            streaming=streaming,
            openai_api_key=api_key,
        )

    elif provider == "ollama":
        base_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        if base_url:
            base_url = base_url.split("#")[0].strip().strip('"').strip("'")
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model or "gemma3:4b",
            temperature=temperature,
            streaming=streaming,
            base_url=base_url,
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: '{provider}'. "
            "Set CARTOGRAPHER_LLM_PROVIDER to 'google', 'anthropic', 'openai', or 'ollama'."
        )
