#!/usr/bin/env python3
"""
Generate Korean summaries for the 3 missing cosmology sources.
T53n2122, T54n2127, T55n2145
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")

# GCP Configuration
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0324154376")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
MODEL_NAME = "gemini-2.0-flash-exp"  # Using latest Gemini 2.0 Flash

# Initialize Vertex AI
vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
model = GenerativeModel(MODEL_NAME)

# Generation config
generation_config = GenerationConfig(
    temperature=0.3,
    max_output_tokens=1024,
    top_p=0.9,
)


def generate_korean_summary(
    sutra_id: str,
    title: str,
    author: str,
    sample_text: str,
    volume: str,
    juan: str,
    max_retries: int = 5
) -> Optional[Dict[str, Any]]:
    """
    Generate Korean translation and summaries for a Buddhist text using Gemini.
    """

    prompt = f"""당신은 불교 문헌 전문가입니다. 다음 CBETA 대장경 텍스트의 한글 번역 및 요약을 작성해주세요.

**원문 정보:**
- 문헌 ID: {sutra_id}
- 원제목: {title}
- 저자/역자: {author}
- 권수: {volume}, 卷: {juan}

**원문 샘플:**
{sample_text[:1500]}

**작성 요구사항:**
1. **한글 제목** (title_ko): 원제목을 읽기 쉬운 한글로 번역. 한자는 괄호 안에 병기.
2. **간략 요약** (brief_summary): 이 문헌의 핵심 내용을 100-150자로 요약. 사용자가 목록에서 이 문헌이 무엇인지 즉시 이해할 수 있도록.
3. **상세 요약** (detailed_summary): 500-800자 상세 요약. 다음을 포함:
   - 이 문헌의 주요 가르침
   - 역사적/교리적 맥락
   - 중요한 개념이나 일화
   - 불교 수행에서의 의의
4. **핵심 주제** (key_themes): 3-5개의 핵심 주제/개념 (예: "사성제", "공사상", "보살행" 등)
5. **시대** (period): 추정 성립 시대 (예: "초기불교", "대승 초기", "중국 당나라" 등)
6. **전통** (tradition): 불교 전통 (예: "초기불교", "대승불교", "선종", "밀교" 등)

**JSON 형식으로 출력:**
```json
{{
  "title_ko": "한글 제목 (漢字)",
  "brief_summary": "100-150자 간략 요약",
  "detailed_summary": "500-800자 상세 요약. 단락 구분을 위해 \\n\\n 사용 가능.",
  "key_themes": ["주제1", "주제2", "주제3"],
  "period": "시대",
  "tradition": "전통"
}}
```

원문 샘플이 충분하지 않거나 문헌 ID/제목만으로 알 수 있는 유명한 문헌의 경우, 불교학 지식을 바탕으로 작성하세요.
"""

    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )

            # Extract JSON from response
            text = response.text.strip()

            # Remove markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            # Parse JSON
            summary_data = json.loads(text)

            return summary_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for {sutra_id}: {e}")
            logger.error(f"Raw response: {text[:500]}")
            return None
        except Exception as e:
            error_msg = str(e)

            # Check if it's a rate limit error (429)
            if "429" in error_msg or "Resource exhausted" in error_msg:
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    backoff = 2 ** (attempt + 1)
                    logger.warning(f"Rate limit hit for {sutra_id}. Retrying in {backoff}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(backoff)
                    continue
                else:
                    logger.error(f"Max retries exceeded for {sutra_id} due to rate limits")
                    return None
            else:
                logger.error(f"Error generating summary for {sutra_id}: {e}")
                return None

    return None


def generate_three_missing_summaries():
    """Generate summaries for the 3 missing cosmology sources."""

    script_dir = Path(__file__).parent
    catalog_path = script_dir / "source_data" / "source_catalog.json"
    summaries_path = script_dir / "source_data" / "source_summaries_ko.json"

    # Load source catalog
    logger.info(f"Loading source catalog from {catalog_path}")
    with open(catalog_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    sources = catalog['sources']

    # Load existing summaries
    logger.info(f"Loading existing summaries from {summaries_path}")
    with open(summaries_path, 'r', encoding='utf-8') as f:
        summaries_data = json.load(f)

    existing_summaries = summaries_data.get('summaries', {})
    logger.info(f"Loaded {len(existing_summaries)} existing summaries")

    # The 3 missing sources
    missing_ids = ['T53n2122', 'T54n2127', 'T55n2145']

    logger.info(f"Generating summaries for {len(missing_ids)} missing sources")
    logger.info(f"Using model: {MODEL_NAME}")

    generated = 0
    errors = 0

    for sutra_id in missing_ids:
        # Skip if already exists
        if sutra_id in existing_summaries:
            logger.info(f"✓ {sutra_id} already exists in summaries, skipping")
            continue

        # Get source info from catalog
        if sutra_id not in sources:
            logger.error(f"✗ {sutra_id} not found in source catalog!")
            errors += 1
            continue

        source_info = sources[sutra_id]
        logger.info(f"Processing {sutra_id}: {source_info.get('title', 'Unknown')[:50]}...")

        # Generate summary
        summary = generate_korean_summary(
            sutra_id=sutra_id,
            title=source_info.get('title', 'Unknown'),
            author=source_info.get('author', 'Unknown'),
            sample_text=source_info.get('sample_text', ''),
            volume=source_info.get('volume', 'Unknown'),
            juan=source_info.get('juan', 'Unknown')
        )

        if summary:
            existing_summaries[sutra_id] = {
                **summary,
                'original_title': source_info.get('title', 'Unknown'),
                'author': source_info.get('author', 'Unknown'),
                'volume': source_info.get('volume', 'Unknown'),
                'juan': source_info.get('juan', 'Unknown'),
            }
            logger.info(f"✓ Generated summary for {sutra_id}")
            generated += 1
        else:
            logger.error(f"✗ Failed to generate summary for {sutra_id}")
            errors += 1

        # Small delay between requests
        time.sleep(1.0)

    # Save updated summaries
    if generated > 0:
        logger.info(f"Saving {len(existing_summaries)} summaries to {summaries_path}")
        summaries_data['summaries'] = existing_summaries
        summaries_data['summaries_generated'] = len(existing_summaries)

        with open(summaries_path, 'w', encoding='utf-8') as f:
            json.dump(summaries_data, f, ensure_ascii=False, indent=2)

        logger.info("✓ Summary generation complete!")
        logger.info(f"  New summaries generated: {generated}")
        logger.info(f"  Errors: {errors}")
        logger.info(f"  Total summaries in database: {len(existing_summaries)}")
    else:
        logger.info("No new summaries generated (all sources already exist or failed)")


if __name__ == "__main__":
    logger.info("Generating Korean summaries for 3 missing cosmology sources")
    logger.info("Sources: T53n2122, T54n2127, T55n2145")

    try:
        generate_three_missing_summaries()
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
