"""Structured retrieval and prompt trace helpers for operational logging."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from .prompts import get_prompt_spec


@dataclass(frozen=True)
class RetrievalConfigTrace:
    """Stable retrieval metadata for logs, audits, and future admin tooling."""

    mode: str
    top_k: int
    max_sources: int
    detailed_mode: bool
    collection: str
    filter_type: Optional[str] = None
    filter_value: Optional[str] = None
    filter_sutra_count: Optional[int] = None
    hyde_applied: bool = False
    buddhist_term_expansion: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_prompt_trace(prompt_id: str) -> Dict[str, Any]:
    """Serialize prompt metadata by stable prompt registry id."""

    prompt = get_prompt_spec(prompt_id)
    return {
        "id": prompt.registry_key,
        "prompt_id": prompt.id,
        "version": prompt.version,
        "mode": prompt.mode,
        "description": prompt.description,
    }


def build_query_trace(
    *,
    prompt_id: str,
    retrieval: RetrievalConfigTrace,
    response_mode: str,
    streaming: bool,
    model: str,
) -> Dict[str, Any]:
    """Build the structured query trace payload shared across logs."""

    return {
        "prompt": build_prompt_trace(prompt_id),
        "retrieval": retrieval.to_dict(),
        "response_mode": response_mode,
        "streaming": streaming,
        "model": model,
    }
