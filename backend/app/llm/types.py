"""Shared types for the runtime LLM provider adapter layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ChatModelRequest:
    """Normalized chat model request used by provider adapters."""

    model: str
    temperature: float
    max_tokens: int
    streaming: bool = False


@dataclass(frozen=True)
class LLMProviderConfig:
    """Provider credentials and runtime settings required by adapters."""

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    gcp_project_id: Optional[str] = None
    gcp_location: str = "us-central1"


@dataclass(frozen=True)
class ProviderSelection:
    """Resolved provider route for a requested model name."""

    provider: str
    model: str
