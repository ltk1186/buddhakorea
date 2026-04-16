"""Versioned prompt registry for the Buddha Korea RAG runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from langchain_core.prompts import PromptTemplate


@dataclass(frozen=True)
class PromptSpec:
    """Code-owned prompt definition with a stable operational identifier."""

    id: str
    version: str
    mode: str
    template: str
    input_variables: Tuple[str, ...] = ("context", "question")
    description: str = ""

    @property
    def registry_key(self) -> str:
        return f"{self.id}_{self.version}"

    def render_template(self, **template_vars: str) -> str:
        template = self.template
        for key, value in template_vars.items():
            template = template.replace(f"{{{key}}}", value)
        return template

    def to_prompt(self, **template_vars: str) -> PromptTemplate:
        return PromptTemplate(
            template=self.render_template(**template_vars),
            input_variables=list(self.input_variables),
        )


NORMAL_PROMPT_ID = "normal_v1"
DETAILED_PROMPT_ID = "detailed_v1"
SUTRA_FILTER_PROMPT_ID = "sutra_filter_v1"
SUTRA_FILTER_DETAILED_PROMPT_ID = "sutra_filter_detailed_v1"
TRADITION_FILTER_PROMPT_ID = "tradition_filter_v1"
TRADITION_FILTER_DETAILED_PROMPT_ID = "tradition_filter_detailed_v1"
STREAMING_NORMAL_PROMPT_ID = "streaming_normal_v1"
STREAMING_DETAILED_PROMPT_ID = "streaming_detailed_v1"


PROMPT_REGISTRY: Dict[str, PromptSpec] = {
    NORMAL_PROMPT_ID: PromptSpec(
        id="normal",
        version="v1",
        mode="normal",
        description="Default cross-corpus Buddhist RAG answer prompt.",
        template="""아래 제공된 불교 문헌 내용을 참고하여 질문에 상세하게 답변하세요.

**답변 지침:**
- 문헌의 내용을 기반으로 정확하고 명확하게 설명하세요
- 여러 전통(초기불교, 대승불교 등)의 관점이 다를 수 있다면 각 관점을 소개하세요
- 문헌 내용을 인용할 때는 인용 표시를 하세요
- 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
- 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
{context}

Question: {question}

Answer (한국어 또는 영어로 상세히 답변):""",
    ),
    DETAILED_PROMPT_ID: PromptSpec(
        id="detailed",
        version="v1",
        mode="detailed",
        description="Detailed cross-corpus Buddhist RAG answer prompt.",
        template="""아래 제공된 불교 문헌 내용을 참고하여 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 전통(초기불교, 대승불교 등)의 관점이 다를 수 있다면 각 관점을 자세히 소개하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락, 다른 가르침과의 연결고리를 포함하여 종합적으로 설명하세요
5. 가능한 한 구체적인 예시와 비유를 들어 설명하세요
6. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
7. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
{context}

Question: {question}

Answer:""",
    ),
    SUTRA_FILTER_PROMPT_ID: PromptSpec(
        id="sutra_filter",
        version="v1",
        mode="sutra_filter",
        description="Single-sutra constrained answer prompt.",
        template="""아래 문헌 내용을 바탕으로 답변하세요.

**답변 지침:**
1. 문헌에 제공된 내용을 최대한 활용하여 답변하세요
2. 직접적인 언급이 없더라도 문헌에 관련된 내용이 있다면 그것을 바탕으로 설명하세요
3. 문헌의 내용을 인용할 때는 인용 표시를 하세요
4. 다른 문헌이나 일반적인 불교 지식은 언급하지 마세요 (오직 이 문헌의 내용만)
5. 문헌에 전혀 관련이 없는 질문이라면, "이 문헌에서는 해당 주제를 다루지 않습니다"라고 답변하세요
6. 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
7. 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
{context}

Question: {question}

Answer:""",
    ),
    SUTRA_FILTER_DETAILED_PROMPT_ID: PromptSpec(
        id="sutra_filter_detailed",
        version="v1",
        mode="sutra_filter_detailed",
        description="Detailed single-sutra constrained answer prompt.",
        template="""아래 문헌 내용을 바탕으로 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 관점과 해석이 있다면 모두 소개하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락, 다른 가르침과의 연결고리를 포함하여 종합적으로 설명하세요
5. 다른 문헌이나 일반적인 불교 지식은 언급하지 마세요 (오직 이 문헌의 내용만)
6. 문헌에 전혀 관련이 없는 질문이라면, "이 문헌에서는 해당 주제를 다루지 않습니다"라고 답변하세요
7. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
8. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
{context}

Question: {question}

Answer:""",
    ),
    TRADITION_FILTER_PROMPT_ID: PromptSpec(
        id="tradition_filter",
        version="v1",
        mode="tradition_filter",
        description="Tradition-constrained answer prompt.",
        template="""아래 {tradition} 문헌 내용을 바탕으로 답변하세요.

**답변 지침:**
1. 문헌에 제공된 내용을 최대한 활용하여 답변하세요
2. {tradition}의 관점에서 설명하세요
3. 문헌의 내용을 인용할 때는 인용 표시를 하세요
4. 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
5. 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
{context}

Question: {question}

Answer:""",
    ),
    TRADITION_FILTER_DETAILED_PROMPT_ID: PromptSpec(
        id="tradition_filter_detailed",
        version="v1",
        mode="tradition_filter_detailed",
        description="Detailed tradition-constrained answer prompt.",
        template="""아래 {tradition} 문헌 내용을 바탕으로 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. {tradition}의 관점과 해석을 중심으로 답변하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. 역사적 배경, 맥락을 포함하여 종합적으로 설명하세요
5. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
6. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
{context}

Question: {question}

Answer:""",
    ),
    STREAMING_NORMAL_PROMPT_ID: PromptSpec(
        id="streaming_normal",
        version="v1",
        mode="streaming_normal",
        description="Default prompt for the streaming chat endpoint.",
        template="""아래 제공된 불교 문헌 내용을 참고하여 질문에 상세하게 답변하세요.

**답변 지침:**
- 문헌의 내용을 기반으로 정확하고 명확하게 설명하세요
- 여러 전통(초기불교, 대승불교 등)의 관점이 다를 수 있다면 각 관점을 소개하세요
- 문헌 내용을 인용할 때는 인용 표시를 하세요
- 마크다운 헤더(#, ##, ###)를 사용하지 말고 일반 텍스트로 작성하세요
- 자기소개나 서두 없이 바로 본론으로 시작하세요

참고 문헌:
{context}

Question: {question}

Answer:""",
    ),
    STREAMING_DETAILED_PROMPT_ID: PromptSpec(
        id="streaming_detailed",
        version="v1",
        mode="streaming_detailed",
        description="Detailed prompt for the streaming chat endpoint.",
        template="""아래 문헌 내용을 바탕으로 **가능한 한 상세하고 포괄적으로** 답변하세요.

**답변 지침:**
1. 문헌에 제공된 모든 관련 내용을 최대한 활용하여 **깊이 있게** 설명하세요
2. 여러 관점과 해석이 있다면 모두 소개하세요
3. 문헌 원문을 인용할 때는 인용 표시를 하고, 그 의미를 자세히 풀어 설명하세요
4. **마크다운 헤더(#, ##, ###)를 절대 사용하지 마세요**
5. **자기소개나 서두 없이 바로 본론으로 시작하세요**

참고 문헌:
{context}

Question: {question}

Answer:""",
    ),
}


def build_prompt(prompt_id: str, **template_vars: str) -> PromptTemplate:
    """Build a LangChain prompt from a registry key."""

    return PROMPT_REGISTRY[prompt_id].to_prompt(**template_vars)


def get_prompt_spec(prompt_id: str) -> PromptSpec:
    """Return the prompt spec for a stable registry key."""

    return PROMPT_REGISTRY[prompt_id]
