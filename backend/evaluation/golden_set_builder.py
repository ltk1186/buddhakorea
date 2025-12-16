"""
Golden Set Builder for Buddhist RAG Evaluation
Generates high-quality Q&A pairs using Gemini 2.0 Flash
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")

# GCP Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0324154376")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
MODEL_NAME = "gemini-2.0-flash-exp"

# Initialize Vertex AI
vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
model = GenerativeModel(MODEL_NAME)

generation_config = GenerationConfig(
    temperature=0.7,  # Higher for diverse questions
    max_output_tokens=2048,
    top_p=0.9,
)


class GoldenSetBuilder:
    """Builds evaluation golden set from CBETA corpus"""

    def __init__(self, source_summaries_path: str, output_path: str):
        self.source_summaries_path = source_summaries_path
        self.output_path = output_path
        self.golden_set = self._load_golden_set()

    def _load_golden_set(self) -> Dict[str, Any]:
        """Load existing golden set or create new one"""
        if os.path.exists(self.output_path):
            with open(self.output_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "metadata": {
                    "version": "1.0",
                    "created_at": time.strftime('%Y-%m-%d'),
                    "description": "Golden evaluation set for Buddhist RAG system",
                    "total_questions": 0,
                    "categories": {
                        "factual": "Factual questions about specific Buddhist concepts",
                        "interpretive": "Questions requiring interpretation of teachings",
                        "comparative": "Questions comparing different sutras or concepts",
                        "practical": "Questions about Buddhist practice"
                    }
                },
                "questions": []
            }

    def _load_source_summaries(self) -> Dict[str, Any]:
        """Load source summaries with Korean translations"""
        with open(self.source_summaries_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def generate_questions_for_sutra(
        self,
        sutra_id: str,
        title_ko: str,
        brief_summary: str,
        detailed_summary: str,
        key_themes: List[str],
        tradition: str,
        num_questions: int = 5
    ) -> List[Dict[str, Any]]:
        """Generate diverse evaluation questions for a specific sutra"""

        prompt = f"""당신은 불교 교육 평가 전문가입니다. 다음 문헌에 대한 평가용 질문-답변 쌍을 생성하세요.

**문헌 정보:**
- ID: {sutra_id}
- 제목: {title_ko}
- 간략 요약: {brief_summary}
- 상세 요약: {detailed_summary}
- 핵심 주제: {', '.join(key_themes)}
- 전통: {tradition}

**작성 요구사항:**
{num_questions}개의 질문-답변 쌍을 생성하세요. 다음 카테고리를 골고루 포함:

1. **factual** (사실 질문): 문헌의 구체적 내용에 대한 질문
   - 예: "이 문헌에서 설명하는 사성제는 무엇인가요?"

2. **interpretive** (해석 질문): 가르침의 의미를 해석하는 질문
   - 예: "이 문헌에서 공(空) 사상은 어떤 의미를 가지나요?"

3. **practical** (실천 질문): 수행과 관련된 질문
   - 예: "이 문헌에 따르면 어떻게 명상을 실천해야 하나요?"

**질문 작성 지침:**
- 자연스러운 한국어로 작성
- 초보자도 이해할 수 있는 명확한 언어 사용
- 문헌의 구체적 내용을 참조할 수 있는 질문
- 너무 일반적이거나 모호하지 않게

**답변 작성 지침:**
- 문헌의 내용을 바탕으로 정확하게 작성
- 200-400자 분량
- 핵심 개념을 명확히 설명
- 필요시 예시 포함

**출력 형식 (JSON):**
```json
[
  {{
    "question": "질문 내용",
    "answer": "답변 내용 (200-400자)",
    "category": "factual|interpretive|practical",
    "sutra_id": "{sutra_id}",
    "difficulty": "easy|medium|hard",
    "key_concepts": ["개념1", "개념2"]
  }},
  ...
]
```

불교학 지식을 바탕으로 {num_questions}개의 고품질 Q&A를 생성하세요.
"""

        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )

            # Extract JSON
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            questions = json.loads(text)

            logger.success(f"✓ Generated {len(questions)} questions for {sutra_id}")
            return questions

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for {sutra_id}: {e}")
            logger.error(f"Raw response: {text[:500]}")
            return []
        except Exception as e:
            logger.error(f"Error generating questions for {sutra_id}: {e}")
            return []

    def build_golden_set(
        self,
        target_count: int = 100,
        questions_per_sutra: int = 5,
        rate_limit_delay: float = 1.0
    ):
        """Build golden set by sampling diverse sutras"""

        logger.info(f"Loading source summaries from {self.source_summaries_path}")
        summaries_data = self._load_source_summaries()
        summaries = summaries_data['summaries']

        # Current count
        current_count = len(self.golden_set['questions'])
        logger.info(f"Current golden set size: {current_count}")

        if current_count >= target_count:
            logger.info(f"Golden set already has {current_count} questions (target: {target_count})")
            return

        needed = target_count - current_count
        num_sutras_needed = (needed + questions_per_sutra - 1) // questions_per_sutra

        logger.info(f"Need {needed} more questions")
        logger.info(f"Will process ~{num_sutras_needed} sutras ({questions_per_sutra} Q/sutra)")

        # Sample diverse sutras across traditions and periods
        sutra_list = list(summaries.items())

        # Track progress
        processed = 0
        total_questions_added = 0

        for sutra_id, summary_data in sutra_list:
            if total_questions_added >= needed:
                break

            # Skip if already have questions from this sutra
            existing_ids = {q['sutra_id'] for q in self.golden_set['questions']}
            if sutra_id in existing_ids:
                continue

            logger.info(f"[{processed+1}/{num_sutras_needed}] Processing {sutra_id}: {summary_data.get('title_ko', 'Unknown')[:50]}...")

            questions = self.generate_questions_for_sutra(
                sutra_id=sutra_id,
                title_ko=summary_data.get('title_ko', 'Unknown'),
                brief_summary=summary_data.get('brief_summary', ''),
                detailed_summary=summary_data.get('detailed_summary', ''),
                key_themes=summary_data.get('key_themes', []),
                tradition=summary_data.get('tradition', 'Unknown'),
                num_questions=questions_per_sutra
            )

            if questions:
                self.golden_set['questions'].extend(questions)
                total_questions_added += len(questions)
                processed += 1

                # Save checkpoint
                self.golden_set['metadata']['total_questions'] = len(self.golden_set['questions'])
                self.golden_set['metadata']['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

                with open(self.output_path, 'w', encoding='utf-8') as f:
                    json.dump(self.golden_set, f, ensure_ascii=False, indent=2)

                logger.info(f"  Added {len(questions)} questions. Total: {len(self.golden_set['questions'])}/{target_count}")

            # Rate limiting
            time.sleep(rate_limit_delay)

        logger.success(f"\n✓ Golden set construction complete!")
        logger.info(f"  Total questions: {len(self.golden_set['questions'])}")
        logger.info(f"  Unique sutras: {len(set(q['sutra_id'] for q in self.golden_set['questions']))}")
        logger.info(f"  Output: {self.output_path}")

        # Category distribution
        categories = {}
        for q in self.golden_set['questions']:
            cat = q.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1

        logger.info(f"\n  Category distribution:")
        for cat, count in categories.items():
            logger.info(f"    {cat}: {count}")


if __name__ == "__main__":
    # Paths
    SUMMARIES_PATH = "../source_explorer/source_data/source_summaries_ko.json"
    OUTPUT_PATH = "golden_set.json"

    # Configuration
    TARGET_COUNT = 100  # Target number of Q&A pairs
    QUESTIONS_PER_SUTRA = 5  # Questions to generate per sutra
    RATE_LIMIT_DELAY = 1.5  # Seconds between API calls

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    logger.info("🔨 Golden Set Builder for Buddhist RAG Evaluation")
    logger.info(f"Target: {TARGET_COUNT} Q&A pairs")
    logger.info(f"Using: {MODEL_NAME}")
    logger.info("Press Ctrl+C to stop (progress will be saved)\n")

    try:
        builder = GoldenSetBuilder(
            source_summaries_path=SUMMARIES_PATH,
            output_path=OUTPUT_PATH
        )

        builder.build_golden_set(
            target_count=TARGET_COUNT,
            questions_per_sutra=QUESTIONS_PER_SUTRA,
            rate_limit_delay=RATE_LIMIT_DELAY
        )

    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user. Progress has been saved.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
