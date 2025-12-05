"""
Retry Korean Summary Generation for Failed Sources
Processes only the 35 sources that failed due to rate limits
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
MODEL_NAME = "gemini-2.0-flash-exp"

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
    max_retries: int = 8  # Increased from 5
) -> Optional[Dict[str, Any]]:
    """
    Generate Korean translation and summaries for a Buddhist text using Gemini.
    Implements exponential backoff for rate limit errors.
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

            logger.success(f"✓ Generated summary for {sutra_id}")
            return summary_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for {sutra_id}: {e}")
            logger.error(f"Raw response: {text[:500]}")
            return None
        except Exception as e:
            error_msg = str(e)

            # Check if it's a rate limit error (429)
            if "429" in error_msg or "Resource exhausted" in error_msg or "quota" in error_msg.lower():
                if attempt < max_retries - 1:
                    # Longer exponential backoff: 4^attempt seconds
                    backoff = 4 ** (attempt + 1)
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


def retry_failed_summaries():
    """
    Retry generating summaries for the 35 failed sources.
    """
    CATALOG_PATH = "source_data/source_catalog.json"
    FAILED_PATH = "source_data/failed_sources.json"
    SUMMARIES_PATH = "source_data/source_summaries_ko.json"
    RETRY_OUTPUT_PATH = "source_data/retry_summaries.json"

    logger.info("Loading failed sources...")
    with open(FAILED_PATH, 'r', encoding='utf-8') as f:
        failed_data = json.load(f)

    failed_ids = failed_data['failed_ids']
    failed_details = failed_data['details']

    logger.info(f"Found {len(failed_ids)} failed sources to retry")
    logger.info(f"Using model: {MODEL_NAME}")
    logger.info(f"Rate limit: 5s between requests (much slower to avoid 429s)")

    # Process failed sources
    retry_summaries = {}
    errors = []

    for i, sutra_id in enumerate(failed_ids, 1):
        source_info = failed_details[sutra_id]

        logger.info(f"[{i}/{len(failed_ids)}] Retrying {sutra_id}: {source_info.get('title', 'Unknown')[:50]}...")

        summary = generate_korean_summary(
            sutra_id=sutra_id,
            title=source_info.get('title', 'Unknown'),
            author=source_info.get('author', 'Unknown'),
            sample_text=source_info.get('sample_text', ''),
            volume=source_info.get('volume', 'Unknown'),
            juan=source_info.get('juan', 'Unknown')
        )

        if summary:
            retry_summaries[sutra_id] = {
                **summary,
                'original_title': source_info.get('title', 'Unknown'),
                'author': source_info.get('author', 'Unknown'),
                'volume': source_info.get('volume', 'Unknown'),
                'juan': source_info.get('juan', 'Unknown'),
            }
        else:
            errors.append(sutra_id)

        # Save checkpoint after each success
        if retry_summaries:
            with open(RETRY_OUTPUT_PATH, 'w', encoding='utf-8') as f:
                json.dump({
                    'retried_count': len(retry_summaries),
                    'remaining_errors': len(errors),
                    'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'summaries': retry_summaries
                }, f, ensure_ascii=False, indent=2)

        # Rate limiting - wait 5 seconds between requests (slower than before)
        time.sleep(5.0)

    # Merge with existing summaries
    logger.info(f"\nMerging {len(retry_summaries)} new summaries with existing summaries...")

    with open(SUMMARIES_PATH, 'r', encoding='utf-8') as f:
        existing_data = json.load(f)

    # Add new summaries
    existing_data['summaries'].update(retry_summaries)
    existing_data['summaries_generated'] = len(existing_data['summaries'])
    existing_data['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')

    # Save merged results
    with open(SUMMARIES_PATH, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    logger.success("\n✓ Retry complete!")
    logger.info(f"  Successfully generated: {len(retry_summaries)}")
    logger.info(f"  Still failed: {len(errors)}")
    logger.info(f"  Total summaries now: {len(existing_data['summaries'])}/2410")
    logger.info(f"  Updated file: {SUMMARIES_PATH}")

    if errors:
        logger.warning(f"\n  Sources still failing: {errors}")


if __name__ == "__main__":
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    logger.info("Starting retry of 35 failed summaries with Gemini 2.0 Flash")
    logger.info("Using slower rate (5s between requests) to avoid rate limits")
    logger.info("Estimated time: ~3-5 minutes for 35 sources")
    logger.info("Press Ctrl+C to stop (progress will be saved)\n")

    try:
        retry_failed_summaries()
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user. Progress has been saved.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
