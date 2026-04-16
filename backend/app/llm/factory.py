"""Provider routing for runtime chat model construction."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .anthropic import AnthropicAdapter
from .base import ChatProviderAdapter
from .gemini_vertex import GeminiVertexAdapter
from .openai import OpenAIAdapter
from .types import ChatModelRequest, LLMProviderConfig, ProviderSelection


ADAPTERS: Dict[str, ChatProviderAdapter] = {
    "anthropic": AnthropicAdapter(),
    "gemini_vertex": GeminiVertexAdapter(),
    "openai": OpenAIAdapter(),
}


def resolve_provider(model: str) -> ProviderSelection:
    """Resolve the provider route for a configured model name."""

    model_lower = model.lower()
    if "claude" in model_lower:
        return ProviderSelection(provider="anthropic", model=model)
    if "gemini" in model_lower:
        return ProviderSelection(provider="gemini_vertex", model=model)
    return ProviderSelection(provider="openai", model=model)


def get_provider_for_model(model: str) -> str:
    """Return the stable provider identifier for a model name."""

    return resolve_provider(model).provider


def create_chat_llm(
    request: ChatModelRequest,
    provider_config: LLMProviderConfig,
) -> Optional[Any]:
    """Create a chat model using the resolved provider adapter."""

    selection = resolve_provider(request.model)
    adapter = ADAPTERS[selection.provider]
    return adapter.create_chat_model(request, provider_config)
