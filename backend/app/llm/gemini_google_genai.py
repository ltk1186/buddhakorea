"""Experimental Gemini adapter using langchain-google-genai."""

from __future__ import annotations

from typing import Any, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from .base import ChatProviderAdapter
from .types import ChatModelRequest, LLMProviderConfig


class GeminiGoogleGenAIAdapter(ChatProviderAdapter):
    """Create Gemini chat models through the Google GenAI LangChain adapter."""

    provider_name = "gemini_google_genai"

    def create_chat_model(
        self,
        request: ChatModelRequest,
        provider_config: LLMProviderConfig,
    ) -> Optional[Any]:
        if not provider_config.gemini_api_key:
            logger.warning(
                "GEMINI_PROVIDER=google_genai requires GEMINI_API_KEY - "
                "falling back to disabled Gemini route"
            )
            return None

        streaming_kwargs = {"streaming": True} if request.streaming else {}
        logger.info("Using Google GenAI adapter for Gemini model")
        return ChatGoogleGenerativeAI(
            model=request.model,
            google_api_key=provider_config.gemini_api_key,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **streaming_kwargs,
        )
