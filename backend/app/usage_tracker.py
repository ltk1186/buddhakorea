"""
Token Usage Tracker for Buddha Korea RAG System

Tracks and logs token usage and costs for LLM API calls.
Supports Gemini, Claude, and OpenAI models.
PII is automatically masked before logging.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from .privacy import mask_pii

# Usage log file path (DEPRECATED: Cloud Logging을 통해 BigQuery로 분석 예정)
# 로컬 개발/테스트용으로만 유지
USAGE_LOG_FILE = Path("logs/usage.jsonl")

# Pricing per 1M tokens (USD)
PRICING = {
    "gemini-2.5-pro": {
        "input": 1.25,
        "output": 10.0
    },
    "gemini-2.0-flash-exp": {
        "input": 0.0,  # Free input < 128K
        "output": 0.82
    },
    "gemini-1.5-pro-002": {
        "input": 1.25,
        "output": 5.0
    },
    "gemini-1.5-flash-002": {
        "input": 0.075,
        "output": 0.30
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.0,
        "output": 15.0
    },
    "claude-3-5-sonnet-20240620": {
        "input": 3.0,
        "output": 15.0
    },
    "gpt-4o": {
        "input": 2.5,
        "output": 10.0
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60
    }
}


def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """
    Calculate cost for token usage.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name

    Returns:
        Cost in USD
    """
    # Get pricing for model (default to Gemini 2.5 Pro if unknown)
    pricing = PRICING.get(model, PRICING["gemini-2.5-pro"])

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost


def estimate_cost_from_total_tokens(
    total_tokens: Optional[int],
    model: Optional[str],
    *,
    assumed_input_share: float = 0.85,
) -> Optional[float]:
    """
    Estimate cost from a stored total-token count.

    Stored chat_messages currently keep a single `tokens_used` value rather than
    separate prompt/completion counts. For observability, we use a stable input
    share assumption so operators still get a cost trend in environments where
    file-based usage logs are unavailable.
    """
    if not total_tokens or total_tokens <= 0 or not model:
        return None

    input_tokens = int(round(total_tokens * assumed_input_share))
    output_tokens = max(int(total_tokens) - input_tokens, 0)
    return calculate_cost(input_tokens, output_tokens, model)


def log_token_usage(
    query: str,
    response: str,
    input_tokens: int,
    output_tokens: int,
    model: str,
    mode: str = "normal",
    session_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
    from_cache: bool = False,
    trace: Optional[Dict] = None
) -> None:
    """
    Log token usage to JSONL file.

    Args:
        query: User query (will be truncated)
        response: LLM response (will be truncated)
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name
        mode: Query mode (normal/detailed)
        session_id: Session ID (optional)
        latency_ms: Response latency in milliseconds (optional)
        from_cache: Whether response was from cache
        trace: Structured prompt/retrieval metadata for this query
    """
    # Calculate cost
    cost = calculate_cost(input_tokens, output_tokens, model)

    # Mask PII before logging
    masked_query = mask_pii(query[:100])  # First 100 chars, then mask
    masked_response = mask_pii(response[:100])  # First 100 chars, then mask

    # Create usage entry
    usage_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": masked_query,
        "response_preview": masked_response,
        "mode": mode,
        "model": model,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens
        },
        "cost_usd": round(cost, 6),
        "from_cache": from_cache,
        "session_id": session_id,
        "latency_ms": latency_ms,
        "trace": trace or {}
    }

    # Log the structured data using loguru (this will go to stdout as JSON)
    # Using logger.bind() to attach structured data that serialize=True will include
    logger.bind(usage=usage_entry).info("Token usage logged")


def analyze_usage_logs(days: int = 7) -> Dict:
    """
    Analyze usage logs for the specified period.

    Args:
        days: Number of days to analyze

    Returns:
        Dictionary with usage statistics
    """
    if not USAGE_LOG_FILE.exists():
        return {
            "total_queries": 0,
            "total_cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "by_mode": {},
            "by_model": {},
            "by_day": {}
        }

    # Calculate cutoff date
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Read and filter logs
    stats = {
        "total_queries": 0,
        "total_cost": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "by_mode": {},
        "by_model": {},
        "by_day": {},
        "cached_queries": 0
    }

    try:
        with open(USAGE_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())

                    # Parse timestamp
                    timestamp = datetime.fromisoformat(entry["timestamp"])

                    # Skip if outside date range
                    if timestamp < cutoff:
                        continue

                    # Update totals
                    stats["total_queries"] += 1
                    stats["total_cost"] += entry["cost_usd"]
                    tokens = entry["tokens"]
                    stats["input_tokens"] += tokens.get("input", 0)
                    stats["output_tokens"] += tokens.get("output", 0)
                    # Handle old format without 'total' field
                    stats["total_tokens"] += tokens.get("total", tokens.get("input", 0) + tokens.get("output", 0))

                    if entry.get("from_cache", False):
                        stats["cached_queries"] += 1

                    # Calculate total tokens once for reuse
                    total_tokens = tokens.get("total", tokens.get("input", 0) + tokens.get("output", 0))

                    # By mode
                    mode = entry["mode"]
                    if mode not in stats["by_mode"]:
                        stats["by_mode"][mode] = {
                            "queries": 0,
                            "cost": 0.0,
                            "tokens": 0
                        }
                    stats["by_mode"][mode]["queries"] += 1
                    stats["by_mode"][mode]["cost"] += entry["cost_usd"]
                    stats["by_mode"][mode]["tokens"] += total_tokens

                    # By model
                    model = entry["model"]
                    if model not in stats["by_model"]:
                        stats["by_model"][model] = {
                            "queries": 0,
                            "cost": 0.0,
                            "tokens": 0
                        }
                    stats["by_model"][model]["queries"] += 1
                    stats["by_model"][model]["cost"] += entry["cost_usd"]
                    stats["by_model"][model]["tokens"] += total_tokens

                    # By day
                    day = timestamp.date().isoformat()
                    if day not in stats["by_day"]:
                        stats["by_day"][day] = {
                            "queries": 0,
                            "cost": 0.0,
                            "tokens": 0
                        }
                    stats["by_day"][day]["queries"] += 1
                    stats["by_day"][day]["cost"] += entry["cost_usd"]
                    stats["by_day"][day]["tokens"] += total_tokens

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Error parsing usage log entry: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error reading usage logs: {e}")

    return stats


def _calculate_percentile(values: List[int], percentile: float) -> Optional[int]:
    """Return a rounded percentile from a list of integer values."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    if lower_index == upper_index:
        return lower_value
    weight = rank - lower_index
    return int(round(lower_value + (upper_value - lower_value) * weight))


def analyze_observability_logs(days: int = 7, slow_query_ms: int = 30000) -> Dict:
    """
    Compute reliability-focused metrics from usage logs.

    This is intentionally read-only and derived from the same structured
    usage.jsonl records already used for cost analytics.
    """
    base = {
        "window_days": days,
        "usage_log_available": USAGE_LOG_FILE.exists(),
        "total_queries": 0,
        "queries_with_latency": 0,
        "cache_hit_rate": 0.0,
        "avg_cost_per_query_usd": 0.0,
        "avg_latency_ms": None,
        "p50_latency_ms": None,
        "p95_latency_ms": None,
        "slow_query_threshold_ms": slow_query_ms,
        "slow_queries": 0,
        "by_day": {}
    }

    if not USAGE_LOG_FILE.exists():
        return base

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    latencies: List[int] = []
    cached_queries = 0
    total_cost = 0.0

    try:
        with open(USAGE_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    timestamp = datetime.fromisoformat(entry["timestamp"])
                    if timestamp < cutoff:
                        continue

                    day = timestamp.date().isoformat()
                    if day not in base["by_day"]:
                        base["by_day"][day] = {
                            "queries": 0,
                            "cost_usd": 0.0,
                            "cached_queries": 0,
                            "cache_hit_rate": 0.0,
                            "avg_latency_ms": None,
                            "p95_latency_ms": None
                        }
                    day_bucket = base["by_day"][day]

                    base["total_queries"] += 1
                    day_bucket["queries"] += 1

                    cost = float(entry.get("cost_usd", 0.0) or 0.0)
                    total_cost += cost
                    day_bucket["cost_usd"] += cost

                    if entry.get("from_cache", False):
                        cached_queries += 1
                        day_bucket["cached_queries"] += 1

                    latency_ms = entry.get("latency_ms")
                    if isinstance(latency_ms, (int, float)) and latency_ms >= 0:
                        latency_value = int(latency_ms)
                        latencies.append(latency_value)
                        base["queries_with_latency"] += 1
                        if latency_value >= slow_query_ms:
                            base["slow_queries"] += 1

                        day_bucket.setdefault("_latencies", []).append(latency_value)

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Error parsing observability usage entry: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error reading observability usage logs: {e}")
        return base

    if base["total_queries"] > 0:
        base["cache_hit_rate"] = round((cached_queries / base["total_queries"]) * 100, 2)
        base["avg_cost_per_query_usd"] = round(total_cost / base["total_queries"], 6)

    if latencies:
        base["avg_latency_ms"] = int(round(sum(latencies) / len(latencies)))
        base["p50_latency_ms"] = _calculate_percentile(latencies, 0.50)
        base["p95_latency_ms"] = _calculate_percentile(latencies, 0.95)

    for day_entry in base["by_day"].values():
        if day_entry["queries"] > 0:
            day_entry["cache_hit_rate"] = round((day_entry["cached_queries"] / day_entry["queries"]) * 100, 2)
        day_latencies = day_entry.pop("_latencies", [])
        if day_latencies:
            day_entry["avg_latency_ms"] = int(round(sum(day_latencies) / len(day_latencies)))
            day_entry["p95_latency_ms"] = _calculate_percentile(day_latencies, 0.95)
        day_entry["cost_usd"] = round(day_entry["cost_usd"], 6)

    return base


def analyze_observability_messages(
    message_rows: List[tuple],
    *,
    days: int = 7,
    slow_query_ms: int = 30000,
) -> Dict:
    """
    Compute reliability metrics from persisted assistant chat messages.

    Expected row shape:
    - created_at
    - latency_ms
    - tokens_used
    - model_used
    - response_mode
    """
    base = {
        "window_days": days,
        "metrics_source": "database",
        "latency_metrics_available": False,
        "cache_metrics_available": False,
        "cost_metrics_available": False,
        "cost_metrics_estimated": False,
        "total_queries": 0,
        "queries_with_latency": 0,
        "queries_with_cost": 0,
        "cache_queries_sample": 0,
        "cache_hit_rate": None,
        "avg_cost_per_query_usd": None,
        "avg_latency_ms": None,
        "p50_latency_ms": None,
        "p95_latency_ms": None,
        "slow_query_threshold_ms": slow_query_ms,
        "slow_queries": 0,
        "by_day": {},
    }

    latencies: List[int] = []
    total_cost = 0.0

    cached_queries = 0

    for created_at, latency_ms, tokens_used, model_used, response_mode in message_rows:
        if not created_at:
            continue
            
        response_mode = response_mode or "normal"

        day = created_at.date().isoformat()
        if day not in base["by_day"]:
            base["by_day"][day] = {
                "queries": 0,
                "cost_usd": None,
                "cached_queries": None,
                "cache_hit_rate": None,
                "avg_latency_ms": None,
                "p95_latency_ms": None,
            }
        day_bucket = base["by_day"][day]
        base["total_queries"] += 1
        day_bucket["queries"] += 1

        if response_mode == "cached":
            cached_queries += 1
            day_bucket["_cached_queries"] = day_bucket.get("_cached_queries", 0) + 1

        estimated_cost = estimate_cost_from_total_tokens(tokens_used, model_used)
        if estimated_cost is not None:
            total_cost += estimated_cost
            base["queries_with_cost"] += 1
            day_bucket["_cost_usd"] = day_bucket.get("_cost_usd", 0.0) + estimated_cost
            day_bucket["_queries_with_cost"] = day_bucket.get("_queries_with_cost", 0) + 1

        if isinstance(latency_ms, (int, float)) and latency_ms >= 0:
            latency_value = int(latency_ms)
            latencies.append(latency_value)
            base["queries_with_latency"] += 1
            if latency_value >= slow_query_ms:
                base["slow_queries"] += 1
            day_bucket.setdefault("_latencies", []).append(latency_value)

    if base["queries_with_latency"] > 0:
        base["latency_metrics_available"] = True
        base["avg_latency_ms"] = int(round(sum(latencies) / len(latencies)))
        base["p50_latency_ms"] = _calculate_percentile(latencies, 0.50)
        base["p95_latency_ms"] = _calculate_percentile(latencies, 0.95)

    if base["queries_with_cost"] > 0:
        base["cost_metrics_available"] = True
        base["cost_metrics_estimated"] = True
        base["avg_cost_per_query_usd"] = round(total_cost / base["queries_with_cost"], 6)

    if base["total_queries"] > 0:
        base["cache_metrics_available"] = True
        base["cache_queries_sample"] = cached_queries
        base["cache_hit_rate"] = round((cached_queries / base["total_queries"]) * 100, 2)

    for day_bucket in base["by_day"].values():
        day_latencies = day_bucket.pop("_latencies", [])
        if day_latencies:
            day_bucket["avg_latency_ms"] = int(round(sum(day_latencies) / len(day_latencies)))
            day_bucket["p95_latency_ms"] = _calculate_percentile(day_latencies, 0.95)

        cached_for_day = day_bucket.pop("_cached_queries", 0)
        day_bucket["cached_queries"] = cached_for_day
        if day_bucket["queries"] > 0:
            day_bucket["cache_hit_rate"] = round((cached_for_day / day_bucket["queries"]) * 100, 2)

        queries_with_cost = day_bucket.pop("_queries_with_cost", 0)
        if queries_with_cost > 0:
            day_bucket["cost_usd"] = round(day_bucket.pop("_cost_usd", 0.0), 6)
        else:
            day_bucket.pop("_cost_usd", None)

    return base


def get_recent_queries(limit: int = 10) -> List[Dict]:
    """
    Get recent queries from usage logs.

    Args:
        limit: Maximum number of queries to return

    Returns:
        List of recent query entries
    """
    if not USAGE_LOG_FILE.exists():
        return []

    queries = []

    try:
        with open(USAGE_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Get last N lines
        for line in reversed(lines[-limit:]):
            try:
                entry = json.loads(line.strip())
                queries.append(entry)
            except json.JSONDecodeError:
                continue

    except Exception as e:
        logger.error(f"Error reading recent queries: {e}")

    return queries


def export_usage_csv(output_file: str = "logs/usage_export.csv", days: int = 30) -> bool:
    """
    Export usage logs to CSV file.

    Args:
        output_file: Output CSV file path
        days: Number of days to export

    Returns:
        True if successful, False otherwise
    """
    if not USAGE_LOG_FILE.exists():
        logger.warning("No usage logs found")
        return False

    import csv

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        with open(USAGE_LOG_FILE, "r", encoding="utf-8") as f_in:
            with open(output_file, "w", newline="", encoding="utf-8") as f_out:
                writer = csv.writer(f_out)

                # Write header
                writer.writerow([
                    "Timestamp",
                    "Query",
                    "Mode",
                    "Model",
                    "Input Tokens",
                    "Output Tokens",
                    "Total Tokens",
                    "Cost (USD)",
                    "From Cache",
                    "Latency (ms)"
                ])

                # Write rows
                for line in f_in:
                    try:
                        entry = json.loads(line.strip())
                        timestamp = datetime.fromisoformat(entry["timestamp"])

                        if timestamp < cutoff:
                            continue

                        writer.writerow([
                            entry["timestamp"],
                            entry["query"],
                            entry["mode"],
                            entry["model"],
                            entry["tokens"]["input"],
                            entry["tokens"]["output"],
                            entry["tokens"]["total"],
                            entry["cost_usd"],
                            entry.get("from_cache", False),
                            entry.get("latency_ms", "")
                        ])
                    except json.JSONDecodeError:
                        continue

        logger.info(f"Usage logs exported to {output_file}")
        return True

    except Exception as e:
        logger.error(f"Error exporting usage logs: {e}")
        return False
