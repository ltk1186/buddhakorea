"""Provider routing for runtime chat model construction."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .anthropic import AnthropicAdapter
from .base import ChatProviderAdapter
from .gemini_google_genai import GeminiGoogleGenAIAdapter
from .gemini_vertex import GeminiVertexAdapter
from .openai import OpenAIAdapter
from .types import ChatModelRequest, LLMProviderConfig, ProviderSelection


ADAPTERS: Dict[str, ChatProviderAdapter] = {
    "anthropic": AnthropicAdapter(),
    "gemini_google_genai": GeminiGoogleGenAIAdapter(),
    "gemini_vertex": GeminiVertexAdapter(),
    "openai": OpenAIAdapter(),
}


def resolve_provider(
    model: str,
    *,
    gemini_provider: str = "vertex",
) -> ProviderSelection:
    """Resolve the provider route for a configured model name."""

    model_lower = model.lower()
    if "claude" in model_lower:
        return ProviderSelection(provider="anthropic", model=model)
    if "gemini" in model_lower:
        provider = (
            "gemini_google_genai"
            if gemini_provider == "google_genai"
            else "gemini_vertex"
        )
        return ProviderSelection(provider=provider, model=model)
    return ProviderSelection(provider="openai", model=model)


def get_provider_for_model(model: str, *, gemini_provider: str = "vertex") -> str:
    """Return the stable provider identifier for a model name."""

    return resolve_provider(model, gemini_provider=gemini_provider).provider


def create_chat_llm(
    request: ChatModelRequest,
    provider_config: LLMProviderConfig,
) -> Optional[Any]:
    """Create a chat model using the resolved provider adapter."""

    selection = resolve_provider(
        request.model,
        gemini_provider=provider_config.gemini_provider,
    )
    adapter = ADAPTERS[selection.provider]
    return adapter.create_chat_model(request, provider_config)
