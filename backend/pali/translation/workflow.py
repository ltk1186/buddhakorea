"""Small workflow helpers for future async translation jobs."""

from __future__ import annotations

from .schemas import TranslationJobStatus


TERMINAL_JOB_STATUSES = {
    TranslationJobStatus.SUCCEEDED,
    TranslationJobStatus.FAILED,
    TranslationJobStatus.CANCELLED,
    TranslationJobStatus.SKIPPED,
}


def is_terminal_status(status: TranslationJobStatus) -> bool:
    return status in TERMINAL_JOB_STATUSES

