"""Base interfaces for runtime LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from .types import ChatModelRequest, LLMProviderConfig


class ChatProviderAdapter(ABC):
    """Create a chat model for one concrete provider integration."""

    provider_name: str

    @abstractmethod
    def create_chat_model(
        self,
        request: ChatModelRequest,
        provider_config: LLMProviderConfig,
    ) -> Optional[Any]:
        """Return the provider chat model or None when the route is unavailable."""
