"""Anthropic adapter for the runtime chat path."""

from __future__ import annotations

from typing import Any, Optional

from langchain_anthropic import ChatAnthropic
from loguru import logger

from .base import ChatProviderAdapter
from .types import ChatModelRequest, LLMProviderConfig


class AnthropicAdapter(ChatProviderAdapter):
    """Create Claude chat models through the Anthropic LangChain adapter."""

    provider_name = "anthropic"

    def create_chat_model(
        self,
        request: ChatModelRequest,
        provider_config: LLMProviderConfig,
    ) -> Optional[Any]:
        if not provider_config.anthropic_api_key:
            logger.warning("Anthropic API key not found - LLM features will be disabled")
            return None

        streaming_kwargs = {"streaming": True} if request.streaming else {}
        return ChatAnthropic(
            model=request.model,
            anthropic_api_key=provider_config.anthropic_api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **streaming_kwargs,
        )
