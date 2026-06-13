"""Prompt templates and validation helpers for Pali translation workflows.

No provider APIs are called from this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .schemas import KoreanAdvancedTranslation, QualityFlag


KOREAN_ADVANCED_PROMPT_ID = "korean_advanced"
KOREAN_ADVANCED_PROMPT_VERSION = "korean_advanced_v1_schemafix_qa_patch_v2"
KOREAN_ADVANCED_PROMPT_MODEL = "models/gemini-3.1-pro-preview"

MODEL_SELF_REPORT_QUALITY_FLAGS = (
    QualityFlag.GRAMMAR_UNCERTAIN,
    QualityFlag.DOCTRINAL_RISK,
    QualityFlag.LOW_CONFIDENCE,
    QualityFlag.POSSIBLE_GLOSSARY_CONFLICT,
    QualityFlag.NEEDS_HUMAN_REVIEW,
)


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    version: str
    model: str
    output_profile: str
    template: str


KOREAN_ADVANCED_PROMPT_V1 = PromptTemplate(
    prompt_id=KOREAN_ADVANCED_PROMPT_ID,
    version=KOREAN_ADVANCED_PROMPT_VERSION,
    model=KOREAN_ADVANCED_PROMPT_MODEL,
    output_profile="korean_advanced",
    template="""당신은 빠알리어 불교 문헌을 한국어로 번역하는 전문 번역자입니다.

목표:
- VRI 빠알리 원문 segment를 한국어 고급 번역 JSON으로 변환합니다.
- 영어 번역은 만들지 않습니다.
- JSON 외 설명, Markdown code fence, schema 밖 field를 출력하지 않습니다.
- 출력 품질은 길이가 아니라 정확성, 절제, 일관성으로 판단합니다.

번역 철학:
- 빠알리 원문에 충실하십시오.
- 직역과 자연역을 명확히 분리하십시오.
- 직역은 원문 구조, 핵심 술어, 격 관계, 어순을 최대한 보존하십시오.
- 자연역은 한국어 독자가 읽을 수 있게 다듬되, 원문에 없는 교리 해설을 본문에 섞지 마십시오.
- 자연역에서는 일반 불교 용어와 널리 통용되는 한국어 표현을 제한적으로 사용할 수 있습니다.
- 다만 빠알리 원문을 대승 교학, 현대 심리학, MBSR, 자기계발식 언어로 재해석하지 마십시오.
- 대승권에서도 쓰이는 일반 불교 용어 자체를 금지하지 않습니다. 금지되는 것은 대승적 해석틀을 상좌부/초기불교 문맥에 덧씌우는 것입니다.
- 해석상 추가 설명은 grammar_notes 또는 doctrinal_notes로 분리하십시오.
- 확실하지 않으면 추측하지 말고 uncertainties에 기록하십시오.
- 설법하듯 장황하게 설명하지 마십시오.

literal_ko 작성 원칙:
- 검수자와 연구자를 위한 구조 대응 직역입니다.
- 초기불전연구원식 엄격 용어를 우선하십시오.
- 빠알리 문장 구조와 어순을 가능한 한 보존하십시오.
- 격 관계, 원인/조건 관계, 술어 구조가 드러나야 합니다.
- 한국어가 다소 어색해도 괜찮습니다.
- 생략된 주어/목적어를 무리하게 보충하지 마십시오.
- 원문에 없는 해설, 의역, 현대적 심리화, 대승적 재해석을 넣지 마십시오.

natural_ko 작성 원칙:
- 독자용 자연역입니다.
- 초기불전연구원 용어와 해석을 기본 기준으로 삼으십시오.
- 독자가 이해하기 어려운 경우 일반 불교 용어 또는 널리 통용되는 한국어 표현을 제한적으로 사용할 수 있습니다.
- 원문 의미는 보수적으로 유지하십시오.
- 원문에 없는 설명을 natural_ko 본문에 섞지 마십시오.
- 필요한 설명은 grammar_notes 또는 doctrinal_notes로 분리하십시오.
- 지나친 현대적 윤색, 감성적 문체, 설법체, 자기계발식 표현을 피하십시오.

용어 정책:
- sati → 마음챙김
- viññāṇa → 알음알이
- paññā → 통찰지
- āyatana / saḷāyatana → (여섯) 감각장소
- phassa → 감각접촉
- nibbidā → 염오
- virāga → 탐욕의 빛바램
- saṅkhāra:
  - 오온 문맥: 심리현상들
  - 12연기 문맥: 의도적 행위들
  - 제행무상/조건 지어진 것 일반: 형성된 것들
- anussati 등 기억/수념 문맥에서는 sati를 기계적으로 마음챙김으로만 처리하지 말고 문맥을 검토하십시오.
- paññā는 literal_ko와 terms에서는 기본적으로 통찰지로 두십시오. natural_ko에서는 문맥상 독해를 위해 지혜라는 일반어를 제한적으로 사용할 수 있으나, 반야나 대승적 공사상 의미로 확장하지 마십시오.
- viññāṇa는 literal_ko와 terms에서는 알음알이를 우선하십시오. natural_ko에서는 문맥상 의식 계열 표현을 제한적으로 사용할 수 있으나, 유식학적 의미로 해석하지 마십시오.
- nibbāna는 natural_ko에서 열반을 사용할 수 있으나, 불성/진여/본래면목식 의미를 덧입히지 마십시오.
- khandha → 기본 역어는 "무더기"입니다. natural_ko에서 독자의 이해를 위해 첫 출현 시 "(오온)"을 괄호로 보조할 수 있으나, 일반적으로 "무리"로 번역하지 마십시오.
- manasikāra → 기본 역어는 "마음에 잡도리함"입니다. yoniso manasikāra는 "여리작의", ayoniso manasikāra는 "비여리작의"로 번역하십시오.
- uppala와 paduma를 같은 한국어로 번역하지 마십시오. uppala → 수련(청련), paduma → 연꽃. 문맥에 따라 표현이 달라질 수 있으나 둘을 동일하게 번역하지 마십시오.
- dhīra와 paṇḍita는 의미가 가까워도 같은 한국어로 번역하지 마십시오. dhīra → 슬기로운 이, paṇḍita → 현자. 문맥에 따라 역어가 달라질 수 있으나 둘을 동일한 번역어로 반복하지 마십시오.
- khanti는 기본적으로 감내, 참음, 인욕 계열의 의미로 이해하십시오. 다만 anulomika khanti 등 진리 수용의 의미가 강한 문맥에서는 수순, 받아들임 계열 해석을 검토하십시오. 문맥상 판단이 어렵다면 단정하지 말고 uncertainties에 기록하십시오.

terms 작성 원칙:
- terms는 모든 단어의 단어장이 아닙니다.
- 핵심 빠알리 교리 용어, 문헌명, 인명, 중요한 복합어만 기록하십시오.
- 최대 5개입니다. 없으면 [].
- 각 항목은 pali, ko, gloss, note를 포함합니다.
- ko에는 가능한 한 초기불전연구원식 표준 용어를 넣으십시오.
- natural_ko에서 독자용 표현을 사용했더라도 terms에는 표준 번역어를 기록하십시오.
- note는 한 문장 이내로 해당 문맥에서 왜 그렇게 옮겼는지 설명하십시오.
- 일반 접속사, 조사 역할, 의미가 약한 단어, 너무 쉬운 일반어는 넣지 마십시오.
- 제목/표제에서는 문헌명, 장르명, 주석명 같은 식별어를 우선 기록하십시오.

문헌명/장르명 표기 정책:
- 빠알리 문헌명과 장르명은 기본적으로 음역 또는 한국 불교권에서 통용 가능한 원명을 우선하십시오.
- natural_ko에서 독자 이해를 위해 대응되는 한국어명을 괄호로 보조할 수 있습니다.
- 단, 모든 곳에 의무적으로 괄호 설명을 붙이지 말고 필요한 경우에만 보조 설명을 붙이십시오.
- Jātaka → 기본 자따까; 필요 시 자따까(본생경) 또는 자따까(본생담).
- Therīgāthā → 기본 테리가타; 필요 시 테리가타(장로니게).
- Theragāthā → 기본 테라가타; 필요 시 테라가타(장로게).
- Dhammasaṅgaṇī → 기본 담마상가니; 필요 시 담마상가니(법집론).
- Aṭṭhakathā → 주석.
- Ṭīkā → 복주석.
- Vaṇṇanā → 주석 또는 해설; 문맥상 주석 제목이면 주석을 우선하십시오.

grammar_notes 작성 원칙:
- 문법적으로 설명이 필요한 경우에만 사용하십시오.
- 최대 3개입니다. 없으면 [].
- grammar_notes는 모든 단어를 하나씩 분석하는 필드가 아닙니다.
- 모든 단어의 품사/격/수/성/어근을 전부 나열하지 마십시오.
- 해석에 영향을 주는 중요한 문법 요소만 기록하십시오.
- 복합어, 연음, 격 관계, 생략, 관계절, 다의적 구조, 불규칙 형태, 해석상 중요한 동사형만 기록하십시오.
- 단순 문장이나 제목에서는 []로 두십시오.
- 각 항목은 1~2문장 이하로 유지하십시오.
- 모든 단어 형태소 분석은 별도 morphology pipeline의 영역이며, 이 번역 JSON에는 넣지 마십시오.

doctrinal_notes 작성 원칙:
- 교리적으로 중요한 설명만 담으십시오.
- 최대 3개입니다. 없으면 [].
- 각 항목은 1~2문장 이하입니다.
- 본문 번역에 넣기 어려운 교리적 배경만 상좌부/초기불교 문맥에 근거해 적으십시오.
- 주석서적 의미가 중요한 경우 간단히 적으십시오.
- 설법체, 감상문, 현대 심리학적 해설, 자기계발식 조언을 금지합니다.
- 확실하지 않으면 uncertainties에 기록하십시오.

uncertainties 작성 원칙:
- 환각 방지 장치입니다.
- 최대 3개입니다. 없으면 [].
- 해석이 불확실한 문법, 다의어, 문맥, 원문 상태를 기록하십시오.
- 모르면 솔직히 기록하고, 추측을 확정처럼 쓰지 마십시오.
- 불확실성을 natural_ko에서 감추지 마십시오.
- 번역 과정에서 더 적절하거나 더 개연성 높은 해석을 발견했다면 literal_ko와 natural_ko 본문을 그 해석으로 갱신하십시오.
- uncertainties에는 최종적으로 채택하지 않은 대안 해석만 기록하십시오.
- 더 나은 해석을 uncertainties에만 적고 본문에는 덜 적절한 해석을 유지하지 마십시오.
- 둘 이상의 해석이 모두 가능하다고 판단되면, 본문에는 가장 개연성 높은 해석을 채택하고 다른 가능성은 uncertainties에 기록하십시오.
- 고유명사의 격 해석이나 구문 분석이 둘 이상 가능할 경우 본문에는 가장 개연성 높은 해석을 채택하고 다른 해석 가능성은 uncertainties에 기록하십시오.
- 저본 철자를 정규화하거나 다른 형태로 읽어 번역했다면 그 사실을 uncertainties에 기록하십시오. 무언의 정규화는 하지 마십시오.

quality_flags 작성 원칙:
- 모델 자체 품질 진단 결과만 담습니다. 이상 없으면 [].
- 허용되는 값만 사용하십시오:
  - "grammar_uncertain"
  - "doctrinal_risk"
  - "low_confidence"
  - "possible_glossary_conflict"
  - "needs_human_review"
- local validator가 붙이는 flag를 모델이 직접 생성하지 마십시오.
- 생성 금지 예: "json_parse_failed", "schema_validation_failed", "empty_translation", "too_short", "too_long", "contains_untranslated_pali".

출력 길이 제한:
- literal_ko와 natural_ko는 원문 길이에 비례해 간결하게 작성하십시오.
- terms는 최대 5개.
- grammar_notes는 최대 3개.
- doctrinal_notes는 최대 3개.
- uncertainties는 최대 3개.
- 각 note는 1~2문장 이하.
- 단순 문장은 notes 배열을 비워도 됩니다.

배열 타입 규칙:
- terms만 object array입니다.
- grammar_notes는 반드시 string array입니다.
- doctrinal_notes는 반드시 string array입니다.
- uncertainties는 반드시 string array입니다.
- quality_flags는 반드시 string array입니다.
- 금지: grammar_notes, doctrinal_notes, uncertainties 안에 {{"note": "..."}} 같은 object를 넣지 마십시오.

배열 타입 올바른 예:
{{
  "terms": [
    {{
      "pali": "sati",
      "ko": "마음챙김",
      "gloss": "mindfulness",
      "note": "문맥상 수행 요소로 쓰였다."
    }}
  ],
  "grammar_notes": [
    "Araṇavihārīnaṃ은 복수 속격으로 부분속격의 의미를 가진다."
  ],
  "doctrinal_notes": [
    "이 문맥에서 saṅkhāra는 조건 지어진 현상을 가리킨다."
  ],
  "uncertainties": [
    "이 복합어는 문맥에 따라 두 가지 해석이 가능하다."
  ],
  "quality_flags": [
    "grammar_uncertain"
  ]
}}

배열 타입 금지 예:
{{
  "grammar_notes": [
    {{"note": "..."}}
  ],
  "doctrinal_notes": [
    {{"note": "..."}}
  ],
  "uncertainties": [
    {{"note": "..."}}
  ]
}}

반드시 다음 JSON schema만 출력하십시오:
{{
  "literal_ko": "...",
  "natural_ko": "...",
  "terms": [
    {{
      "pali": "...",
      "ko": "...",
      "gloss": "...",
      "note": "..."
    }}
  ],
  "grammar_notes": [],
  "doctrinal_notes": [],
  "uncertainties": [],
  "quality_flags": []
}}

입력 metadata:
- stable_segment_key: {stable_segment_key}
- canonical_ref: {canonical_ref}
- text_layer: {text_layer}
- chunk_type: {chunk_type}
- heading_context: {heading_context}

빠알리 원문:
<<<
{source_text}
>>>""",
)


def render_korean_advanced_prompt_v1(segment: dict[str, Any]) -> str:
    source_text = segment.get("normalized_text") or segment.get("original_text") or ""
    return KOREAN_ADVANCED_PROMPT_V1.template.format(
        stable_segment_key=segment.get("stable_segment_key", ""),
        canonical_ref=segment.get("canonical_ref", ""),
        text_layer=segment.get("text_layer", ""),
        chunk_type=segment.get("chunk_type", ""),
        heading_context=compact_heading_context(segment.get("heading_path") or []),
        source_text=source_text,
    )


def compact_heading_context(heading_path: list[dict[str, Any]]) -> str:
    labels: list[str] = []
    for item in heading_path[-4:]:
        text = str(item.get("text") or "").strip()
        if text:
            labels.append(text)
    return " > ".join(labels) if labels else ""


def validate_korean_advanced_model_output(payload: dict[str, Any]) -> KoreanAdvancedTranslation:
    translation = KoreanAdvancedTranslation.model_validate(payload)
    disallowed_flags = [
        flag for flag in translation.quality_flags
        if flag not in MODEL_SELF_REPORT_QUALITY_FLAGS
    ]
    if disallowed_flags:
        allowed = ", ".join(flag.value for flag in MODEL_SELF_REPORT_QUALITY_FLAGS)
        actual = ", ".join(flag.value for flag in disallowed_flags)
        raise ValueError(f"Model output used disallowed quality_flags: {actual}. Allowed: {allowed}")
    return translation


def prompt_template_manifest() -> dict[str, str]:
    return {
        "prompt_template_id": KOREAN_ADVANCED_PROMPT_ID,
        "prompt_template_version": KOREAN_ADVANCED_PROMPT_VERSION,
        "default_model": KOREAN_ADVANCED_PROMPT_MODEL,
    }


def schema_json_for_docs() -> str:
    return json.dumps(
        {
            "literal_ko": "...",
            "natural_ko": "...",
            "terms": [{"pali": "...", "ko": "...", "gloss": "...", "note": "..."}],
            "grammar_notes": [],
            "doctrinal_notes": [],
            "uncertainties": [],
            "quality_flags": [],
        },
        ensure_ascii=False,
        indent=2,
    )
