"""
Generate Korean AI Summaries for Buddhist Sources
Uses Gemini 2.0 Flash via Vertex AI to create professional Korean translations and summaries
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
# Available models (in order of preference):
# 1. "gemini-2.0-flash-exp" - Gemini 2.0 Flash (experimental, but newer & faster)
# 2. "gemini-1.5-flash-002" - Gemini 1.5 Flash stable (2000 req/min quota)
# 3. "gemini-1.5-pro-002" - Gemini 1.5 Pro (higher quality, lower quota)
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

    Implements exponential backoff for rate limit errors.

    Returns:
        {
            'title_ko': '한글 제목',
            'brief_summary': '100-150자 요약',
            'detailed_summary': '500-800자 상세 요약',
            'key_themes': ['주제1', '주제2', ...],
            'period': '시대',
            'tradition': '전통 (초기불교/대승/밀교 등)'
        }
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


def generate_all_summaries(
    catalog_path: str,
    output_path: str,
    start_from: int = 0,
    batch_size: int = 50,
    rate_limit_delay: float = 1.0
):
    """
    Generate Korean summaries for all sources in the catalog.
    """
    logger.info(f"Loading source catalog from {catalog_path}")

    with open(catalog_path, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    sources = catalog['sources']
    total = len(sources)

    logger.info(f"Total sources: {total:,}")
    logger.info(f"Starting from index: {start_from}")
    logger.info(f"Using model: {MODEL_NAME}")
    logger.info(f"Rate limit: {rate_limit_delay}s between requests")

    # Load existing summaries if resuming
    summaries = {}
    if os.path.exists(output_path):
        logger.info(f"Loading existing summaries from {output_path}")
        with open(output_path, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            summaries = existing_data.get('summaries', {})
        logger.info(f"Loaded {len(summaries)} existing summaries")

    # Process sources
    source_items = list(sources.items())
    processed = 0
    errors = 0

    for i, (sutra_id, source_info) in enumerate(source_items):
        if i < start_from:
            continue

        # Skip if already processed
        if sutra_id in summaries:
            logger.info(f"[{i+1}/{total}] Skipping {sutra_id} (already processed)")
            continue

        logger.info(f"[{i+1}/{total}] Processing {sutra_id}: {source_info.get('title', 'Unknown')[:50]}...")

        summary = generate_korean_summary(
            sutra_id=sutra_id,
            title=source_info.get('title', 'Unknown'),
            author=source_info.get('author', 'Unknown'),
            sample_text=source_info.get('sample_text', ''),
            volume=source_info.get('volume', 'Unknown'),
            juan=source_info.get('juan', 'Unknown')
        )

        if summary:
            summaries[sutra_id] = {
                **summary,
                'original_title': source_info.get('title', 'Unknown'),
                'author': source_info.get('author', 'Unknown'),
                'volume': source_info.get('volume', 'Unknown'),
                'juan': source_info.get('juan', 'Unknown'),
            }
            processed += 1
        else:
            errors += 1

        # Save checkpoint every batch_size
        if (processed + errors) % batch_size == 0:
            logger.info(f"Checkpoint: Saving {len(summaries)} summaries to {output_path}")
            save_summaries(summaries, output_path, total)

        # Rate limiting
        time.sleep(rate_limit_delay)

    # Final save
    logger.info(f"Saving final results to {output_path}")
    save_summaries(summaries, output_path, total)

    logger.info("✓ Summary generation complete!")
    logger.info(f"  Total processed: {processed}")
    logger.info(f"  Errors: {errors}")
    logger.info(f"  Output file: {output_path}")


def save_summaries(summaries: Dict[str, Any], output_path: str, total_sources: int):
    """Save summaries to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    output_data = {
        'total_sources': total_sources,
        'summaries_generated': len(summaries),
        'model': MODEL_NAME,
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'summaries': summaries
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Configuration
    CATALOG_PATH = "source_data/source_catalog.json"
    OUTPUT_PATH = "source_data/source_summaries_ko.json"

    # Resume from specific index if needed (use 0 to start fresh)
    START_FROM = 0

    # Batch size for checkpoints
    BATCH_SIZE = 50

    # Rate limiting (seconds between API calls)
    # Gemini 2.0 Flash experimental: ~300 req/min quota
    # Gemini 1.5 Flash stable: ~2000 req/min quota
    # Safe rate: 0.2s delay = 5 req/sec = 300 req/min (leaves headroom)
    RATE_LIMIT_DELAY = 0.2  # 5 requests/second = ~8 minutes for 2233 remaining sources

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Check if catalog exists
    if not os.path.exists(CATALOG_PATH):
        logger.error(f"Source catalog not found at {CATALOG_PATH}")
        logger.error("Please run extract_sources.py first")
        sys.exit(1)

    logger.info("Starting Korean summary generation with Gemini 2.0 Flash")
    logger.info(f"This will process {2410} sources (~20-30 minutes at 2 req/sec)")
    logger.info("Press Ctrl+C to stop (progress will be saved)")

    try:
        generate_all_summaries(
            catalog_path=CATALOG_PATH,
            output_path=OUTPUT_PATH,
            start_from=START_FROM,
            batch_size=BATCH_SIZE,
            rate_limit_delay=RATE_LIMIT_DELAY
        )
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user. Progress has been saved.")
        logger.info(f"To resume, the script will automatically skip already processed sources")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
