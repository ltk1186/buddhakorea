"""
Translation Logger Service.

구조화된 번역 메트릭 로깅을 제공합니다.
"""
import json
import time
import logging
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from contextlib import contextmanager

logger = logging.getLogger("translation_metrics")


@dataclass
class TranslationMetrics:
    """번역 요청 메트릭."""
    request_id: str
    literature_id: str
    segment_ids: List[int]
    model: str
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    hints_used: bool = False
    hints_count: int = 0
    fallback_used: bool = False
    success: bool = True
    error: Optional[str] = None
    is_batch: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class TranslationLogger:
    """구조화된 번역 메트릭 로거."""

    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_name = model_name

    def generate_request_id(self) -> str:
        """고유 요청 ID 생성."""
        return str(uuid.uuid4())[:8]

    @contextmanager
    def track_translation(
        self,
        literature_id: str,
        segment_ids: List[int],
        hints_used: bool = False,
        hints_count: int = 0,
        is_batch: bool = False
    ):
        """
        번역 요청 추적 컨텍스트 매니저.

        Usage:
            with logger.track_translation("lit_123", [1, 2, 3]) as metrics:
                # perform translation
                metrics.input_tokens = 1000
                metrics.output_tokens = 500
        """
        request_id = self.generate_request_id()
        start_time = time.time()

        metrics = TranslationMetrics(
            request_id=request_id,
            literature_id=literature_id,
            segment_ids=segment_ids,
            model=self.model_name,
            hints_used=hints_used,
            hints_count=hints_count,
            is_batch=is_batch
        )

        try:
            yield metrics
        except Exception as e:
            metrics.success = False
            metrics.error = str(e)
            raise
        finally:
            metrics.latency_ms = int((time.time() - start_time) * 1000)
            self.log(metrics)

    def log(self, metrics: TranslationMetrics):
        """메트릭 로그 출력."""
        log_data = metrics.to_dict()

        if metrics.success:
            logger.info(json.dumps(log_data, ensure_ascii=False))
        else:
            logger.error(json.dumps(log_data, ensure_ascii=False))

    def log_single(
        self,
        request_id: str,
        literature_id: str,
        segment_id: int,
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        hints_used: bool = False,
        hints_count: int = 0,
        success: bool = True,
        error: Optional[str] = None
    ):
        """단일 번역 메트릭 로그."""
        metrics = TranslationMetrics(
            request_id=request_id,
            literature_id=literature_id,
            segment_ids=[segment_id],
            model=self.model_name,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            hints_used=hints_used,
            hints_count=hints_count,
            success=success,
            error=error,
            is_batch=False
        )
        self.log(metrics)

    def log_batch(
        self,
        request_id: str,
        literature_id: str,
        segment_ids: List[int],
        latency_ms: int,
        input_tokens: int = 0,
        output_tokens: int = 0,
        hints_used: bool = False,
        hints_count: int = 0,
        fallback_used: bool = False,
        success: bool = True,
        error: Optional[str] = None
    ):
        """배치 번역 메트릭 로그."""
        metrics = TranslationMetrics(
            request_id=request_id,
            literature_id=literature_id,
            segment_ids=segment_ids,
            model=self.model_name,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            hints_used=hints_used,
            hints_count=hints_count,
            fallback_used=fallback_used,
            success=success,
            error=error,
            is_batch=True
        )
        self.log(metrics)


# Singleton factory
_logger_instance: Optional[TranslationLogger] = None


def get_translation_logger() -> TranslationLogger:
    """Get TranslationLogger singleton."""
    global _logger_instance
    if _logger_instance is None:
        from config import settings
        _logger_instance = TranslationLogger(model_name=settings.GEMINI_MODEL)
    return _logger_instance
