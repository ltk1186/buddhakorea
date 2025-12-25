"""
Gemini AI client for Pali text translation.
Supports both streaming and non-streaming responses with DPD hints.
"""
import json
import re
import logging
from typing import AsyncGenerator, Optional, List, Tuple
from pydantic import ValidationError
import google.generativeai as genai

from ..config import settings
from ..schemas.translate import TranslationResult

logger = logging.getLogger(__name__)


class TranslationParseError(Exception):
    """JSON 파싱 또는 검증 실패."""
    pass


# Legacy translation prompt (for backward compatibility)
TRANSLATION_PROMPT = '''당신은 빠알리어(Pali) 전문가입니다. 주어진 빠알리어 원문을 다음 JSON 형식으로 번역해주세요.
규칙:
1. 각 문장별로 분석합니다
2. 문법 분석에는 품사, 격, 수, 활용형을 포함합니다
3. 직역은 단어 순서대로, 의역은 자연스러운 한국어로 작성합니다
4. 설명에는 주석서의 맥락과 교리적 의미를 포함합니다

출력 형식 (JSON):
{{
  "sentences": [
    {{
      "original_pali": "원문 빠알리어",
      "grammatical_analysis": "문법 분석",
      "literal_translation": "직역",
      "free_translation": "의역",
      "explanation": "설명"
    }}
  ],
  "summary": "전체 요약"
}}

원문:
{text}

JSON 형식으로만 응답하세요:'''


# Enhanced translation prompt with grammar rules (from CLI batch_processor)
ENHANCED_TRANSLATION_PROMPT = '''역할: 빠알리 주석서(Aṭṭhakathā) 한국어 번역 전문가
대상: 한국 불교 승려 및 학자

## 문법 태그 규칙
- 품사: 명사(남/여/중), 동사, 형용사, 대명사, 수사, 불변화사, 분사
- 격: 주격, 대격, 도구격, 여격, 탈격, 속격, 처격, 호격
- 수: 단수, 복수
- 시제: 현재, 과거, 미래, 아오리스트
- 법: 직설법, 명령법, 기원법, 조건법
- 복합어: 구성요소를 '+'로 분리

{grammar_hints}

## 출력 규칙
1. **해설(explanation)은 반드시 {max_explanation_sentences}문장 이내**로 작성
2. 힌트에 있는 단어는 선택만, 없는 단어만 상세 분석
3. 모든 빠알리어 단어는 반드시 문법 분석에 포함

## 입력
{pali_text}

## 출력 형식 (JSON)
{{
  "sentences": [
    {{
      "original_pali": "빠알리 원문 문장",
      "grammatical_analysis": "Word [태그]: 의미\\nWord2 [태그]: 의미\\n...",
      "literal_translation": "직역 (단어 순서대로)",
      "free_translation": "의역 (자연스러운 한국어)",
      "explanation": "해설 ({max_explanation_sentences}문장 이내)"
    }}
  ],
  "summary": "단락 전체 요약"
}}'''


# Batch translation prompt
BATCH_TRANSLATION_PROMPT = '''역할: 빠알리 주석서(Aṭṭhakathā) 한국어 번역 전문가
대상: 한국 불교 승려 및 학자

## 문법 태그 규칙
- 품사: 명사(남/여/중), 동사, 형용사, 대명사, 수사, 불변화사, 분사
- 격: 주격, 대격, 도구격, 여격, 탈격, 속격, 처격, 호격
- 수: 단수, 복수
- 시제: 현재, 과거, 미래, 아오리스트
- 법: 직설법, 명령법, 기원법, 조건법
- 복합어: 구성요소를 '+'로 분리

{grammar_hints}

## 출력 규칙
1. 각 세그먼트의 id를 정확히 유지
2. **해설(explanation)은 반드시 {max_explanation_sentences}문장 이내**로 작성
3. 힌트에 있는 단어는 선택만, 없는 단어만 상세 분석

## 입력 세그먼트
{segments_xml}

## 출력 형식 (JSON)
{{
  "results": [
    {{
      "id": "segment_id",
      "sentences": [
        {{
          "original_pali": "빠알리 문장",
          "grammatical_analysis": "Word [태그]: 의미\\n...",
          "literal_translation": "직역",
          "free_translation": "의역",
          "explanation": "해설 ({max_explanation_sentences}문장 이내)"
        }}
      ],
      "summary": "단락 요약"
    }}
  ]
}}'''


CHAT_PROMPT = '''당신은 빠알리어 불교 문헌 전문가입니다.
주어진 빠알리어 원문과 (가능하면) 번역을 바탕으로 사용자의 질문에 상세하게 답변해주세요.

규칙:
1. 번역이 빈 JSON({{}})이거나 내용이 없으면, 번역을 추측하지 말고 원문 기반으로만 답변하세요.
2. 번역이 제공된 경우에만 번역을 근거로 활용하세요.

원문:
{original_text}

번역(JSON, 없으면 {{}}):
{translation}

질문: {question}

답변:'''


class GeminiClient:
    """Client for interacting with Google Gemini AI."""

    def __init__(self):
        """Initialize the Gemini client."""
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)

        # Standard model (for streaming - no JSON mime type)
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": settings.TEMPERATURE,
                "max_output_tokens": 32768,  # Increased for long translations
            }
        )

        # JSON-enforced model (for non-streaming with validation)
        self.json_model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": settings.TEMPERATURE,
                "max_output_tokens": 32768,  # Increased for long translations
                "response_mime_type": "application/json",
            }
        )

        # Batch model with higher token limit (for batch translation)
        self.batch_model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": settings.TEMPERATURE,
                "max_output_tokens": 32768,  # Higher limit for batch
            }
        )

    def _clean_json_response(self, text: str) -> str:
        """Clean up JSON response (remove markdown code blocks)."""
        json_text = text.strip()
        if json_text.startswith("```"):
            json_text = re.sub(r"```json?\n?", "", json_text)
            json_text = re.sub(r"```\s*$", "", json_text)
        return json_text

    def _validate_response(self, raw: str) -> TranslationResult:
        """Pydantic 스키마로 검증."""
        try:
            cleaned = self._clean_json_response(raw)
            data = json.loads(cleaned)
            return TranslationResult.model_validate(data)
        except json.JSONDecodeError as e:
            raise TranslationParseError(f"JSON parse error: {e}")
        except ValidationError as e:
            raise TranslationParseError(f"Validation error: {e}")

    def _build_enhanced_prompt(
        self,
        pali_text: str,
        grammar_hints: str = ""
    ) -> str:
        """Build enhanced prompt with hints."""
        hints_section = ""
        if grammar_hints:
            hints_section = f"## 문법 힌트 (DPD 기반)\n{grammar_hints}"

        return ENHANCED_TRANSLATION_PROMPT.format(
            grammar_hints=hints_section,
            pali_text=pali_text,
            max_explanation_sentences=settings.EXPLANATION_MAX_SENTENCES
        )

    def _build_batch_prompt(
        self,
        segments: List[Tuple[str, str]],
        grammar_hints: str = ""
    ) -> str:
        """Build batch translation prompt with XML segments."""
        from html import escape as html_escape

        # Build XML segments
        segments_xml_lines = ["<segments>"]
        for seg_id, text in segments:
            safe_id = html_escape(str(seg_id))
            safe_text = html_escape(text)
            segments_xml_lines.append(f'  <segment id="{safe_id}">')
            segments_xml_lines.append(f"    {safe_text}")
            segments_xml_lines.append("  </segment>")
        segments_xml_lines.append("</segments>")
        segments_xml = "\n".join(segments_xml_lines)

        hints_section = ""
        if grammar_hints:
            hints_section = f"## 문법 힌트 (DPD 기반)\n{grammar_hints}"

        return BATCH_TRANSLATION_PROMPT.format(
            grammar_hints=hints_section,
            segments_xml=segments_xml,
            max_explanation_sentences=settings.EXPLANATION_MAX_SENTENCES
        )

    # ===== Legacy Methods (backward compatible) =====

    async def translate_stream(self, pali_text: str) -> AsyncGenerator[dict, None]:
        """
        Translate Pali text with streaming response (legacy, no hints).

        Yields SSE-compatible event dicts:
        - {"type": "token", "content": "..."}
        - {"type": "complete", "data": {...}}
        """
        prompt = TRANSLATION_PROMPT.format(text=pali_text)

        try:
            response = await self.model.generate_content_async(
                prompt,
                stream=True
            )

            full_response = ""
            async for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield {"type": "token", "content": chunk.text}

            # Parse the complete JSON response
            try:
                result = self._validate_response(full_response)
                yield {"type": "complete", "data": result.model_dump()}
            except TranslationParseError as e:
                yield {"type": "error", "error": str(e)}

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    async def translate(self, pali_text: str) -> Optional[dict]:
        """
        Translate Pali text (non-streaming, legacy).

        Returns the translation result dict or None on error.
        """
        prompt = TRANSLATION_PROMPT.format(text=pali_text)

        try:
            response = await self.model.generate_content_async(prompt)
            result = self._validate_response(response.text)
            return result.model_dump()
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return None

    # ===== Enhanced Methods (with hints) =====

    async def translate_with_hints_stream(
        self,
        pali_text: str,
        grammar_hints: str = ""
    ) -> AsyncGenerator[dict, None]:
        """
        Translate Pali text with DPD hints and streaming response.

        Args:
            pali_text: Pali source text
            grammar_hints: Pre-generated grammar hints from HintGenerator

        Yields SSE-compatible event dicts:
        - {"type": "token", "content": "..."}
        - {"type": "complete", "data": {...}}
        - {"type": "error", "error": "..."}
        """
        prompt = self._build_enhanced_prompt(pali_text, grammar_hints)

        try:
            response = await self.model.generate_content_async(
                prompt,
                stream=True
            )

            full_response = ""
            async for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield {"type": "token", "content": chunk.text}

            # Validate and parse
            try:
                result = self._validate_response(full_response)
                yield {"type": "complete", "data": result.model_dump()}
            except TranslationParseError as e:
                # Retry once without streaming
                logger.warning(f"Streaming parse failed, retrying: {e}")
                try:
                    retry_result = await self._translate_with_hints_retry(
                        pali_text, grammar_hints
                    )
                    if retry_result:
                        yield {"type": "complete", "data": retry_result.model_dump()}
                    else:
                        yield {"type": "error", "error": str(e)}
                except Exception as retry_e:
                    yield {"type": "error", "error": str(retry_e)}

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    def _get_response_text(self, response) -> str:
        """Safely extract text from Gemini response, handling blocked/empty responses."""
        try:
            # Check if response has candidates
            if not response.candidates:
                raise TranslationParseError("No response candidates available")

            candidate = response.candidates[0]

            # Check finish_reason (2 = SAFETY, 3 = RECITATION, 4 = OTHER)
            if hasattr(candidate, 'finish_reason') and candidate.finish_reason in [2, 3, 4]:
                reason_names = {2: "SAFETY", 3: "RECITATION", 4: "OTHER"}
                reason = reason_names.get(candidate.finish_reason, str(candidate.finish_reason))
                raise TranslationParseError(f"Response blocked: finish_reason={reason}")

            # Try to get text
            if hasattr(candidate, 'content') and candidate.content and candidate.content.parts:
                return candidate.content.parts[0].text

            # Fallback to response.text
            return response.text
        except AttributeError:
            # Simple response object
            return response.text

    async def _translate_with_hints_retry(
        self,
        pali_text: str,
        grammar_hints: str
    ) -> Optional[TranslationResult]:
        """Retry translation with JSON-enforced model."""
        prompt = self._build_enhanced_prompt(pali_text, grammar_hints)

        for attempt in range(settings.TRANSLATION_MAX_RETRIES + 1):
            try:
                response = await self.json_model.generate_content_async(prompt)
                text = self._get_response_text(response)
                return self._validate_response(text)
            except TranslationParseError as e:
                if attempt == settings.TRANSLATION_MAX_RETRIES:
                    raise
                logger.warning(f"JSON parse failed, retry {attempt + 1}: {e}")

        return None

    async def translate_with_hints(
        self,
        pali_text: str,
        grammar_hints: str = ""
    ) -> Optional[dict]:
        """
        Translate Pali text with hints (non-streaming).

        Returns the translation result dict or None on error.
        """
        prompt = self._build_enhanced_prompt(pali_text, grammar_hints)

        for attempt in range(settings.TRANSLATION_MAX_RETRIES + 1):
            try:
                response = await self.json_model.generate_content_async(prompt)
                text = self._get_response_text(response)
                result = self._validate_response(text)
                return result.model_dump()
            except TranslationParseError as e:
                if attempt == settings.TRANSLATION_MAX_RETRIES:
                    logger.error(f"Translation failed after retries: {e}")
                    return None
                logger.warning(f"Retry {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Translation error: {e}")
                return None

        return None

    # ===== Batch Translation Methods =====

    async def translate_batch_stream(
        self,
        segments: List[Tuple[str, str]],
        grammar_hints: str = ""
    ) -> AsyncGenerator[dict, None]:
        """
        Translate multiple segments in batch with streaming.

        Args:
            segments: List of (segment_id, pali_text) tuples
            grammar_hints: Pre-generated batch grammar hints

        Yields SSE-compatible event dicts:
        - {"type": "token", "content": "..."}
        - {"type": "parse_complete", "status": "parsing"}
        - {"type": "segment_complete", "segment_id": X, "translation": {...}}
        - {"type": "error", "error": "...", "segment_id": X (optional)}
        """
        prompt = self._build_batch_prompt(segments, grammar_hints)
        segment_ids = [seg_id for seg_id, _ in segments]

        try:
            # Use batch_model with higher token limit
            response = await self.batch_model.generate_content_async(
                prompt,
                stream=True
            )

            full_response = ""
            async for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    yield {"type": "token", "content": chunk.text}

            # Signal parsing phase
            yield {"type": "parse_complete", "status": "parsing"}

            # Parse batch results
            try:
                cleaned = self._clean_json_response(full_response)
                data = json.loads(cleaned)
                results = data.get("results", [])

                # Debug: Log detailed info
                logger.info(f"Batch translation: received {len(results)} results for {len(segment_ids)} segments")
                logger.info(f"Requested segment_ids: {segment_ids}")
                logger.info(f"Response keys: {data.keys()}")

                # Log each result's ID for debugging
                for i, r in enumerate(results):
                    result_id = r.get("id")
                    logger.info(f"  Result {i}: id={result_id} (type={type(result_id).__name__})")

                # Track which segments were successfully processed
                result_ids = set()

                # Emit segment_complete for each result
                for result in results:
                    seg_id = result.get("id")
                    # Normalize to string for comparison
                    seg_id_str = str(seg_id) if seg_id is not None else None

                    if seg_id_str:
                        result_ids.add(seg_id_str)

                    try:
                        # Validate individual translation
                        translation = TranslationResult.model_validate({
                            "sentences": result.get("sentences", []),
                            "summary": result.get("summary")
                        })
                        yield {
                            "type": "segment_complete",
                            "segment_id": seg_id_str,  # Use normalized string
                            "translation": translation.model_dump()
                        }
                    except ValidationError as e:
                        logger.error(f"Validation error for segment {seg_id}: {e}")
                        yield {
                            "type": "error",
                            "error": f"Validation error for segment {seg_id}: {e}",
                            "segment_id": seg_id_str
                        }

                # Check for missing segments and fallback
                requested_ids = set(segment_ids)  # These are already strings
                missing_ids = requested_ids - result_ids

                if missing_ids:
                    logger.warning(f"Missing segments in batch response: {missing_ids}")
                    yield {"type": "fallback_start", "reason": f"Missing segments: {missing_ids}"}

                    # Fallback: translate missing segments individually
                    for seg_id, text in segments:
                        if seg_id in missing_ids:
                            logger.info(f"Fallback translation for segment {seg_id}")
                            try:
                                async for event in self.translate_with_hints_stream(text, ""):
                                    if event["type"] == "complete":
                                        yield {
                                            "type": "segment_complete",
                                            "segment_id": seg_id,
                                            "translation": event["data"]
                                        }
                                    elif event["type"] == "error":
                                        yield {
                                            "type": "error",
                                            "error": event["error"],
                                            "segment_id": seg_id
                                        }
                            except Exception as fallback_e:
                                logger.error(f"Fallback failed for segment {seg_id}: {fallback_e}")
                                yield {
                                    "type": "error",
                                    "error": str(fallback_e),
                                    "segment_id": seg_id
                                }

            except json.JSONDecodeError as e:
                # Batch parse failed - try individual fallback
                logger.warning(f"Batch parse failed, falling back to individual: {e}")
                yield {"type": "fallback_start", "reason": str(e)}

                for seg_id, text in segments:
                    try:
                        async for event in self.translate_with_hints_stream(text, ""):
                            if event["type"] == "complete":
                                yield {
                                    "type": "segment_complete",
                                    "segment_id": seg_id,
                                    "translation": event["data"]
                                }
                            elif event["type"] == "error":
                                yield {
                                    "type": "error",
                                    "error": event["error"],
                                    "segment_id": seg_id
                                }
                    except Exception as fallback_e:
                        yield {
                            "type": "error",
                            "error": str(fallback_e),
                            "segment_id": seg_id
                        }

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    # ===== Chat Methods =====

    async def chat_stream(
        self,
        question: str,
        original_text: str,
        translation: dict
    ) -> AsyncGenerator[dict, None]:
        """
        Answer a question about a segment with streaming response.

        Yields SSE-compatible event dicts.
        """
        translation_str = json.dumps(translation, ensure_ascii=False, indent=2)
        prompt = CHAT_PROMPT.format(
            original_text=original_text,
            translation=translation_str,
            question=question
        )

        try:
            response = await self.model.generate_content_async(
                prompt,
                stream=True
            )

            async for chunk in response:
                if chunk.text:
                    yield {"type": "token", "content": chunk.text}

            yield {"type": "done"}

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    async def chat(
        self,
        question: str,
        original_text: str,
        translation: dict
    ) -> Optional[str]:
        """
        Answer a question about a segment (non-streaming).

        Returns the answer string or None on error.
        """
        translation_str = json.dumps(translation, ensure_ascii=False, indent=2)
        prompt = CHAT_PROMPT.format(
            original_text=original_text,
            translation=translation_str,
            question=question
        )

        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return None
