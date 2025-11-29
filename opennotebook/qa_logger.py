"""
Q&A Logger for Buddha Korea RAG System

Logs all question-answer pairs with metadata for analysis and caching.
Stores full queries and responses (no truncation) in JSONL format.
PII is automatically masked before logging.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from privacy import mask_pii

# Q&A log file path (DEPRECATED: Cloud Logging을 통해 BigQuery로 분석 예정)
# 로컬 개발/테스트용으로만 유지
QA_LOG_FILE = Path("logs/qa_pairs.jsonl")


def log_qa_pair(
    query: str,
    response: str,
    detailed_mode: bool = False,
    sutra_filter: Optional[str] = None,
    session_id: Optional[str] = None,
    model: str = "unknown",
    sources: Optional[List[str]] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: Optional[int] = None,
    from_cache: bool = False
) -> None:
    """
    Log a complete Q&A pair to JSONL file.

    Args:
        query: Full user query (no truncation)
        response: Full LLM response (no truncation)
        detailed_mode: Whether /자세히 mode was used
        sutra_filter: T-number if /경전 filter was used
        session_id: Session ID (optional)
        model: Model name used for generation
        sources: List of source documents referenced
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        latency_ms: Response latency in milliseconds
        from_cache: Whether response was from cache
    """
    # Mask PII before logging
    masked_query = mask_pii(query)
    masked_response = mask_pii(response)

    # Create Q&A entry
    qa_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": masked_query,  # Full query, PII masked
        "response": masked_response,  # Full response, PII masked
        "detailed_mode": detailed_mode,
        "sutra_filter": sutra_filter,
        "session_id": session_id,
        "model": model,
        "sources": sources or [],
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens
        },
        "latency_ms": latency_ms,
        "from_cache": from_cache
    }

    # Log the structured data using loguru (this will go to stdout as JSON)
    # Using logger.bind() to attach structured data that serialize=True will include
    logger.bind(qa=qa_entry).info("Q&A pair logged")


def get_qa_pairs(
    days: int = 7,
    limit: Optional[int] = None,
    detailed_mode_only: bool = False,
    sutra_filter_only: bool = False,
    sutra_filter: Optional[str] = None
) -> List[Dict]:
    """
    Retrieve Q&A pairs with optional filtering.

    Args:
        days: Number of days to retrieve (from now backwards)
        limit: Maximum number of pairs to return (most recent first)
        detailed_mode_only: Only return pairs with detailed_mode=True
        sutra_filter_only: Only return pairs with sutra_filter set
        sutra_filter: Only return pairs with specific T-number

    Returns:
        List of Q&A pair dictionaries
    """
    if not QA_LOG_FILE.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days)
    pairs = []

    try:
        with open(QA_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())

                    # Parse timestamp
                    timestamp = datetime.fromisoformat(entry["timestamp"])

                    # Skip if outside date range
                    if timestamp < cutoff:
                        continue

                    # Apply filters
                    if detailed_mode_only and not entry.get("detailed_mode", False):
                        continue

                    if sutra_filter_only and not entry.get("sutra_filter"):
                        continue

                    if sutra_filter and entry.get("sutra_filter") != sutra_filter:
                        continue

                    pairs.append(entry)

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Error parsing Q&A entry: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error reading Q&A logs: {e}")

    # Sort by timestamp descending (most recent first)
    pairs.sort(key=lambda x: x["timestamp"], reverse=True)

    # Apply limit
    if limit:
        pairs = pairs[:limit]

    return pairs


def export_to_json(
    output_file: str = "logs/qa_pairs_export.json",
    days: int = 30,
    detailed_mode_only: bool = False,
    sutra_filter_only: bool = False
) -> bool:
    """
    Export Q&A pairs to a single JSON file.

    Args:
        output_file: Output JSON file path
        days: Number of days to export
        detailed_mode_only: Only export pairs with detailed_mode=True
        sutra_filter_only: Only export pairs with sutra_filter set

    Returns:
        True if successful, False otherwise
    """
    try:
        pairs = get_qa_pairs(
            days=days,
            detailed_mode_only=detailed_mode_only,
            sutra_filter_only=sutra_filter_only
        )

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(pairs, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(pairs)} Q&A pairs to {output_file}")
        return True

    except Exception as e:
        logger.error(f"Error exporting Q&A pairs: {e}")
        return False


def analyze_popular_queries(days: int = 7, top_n: int = 10) -> Dict:
    """
    Analyze popular query patterns.

    Args:
        days: Number of days to analyze
        top_n: Number of top queries to return

    Returns:
        Dictionary with analysis statistics
    """
    pairs = get_qa_pairs(days=days)

    if not pairs:
        return {
            "total_queries": 0,
            "detailed_mode_count": 0,
            "sutra_filter_count": 0,
            "by_sutra": {},
            "by_model": {}
        }

    # Calculate statistics
    stats = {
        "total_queries": len(pairs),
        "detailed_mode_count": sum(1 for p in pairs if p.get("detailed_mode", False)),
        "sutra_filter_count": sum(1 for p in pairs if p.get("sutra_filter")),
        "by_sutra": {},
        "by_model": {}
    }

    # Group by sutra filter
    for pair in pairs:
        sutra = pair.get("sutra_filter")
        if sutra:
            if sutra not in stats["by_sutra"]:
                stats["by_sutra"][sutra] = 0
            stats["by_sutra"][sutra] += 1

    # Group by model
    for pair in pairs:
        model = pair.get("model", "unknown")
        if model not in stats["by_model"]:
            stats["by_model"][model] = 0
        stats["by_model"][model] += 1

    return stats


def get_recent_queries(limit: int = 10) -> List[Dict]:
    """
    Get most recent queries with preview.

    Args:
        limit: Maximum number of queries to return

    Returns:
        List of recent query entries with truncated preview
    """
    pairs = get_qa_pairs(days=7, limit=limit)

    # Create preview version
    previews = []
    for pair in pairs:
        previews.append({
            "timestamp": pair["timestamp"],
            "query_preview": pair["query"][:100],
            "response_preview": pair["response"][:100],
            "detailed_mode": pair["detailed_mode"],
            "sutra_filter": pair.get("sutra_filter"),
            "model": pair.get("model"),
            "tokens": pair.get("tokens", {}).get("total", 0)
        })

    return previews
