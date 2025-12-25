"""
Hint Generator Service.

빠알리 세그먼트에서 DPD 기반 문법 힌트를 생성합니다.
Gemini에게 제공할 힌트를 토큰 예산 내에서 최적화합니다.
"""
import re
import json
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from html import escape as html_escape

from ..config import settings
from .dpd_service import DpdService, get_dpd_service


@dataclass
class HintBudget:
    """토큰 예산 설정."""
    max_tokens_per_segment: int = field(
        default_factory=lambda: settings.HINT_MAX_TOKENS_PER_SEGMENT
    )
    max_tokens_per_batch: int = field(
        default_factory=lambda: settings.HINT_MAX_TOKENS_PER_BATCH
    )
    max_words_per_segment: int = field(
        default_factory=lambda: settings.HINT_MAX_WORDS_PER_SEGMENT
    )
    chars_per_token: float = 2.5  # 토큰당 평균 문자 수 (한국어/영어 혼합)

    def estimate_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 추정."""
        return int(len(text) / self.chars_per_token)


@dataclass
class SegmentHints:
    """세그먼트별 힌트."""
    segment_id: str
    hints: List[dict] = field(default_factory=list)
    estimated_tokens: int = 0

    def to_prompt_text(self) -> str:
        """프롬프트에 포함할 힌트 텍스트 생성 (compact 형식)."""
        if not self.hints:
            return ""

        lines = []
        for h in self.hints:
            word = h.get('word', '')
            lemma = h.get('lemma', '')
            # compact 모드: opts는 문자열 리스트
            opts = h.get('opts', [])
            opts_str = ' / '.join(opts)

            if lemma:
                lines.append(f"    {word} ({lemma}): [{opts_str}]")
            else:
                lines.append(f"    {word}: [{opts_str}]")

        return '\n'.join(lines)


class HintGenerator:
    """세그먼트에 대한 DPD 힌트 생성."""

    # 빠알리 단어 추출 정규식 (음절문자 + 일반 라틴)
    PALI_WORD_PATTERN = re.compile(
        r'[a-zA-ZāīūṭḍṇṅñṃḷĀĪŪṬḌṆṄÑṂḶ]+',
        re.UNICODE
    )

    def __init__(
        self,
        dpd: Optional[DpdService] = None,
        budget: Optional[HintBudget] = None
    ):
        """
        Args:
            dpd: DpdService 인스턴스. None이면 싱글톤 사용.
            budget: 토큰 예산 설정. None이면 기본값 사용.
        """
        self.dpd = dpd or get_dpd_service()
        self.budget = budget or HintBudget()

    @staticmethod
    def _escape_xml(text: str) -> str:
        """XML 특수문자 이스케이프 (<, >, &, ', ")."""
        return html_escape(text, quote=True)

    def extract_words(self, text: str, max_words: Optional[int] = None) -> List[str]:
        """
        텍스트에서 빠알리 단어 추출 (순서 유지, 중복 제거).

        Args:
            text: 빠알리 원문
            max_words: 최대 단어 수 (None이면 설정값 사용)

        Returns:
            단어 목록 (중복 제거, 상한선 적용)
        """
        max_words = max_words or self.budget.max_words_per_segment
        words = self.PALI_WORD_PATTERN.findall(text)

        # 순서 유지하면서 중복 제거
        seen = set()
        unique_words = []
        for w in words:
            w_lower = w.lower()
            if w_lower not in seen and len(w) > 1:  # 1글자 제외
                seen.add(w_lower)
                unique_words.append(w)

        # 쿼리 폭발 방지
        return unique_words[:max_words]

    def generate_hints(self, segment_id: str, text: str) -> SegmentHints:
        """
        세그먼트에 대한 힌트 생성.

        Args:
            segment_id: 세그먼트 식별자
            text: 빠알리 원문

        Returns:
            SegmentHints: 토큰 예산 내의 힌트 목록
        """
        if not self.dpd.hints_available:
            return SegmentHints(segment_id=segment_id)

        words = self.extract_words(text)
        hints = []
        total_tokens = 0

        for word in words:
            # 힌트 생성
            hint = self.dpd.get_hint(word)
            if not hint:
                continue

            # 토큰 예산 체크
            hint_text = json.dumps(hint, ensure_ascii=False)
            hint_tokens = self.budget.estimate_tokens(hint_text)

            if total_tokens + hint_tokens > self.budget.max_tokens_per_segment:
                break  # 예산 초과 시 중단

            hints.append(hint)
            total_tokens += hint_tokens

        return SegmentHints(
            segment_id=segment_id,
            hints=hints,
            estimated_tokens=total_tokens
        )

    def generate_batch_hints(
        self,
        segments: List[Tuple[str, str]]
    ) -> List[SegmentHints]:
        """
        배치 세그먼트들에 대한 힌트 생성.

        Args:
            segments: [(segment_id, text), ...] 목록

        Returns:
            SegmentHints 목록 (배치 토큰 예산 내)
        """
        all_hints = []
        batch_tokens = 0

        for seg_id, text in segments:
            seg_hints = self.generate_hints(seg_id, text)

            # 배치 예산 체크
            if batch_tokens + seg_hints.estimated_tokens > self.budget.max_tokens_per_batch:
                # 예산 초과 시 힌트 없이 추가
                all_hints.append(SegmentHints(segment_id=seg_id))
            else:
                all_hints.append(seg_hints)
                batch_tokens += seg_hints.estimated_tokens

        return all_hints

    def format_for_prompt(self, batch_hints: List[SegmentHints]) -> str:
        """
        배치 힌트를 프롬프트용 텍스트로 포맷팅.

        Returns:
            XML 형식의 힌트 텍스트 (이스케이프 적용)
        """
        lines = ["<grammar_hints>"]

        for seg_hints in batch_hints:
            if seg_hints.hints:
                # segment_id 이스케이프
                safe_id = self._escape_xml(str(seg_hints.segment_id))
                lines.append(f"  <segment id=\"{safe_id}\">")
                lines.append(seg_hints.to_prompt_text())
                lines.append("  </segment>")

        lines.append("</grammar_hints>")

        # 힌트가 없으면 빈 문자열 반환
        if len(lines) == 2:  # 시작/종료 태그만 있는 경우
            return ""

        return '\n'.join(lines)

    def format_single_for_prompt(self, segment_hints: SegmentHints) -> str:
        """
        단일 세그먼트 힌트를 프롬프트용 텍스트로 포맷팅.

        Returns:
            힌트 텍스트 (XML 태그 없이)
        """
        if not segment_hints.hints:
            return ""

        lines = ["## 문법 힌트 (DPD 기반)"]
        lines.append(segment_hints.to_prompt_text())
        return '\n'.join(lines)


# Singleton factory
def get_hint_generator() -> HintGenerator:
    """Get HintGenerator instance (uses singleton DpdService)."""
    return HintGenerator()
