"""OpenAI adapter for the runtime chat path."""

from __future__ import annotations

from typing import Any, Optional

from langchain_openai import ChatOpenAI
from loguru import logger

from .base import ChatProviderAdapter
from .types import ChatModelRequest, LLMProviderConfig


class OpenAIAdapter(ChatProviderAdapter):
    """Create OpenAI chat models through the OpenAI LangChain adapter."""

    provider_name = "openai"

    def create_chat_model(
        self,
        request: ChatModelRequest,
        provider_config: LLMProviderConfig,
    ) -> Optional[Any]:
        if not provider_config.openai_api_key:
            logger.warning("OpenAI API key not found - LLM features will be disabled")
            return None

        streaming_kwargs = {"streaming": True} if request.streaming else {}
        return ChatOpenAI(
            model=request.model,
            openai_api_key=provider_config.openai_api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **streaming_kwargs,
        )
