#!/usr/bin/env python
"""
Test Buddhist RAG system with common Korean and English Buddhist terminology.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.embedder import Embedder, EmbedderConfig
from src.vectordb import VectorDB, VectorDBConfig
from src.retriever import Retriever, RetrieverConfig

# Load environment
load_dotenv()

# Test terms
KOREAN_TERMS = [
    "사성제",           # Four Noble Truths
    "팔정도",           # Noble Eightfold Path
    "연기",             # Dependent Origination
    "무상",             # Impermanence
    "공",               # Emptiness
    "열반",             # Nirvana
    "보살",             # Bodhisattva
    "선정",             # Meditation/Dhyana
    "지혜",             # Wisdom/Prajna
    "자비",             # Compassion
]

ENGLISH_TERMS = [
    "Four Noble Truths",
    "Eightfold Path",
    "dependent origination",
    "impermanence",
    "emptiness",
    "nirvana",
    "bodhisattva",
    "meditation",
    "wisdom",
    "compassion",
]


def test_terms(terms, language):
    """Test retrieval for a list of terms."""
    print(f"\n{'='*80}")
    print(f"Testing {language} Buddhist Terms")
    print(f"{'='*80}\n")

    # Initialize components
    embedder_config = EmbedderConfig(
        backend="local",
        local_model="BAAI/bge-m3",
        embedding_dim=1024,  # BGE-M3 uses 1024 dimensions
    )
    embedder = Embedder.from_config(embedder_config)

    vectordb_config = VectorDBConfig(
        collection_name="taisho_canon",
        persist_directory="./data/chroma_db",
    )
    vectordb = VectorDB.from_config(vectordb_config)

    retriever_config = RetrieverConfig(
        top_k=3,
        similarity_threshold=0.0,
    )
    retriever = Retriever(embedder, vectordb, retriever_config)

    results = []

    for i, term in enumerate(terms, 1):
        print(f"\n{i}. Testing: '{term}'")
        print("-" * 60)

        try:
            retrieval_results = retriever.retrieve(term)

            if retrieval_results:
                top_score = retrieval_results[0].score
                num_results = len(retrieval_results)

                # Get preview of top result
                preview = retrieval_results[0].text[:100].replace('\n', ' ')

                print(f"   ✓ Found {num_results} results")
                print(f"   ✓ Top score: {top_score:.4f}")
                print(f"   ✓ Preview: {preview}...")

                results.append({
                    'term': term,
                    'score': top_score,
                    'num_results': num_results,
                    'success': True
                })
            else:
                print(f"   ✗ No results found")
                results.append({
                    'term': term,
                    'score': 0.0,
                    'num_results': 0,
                    'success': False
                })

        except Exception as e:
            print(f"   ✗ Error: {e}")
            results.append({
                'term': term,
                'score': 0.0,
                'num_results': 0,
                'success': False,
                'error': str(e)
            })

    return results


def print_summary(korean_results, english_results):
    """Print summary statistics."""
    print(f"\n{'='*80}")
    print("SUMMARY RESULTS")
    print(f"{'='*80}\n")

    # Korean summary
    korean_scores = [r['score'] for r in korean_results if r['success']]
    korean_success = sum(1 for r in korean_results if r['success'])

    print(f"Korean Terms ({korean_success}/{len(korean_results)} successful):")
    print(f"  Average score: {sum(korean_scores)/len(korean_scores):.4f}" if korean_scores else "  No successful queries")
    print(f"  Max score: {max(korean_scores):.4f}" if korean_scores else "")
    print(f"  Min score: {min(korean_scores):.4f}" if korean_scores else "")

    # English summary
    english_scores = [r['score'] for r in english_results if r['success']]
    english_success = sum(1 for r in english_results if r['success'])

    print(f"\nEnglish Terms ({english_success}/{len(english_results)} successful):")
    print(f"  Average score: {sum(english_scores)/len(english_scores):.4f}" if english_scores else "  No successful queries")
    print(f"  Max score: {max(english_scores):.4f}" if english_scores else "")
    print(f"  Min score: {min(english_scores):.4f}" if english_scores else "")

    # Detailed comparison table
    print(f"\n{'='*80}")
    print("DETAILED COMPARISON")
    print(f"{'='*80}\n")
    print(f"{'Rank':<6} {'Korean Term':<20} {'Score':<10} {'English Term':<25} {'Score':<10}")
    print("-" * 80)

    for i in range(len(korean_results)):
        k_term = korean_results[i]['term']
        k_score = f"{korean_results[i]['score']:.4f}" if korean_results[i]['success'] else "FAILED"
        e_term = english_results[i]['term']
        e_score = f"{english_results[i]['score']:.4f}" if english_results[i]['success'] else "FAILED"

        print(f"{i+1:<6} {k_term:<20} {k_score:<10} {e_term:<25} {e_score:<10}")

    # Score comparison
    print(f"\n{'='*80}")
    print("LANGUAGE PERFORMANCE ANALYSIS")
    print(f"{'='*80}\n")

    if korean_scores and english_scores:
        avg_diff = sum(english_scores)/len(english_scores) - sum(korean_scores)/len(korean_scores)
        print(f"English outperforms Korean by: {avg_diff:+.4f} points on average")
        print(f"Recommended query language: {'English' if avg_diff > 0 else 'Korean'}")
        print(f"\nNote: Chinese (四聖諦 style) queries likely perform best (0.924 observed)")


if __name__ == "__main__":
    print("Buddhist RAG System - Comprehensive Term Testing")
    print("Testing BGE-M3 embeddings on CBETA T01 volume")

    # Run tests
    korean_results = test_terms(KOREAN_TERMS, "Korean")
    english_results = test_terms(ENGLISH_TERMS, "English")

    # Print summary
    print_summary(korean_results, english_results)

    print(f"\n{'='*80}")
    print("Testing complete!")
    print(f"{'='*80}\n")
