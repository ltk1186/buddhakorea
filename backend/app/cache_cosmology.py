#!/usr/bin/env python3
"""
Script to add cosmology and heavenly realms response to cache.
Run this after you've received a good response about cosmology (우주론과 천상).
"""

import json
from datetime import datetime
from pathlib import Path

def add_cosmology_to_cache(response_text: str, sources: list):
    """Add cosmology topic to the response cache."""

    cache_file = Path(__file__).parent / 'cached_responses.json'

    # Load existing cache
    with open(cache_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Add cosmology cache entry
    data['cached_responses']['cosmology_heavens'] = {
        'keywords': [
            '우주론',
            '천상',
            '천상세계',
            '삼계',
            '욕계',
            '색계',
            '무색계',
            'cosmology',
            '불교 우주론',
            '수미산',
            '수미산 우주론'
        ],
        'response': response_text,
        'sources': sources,
        'model': 'gemini-2.5-pro',
        'created_at': datetime.now().isoformat(),
        'hit_count': 0,
        'last_hit': None,
        'metadata': {
            'quality_rating': 'high',
            'manually_curated': True,
            'description': '불교 우주론과 천상세계에 대한 상세한 설명'
        }
    }

    # Save updated cache
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✓ Added 'cosmology_heavens' to cache")
    print(f"  Keywords: {len(data['cached_responses']['cosmology_heavens']['keywords'])}")
    print(f"  Response length: {len(response_text)} chars")
    print(f"  Sources: {len(sources)}")


if __name__ == '__main__':
    print("To cache your cosmology response:")
    print("1. First, make a query: '우주론과 천상에 대해 설명해줘'")
    print("2. Copy the response text and sources from the API response")
    print("3. Call add_cosmology_to_cache(response_text, sources)")
    print("\nOr you can manually edit cached_responses.json and add the entry following the existing format.")
