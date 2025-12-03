#!/usr/bin/env python3
"""
Convert detailed_summary style from 합니다체 to 한다체
Uses existing normalized file as base (tradition/period + brief_summary already done)
"""

import json
import re
import time
from pathlib import Path

import vertexai
from vertexai.generative_models import GenerativeModel

# Config
INPUT_FILE = "source_explorer/source_data/source_summaries_ko_normalized.json"
OUTPUT_FILE = "source_explorer/source_data/source_summaries_ko_final.json"
FORBIDDEN_PATTERN = r'(습니다|옵니다|합니다|됩니다|입니다|있습니다|없습니다|였습니다|했습니다|해요|에요|이에요|세요|시요|이옵나이다)(?=[.!?,\s]|$)'

PROMPT_TEMPLATE = """다음 텍스트의 문체를 '합니다/습니다'체에서 '한다/이다'체로 변환해주세요.
내용은 절대 변경하지 말고, 문체만 변환하세요.
변환된 텍스트만 출력하세요.

텍스트:
{text}"""

def main():
    # Initialize Vertex AI
    vertexai.init(project='gen-lang-client-0324154376', location='us-central1')
    model = GenerativeModel("gemini-2.0-flash")

    # Load data
    print(f"Loading {INPUT_FILE}...")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Find records needing conversion
    to_convert = []
    for record_id, record in data['summaries'].items():
        detailed = record.get('detailed_summary', '')
        if detailed and re.search(FORBIDDEN_PATTERN, detailed):
            to_convert.append(record_id)

    print(f"Found {len(to_convert)} records needing detailed_summary conversion")

    # Convert each
    success = 0
    failed = []

    for i, record_id in enumerate(to_convert):
        text = data['summaries'][record_id]['detailed_summary']

        try:
            # Save original
            data['summaries'][record_id]['_original_detailed_summary'] = text

            # Convert
            prompt = PROMPT_TEMPLATE.format(text=text)
            response = model.generate_content(prompt)

            if response.text:
                converted = response.text.strip()
                # Sanity check
                if 0.5 < len(converted) / len(text) < 2.0:
                    data['summaries'][record_id]['detailed_summary'] = converted
                    data['summaries'][record_id]['detailed_style_status'] = 'completed'
                    success += 1
                else:
                    failed.append((record_id, 'length_mismatch'))
            else:
                failed.append((record_id, 'empty_response'))

        except Exception as e:
            failed.append((record_id, str(e)))

        # Progress
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(to_convert)} ({success} success, {len(failed)} failed)")

        # Rate limit
        time.sleep(0.3)

    print(f"\nCompleted: {success} success, {len(failed)} failed")

    # Save result
    print(f"Saving to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Report failures
    if failed:
        print("\nFailed records:")
        for rid, reason in failed[:10]:
            print(f"  {rid}: {reason}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")

    print("\nDone!")

if __name__ == '__main__':
    main()
