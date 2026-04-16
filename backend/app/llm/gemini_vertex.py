"""Gemini-on-Vertex adapter for the runtime chat path."""

from __future__ import annotations

from typing import Any, Optional

from langchain_google_vertexai import ChatVertexAI
from loguru import logger

from .base import ChatProviderAdapter
from .types import ChatModelRequest, LLMProviderConfig


class GeminiVertexAdapter(ChatProviderAdapter):
    """Create Gemini chat models through the Vertex AI LangChain adapter."""

    provider_name = "gemini_vertex"

    def create_chat_model(
        self,
        request: ChatModelRequest,
        provider_config: LLMProviderConfig,
    ) -> Optional[Any]:
        streaming_kwargs = {"streaming": True} if request.streaming else {}
        logger.info("Using Vertex AI adapter for Gemini model")
        return ChatVertexAI(
            model=request.model,
            project=provider_config.gcp_project_id,
            location=provider_config.gcp_location,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **streaming_kwargs,
        )
