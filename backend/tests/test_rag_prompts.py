from backend.app.rag.prompts import (
    NORMAL_PROMPT_ID,
    PROMPT_REGISTRY,
    STREAMING_DETAILED_PROMPT_ID,
    TRADITION_FILTER_PROMPT_ID,
    build_prompt,
)


def test_prompt_registry_keys_are_stable():
    assert NORMAL_PROMPT_ID in PROMPT_REGISTRY
    assert TRADITION_FILTER_PROMPT_ID in PROMPT_REGISTRY
    assert PROMPT_REGISTRY[NORMAL_PROMPT_ID].registry_key == "normal_v1"


def test_normal_prompt_formats_context_and_question():
    prompt = build_prompt(NORMAL_PROMPT_ID)

    formatted = prompt.format(context="문헌 내용", question="질문")

    assert "문헌 내용" in formatted
    assert "질문" in formatted
    assert "자기소개나 서두 없이 바로 본론" in formatted


def test_tradition_prompt_formats_tradition_context_and_question():
    prompt = build_prompt(TRADITION_FILTER_PROMPT_ID, tradition="초기불교")

    formatted = prompt.format(context="전통 문헌", question="전통 질문")

    assert "초기불교 문헌" in formatted
    assert "초기불교의 관점" in formatted
    assert "전통 문헌" in formatted
    assert "전통 질문" in formatted


def test_streaming_prompt_formats_context_and_question():
    prompt = build_prompt(STREAMING_DETAILED_PROMPT_ID)

    formatted = prompt.format(context="스트리밍 문헌", question="스트리밍 질문")

    assert "스트리밍 문헌" in formatted
    assert "스트리밍 질문" in formatted
    assert "가능한 한 상세하고 포괄적으로" in formatted
