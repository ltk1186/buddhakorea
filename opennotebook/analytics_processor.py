"""
Analytics Processor for Buddha Korea RAG System

Processes rotated JSONL log files incrementally and updates Redis analytics.
Uses file locking to prevent concurrent runs and byte-offset checkpoints for resumability.
"""

import json
import fcntl
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import redis

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# File paths
QA_LOG_FILE = Path("logs/qa_pairs.jsonl")
USAGE_LOG_FILE = Path("logs/usage.jsonl")
CHECKPOINT_FILE = Path("logs/.analytics_checkpoint.json")
LOCKFILE = Path("logs/.analytics_processor.lock")

# Redis connection (will be injected for easier testing)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Lua script for atomic Redis analytics updates
LUA_UPDATE_ANALYTICS = """
local day = ARGV[1]
local mode = ARGV[2]
local model = ARGV[3]
local sutra = ARGV[4]
local queries = tonumber(ARGV[5])
local cost = tonumber(ARGV[6])
local tokens = tonumber(ARGV[7])
local input_tokens = tonumber(ARGV[8])
local output_tokens = tonumber(ARGV[9])
local cached = tonumber(ARGV[10])

-- Update daily totals
redis.call('HINCRBY', 'analytics:daily:' .. day, 'queries', queries)
redis.call('HINCRBYFLOAT', 'analytics:daily:' .. day, 'cost', cost)
redis.call('HINCRBY', 'analytics:daily:' .. day, 'tokens', tokens)
redis.call('HINCRBY', 'analytics:daily:' .. day, 'input_tokens', input_tokens)
redis.call('HINCRBY', 'analytics:daily:' .. day, 'output_tokens', output_tokens)
redis.call('HINCRBY', 'analytics:daily:' .. day, 'cached_queries', cached)

-- Update by mode
if mode ~= "" then
    redis.call('HINCRBY', 'analytics:mode:' .. mode, 'queries', queries)
    redis.call('HINCRBYFLOAT', 'analytics:mode:' .. mode, 'cost', cost)
    redis.call('HINCRBY', 'analytics:mode:' .. mode, 'tokens', tokens)
end

-- Update by model
if model ~= "" then
    redis.call('HINCRBY', 'analytics:model:' .. model, 'queries', queries)
    redis.call('HINCRBYFLOAT', 'analytics:model:' .. model, 'cost', cost)
    redis.call('HINCRBY', 'analytics:model:' .. model, 'tokens', tokens)
end

-- Update by sutra
if sutra ~= "" then
    redis.call('HINCRBY', 'analytics:sutra:' .. sutra, 'queries', queries)
end

return 1
"""


class AnalyticsProcessor:
    """Incremental log processor with Redis analytics."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize analytics processor.

        Args:
            redis_client: Redis client (for testing). If None, creates new client.
        """
        self.redis = redis_client or redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )

        # Register Lua script
        self.update_analytics_script = self.redis.register_script(LUA_UPDATE_ANALYTICS)

    def acquire_lock(self, lockfile: Path, timeout: int = 300) -> Optional[int]:
        """
        Acquire exclusive file lock with timeout.

        Args:
            lockfile: Path to lock file
            timeout: Timeout in seconds

        Returns:
            File descriptor if acquired, None otherwise
        """
        lockfile.parent.mkdir(exist_ok=True)

        try:
            fd = os.open(lockfile, os.O_CREAT | os.O_WRONLY | os.O_TRUNC)

            # Try non-blocking lock
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Write PID to lockfile
            os.write(fd, f"{os.getpid()}\n".encode())

            logger.info(f"Acquired lock: {lockfile}")
            return fd

        except BlockingIOError:
            logger.warning(f"Another analytics processor is running (lockfile: {lockfile})")
            return None
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return None

    def release_lock(self, fd: int, lockfile: Path):
        """Release file lock."""
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            lockfile.unlink(missing_ok=True)
            logger.info(f"Released lock: {lockfile}")
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")

    def load_checkpoint(self) -> Dict[str, int]:
        """
        Load processing checkpoints from file.

        Returns:
            Dictionary mapping log file paths to last processed byte offset
        """
        if not CHECKPOINT_FILE.exists():
            return {}

        try:
            with open(CHECKPOINT_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return {}

    def save_checkpoint(self, checkpoints: Dict[str, int]):
        """
        Save processing checkpoints to file.

        Args:
            checkpoints: Dictionary mapping log file paths to byte offsets
        """
        CHECKPOINT_FILE.parent.mkdir(exist_ok=True)

        try:
            # Atomic write via temp file
            temp_file = CHECKPOINT_FILE.with_suffix('.tmp')
            with open(temp_file, "w") as f:
                json.dump(checkpoints, f, indent=2)
            temp_file.rename(CHECKPOINT_FILE)

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def process_usage_log(
        self,
        log_file: Path,
        start_offset: int = 0
    ) -> Tuple[int, Dict]:
        """
        Process usage log incrementally from byte offset.

        Args:
            log_file: Path to usage log file
            start_offset: Byte offset to start reading from

        Returns:
            Tuple of (new_offset, stats_dict)
        """
        if not log_file.exists():
            logger.warning(f"Usage log not found: {log_file}")
            return start_offset, {}

        stats = {
            "lines_processed": 0,
            "updates_sent": 0,
            "errors": 0
        }

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                # Seek to last checkpoint
                f.seek(start_offset)

                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        # Extract fields
                        timestamp = datetime.fromisoformat(entry["timestamp"])
                        day = timestamp.date().isoformat()
                        mode = entry.get("mode", "normal")
                        model = entry.get("model", "unknown")
                        cost = entry.get("cost_usd", 0.0)
                        tokens = entry.get("tokens", {})
                        input_tokens = tokens.get("input", 0)
                        output_tokens = tokens.get("output", 0)
                        from_cache = 1 if entry.get("from_cache", False) else 0

                        # Update Redis atomically via Lua
                        self.update_analytics_script(
                            keys=[],
                            args=[
                                day, mode, model, "",  # Empty sutra for usage logs
                                1,  # queries
                                cost,
                                input_tokens + output_tokens,  # total tokens
                                input_tokens,
                                output_tokens,
                                from_cache
                            ]
                        )

                        stats["lines_processed"] += 1
                        stats["updates_sent"] += 1

                    except json.JSONDecodeError:
                        stats["errors"] += 1
                        continue
                    except Exception as e:
                        logger.error(f"Error processing usage log entry: {e}")
                        stats["errors"] += 1
                        continue

                # Get final offset
                new_offset = f.tell()

        except Exception as e:
            logger.error(f"Failed to process usage log: {e}")
            return start_offset, stats

        return new_offset, stats

    def process_qa_log(
        self,
        log_file: Path,
        start_offset: int = 0
    ) -> Tuple[int, Dict]:
        """
        Process Q&A log incrementally from byte offset.

        Args:
            log_file: Path to Q&A log file
            start_offset: Byte offset to start reading from

        Returns:
            Tuple of (new_offset, stats_dict)
        """
        if not log_file.exists():
            logger.warning(f"Q&A log not found: {log_file}")
            return start_offset, {}

        stats = {
            "lines_processed": 0,
            "updates_sent": 0,
            "errors": 0
        }

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                # Seek to last checkpoint
                f.seek(start_offset)

                for line in f:
                    try:
                        entry = json.loads(line.strip())

                        # Extract fields
                        timestamp = datetime.fromisoformat(entry["timestamp"])
                        day = timestamp.date().isoformat()
                        sutra = entry.get("sutra_filter", "")
                        model = entry.get("model", "unknown")
                        mode = "detailed" if entry.get("detailed_mode", False) else "normal"
                        tokens = entry.get("tokens", {})
                        input_tokens = tokens.get("input", 0)
                        output_tokens = tokens.get("output", 0)
                        from_cache = 1 if entry.get("from_cache", False) else 0

                        # Calculate cost (approximate from tokens)
                        # This is rough - ideally should track cost in qa_logger
                        cost = 0.0  # Would need pricing data here

                        # Update Redis atomically via Lua
                        self.update_analytics_script(
                            keys=[],
                            args=[
                                day, mode, model, sutra,
                                1,  # queries
                                cost,
                                input_tokens + output_tokens,
                                input_tokens,
                                output_tokens,
                                from_cache
                            ]
                        )

                        stats["lines_processed"] += 1
                        stats["updates_sent"] += 1

                    except json.JSONDecodeError:
                        stats["errors"] += 1
                        continue
                    except Exception as e:
                        logger.error(f"Error processing Q&A log entry: {e}")
                        stats["errors"] += 1
                        continue

                # Get final offset
                new_offset = f.tell()

        except Exception as e:
            logger.error(f"Failed to process Q&A log: {e}")
            return start_offset, stats

        return new_offset, stats

    def process_all_logs(self) -> Dict:
        """
        Process all log files incrementally.

        Returns:
            Summary statistics
        """
        # Load checkpoints
        checkpoints = self.load_checkpoint()

        summary = {
            "start_time": datetime.now().isoformat(),
            "usage_log": {},
            "qa_log": {},
            "total_lines": 0,
            "total_updates": 0,
            "total_errors": 0
        }

        # Process usage log
        usage_offset = checkpoints.get(str(USAGE_LOG_FILE), 0)
        new_usage_offset, usage_stats = self.process_usage_log(
            USAGE_LOG_FILE,
            usage_offset
        )
        checkpoints[str(USAGE_LOG_FILE)] = new_usage_offset
        summary["usage_log"] = usage_stats
        summary["total_lines"] += usage_stats.get("lines_processed", 0)
        summary["total_updates"] += usage_stats.get("updates_sent", 0)
        summary["total_errors"] += usage_stats.get("errors", 0)

        # Process Q&A log
        qa_offset = checkpoints.get(str(QA_LOG_FILE), 0)
        new_qa_offset, qa_stats = self.process_qa_log(
            QA_LOG_FILE,
            qa_offset
        )
        checkpoints[str(QA_LOG_FILE)] = new_qa_offset
        summary["qa_log"] = qa_stats
        summary["total_lines"] += qa_stats.get("lines_processed", 0)
        summary["total_updates"] += qa_stats.get("updates_sent", 0)
        summary["total_errors"] += qa_stats.get("errors", 0)

        # Save updated checkpoints
        self.save_checkpoint(checkpoints)

        summary["end_time"] = datetime.now().isoformat()

        return summary

    def get_analytics(self, days: int = 7) -> Dict:
        """
        Retrieve analytics from Redis.

        Args:
            days: Number of days to retrieve

        Returns:
            Analytics dictionary
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)

        analytics = {
            "daily": {},
            "by_mode": {},
            "by_model": {},
            "by_sutra": {},
            "totals": {
                "queries": 0,
                "cost": 0.0,
                "tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_queries": 0
            }
        }

        # Get daily analytics
        current_date = start_date
        while current_date <= end_date:
            day_key = current_date.isoformat()
            redis_key = f"analytics:daily:{day_key}"

            daily_data = self.redis.hgetall(redis_key)
            if daily_data:
                analytics["daily"][day_key] = {
                    "queries": int(daily_data.get("queries", 0)),
                    "cost": float(daily_data.get("cost", 0.0)),
                    "tokens": int(daily_data.get("tokens", 0)),
                    "input_tokens": int(daily_data.get("input_tokens", 0)),
                    "output_tokens": int(daily_data.get("output_tokens", 0)),
                    "cached_queries": int(daily_data.get("cached_queries", 0))
                }

                # Accumulate totals
                analytics["totals"]["queries"] += analytics["daily"][day_key]["queries"]
                analytics["totals"]["cost"] += analytics["daily"][day_key]["cost"]
                analytics["totals"]["tokens"] += analytics["daily"][day_key]["tokens"]
                analytics["totals"]["input_tokens"] += analytics["daily"][day_key]["input_tokens"]
                analytics["totals"]["output_tokens"] += analytics["daily"][day_key]["output_tokens"]
                analytics["totals"]["cached_queries"] += analytics["daily"][day_key]["cached_queries"]

            current_date += timedelta(days=1)

        # Get mode breakdown
        for mode_key in self.redis.scan_iter("analytics:mode:*"):
            mode = mode_key.split(":")[-1]
            mode_data = self.redis.hgetall(mode_key)
            if mode_data:
                analytics["by_mode"][mode] = {
                    "queries": int(mode_data.get("queries", 0)),
                    "cost": float(mode_data.get("cost", 0.0)),
                    "tokens": int(mode_data.get("tokens", 0))
                }

        # Get model breakdown
        for model_key in self.redis.scan_iter("analytics:model:*"):
            model = model_key.split(":")[-1]
            model_data = self.redis.hgetall(model_key)
            if model_data:
                analytics["by_model"][model] = {
                    "queries": int(model_data.get("queries", 0)),
                    "cost": float(model_data.get("cost", 0.0)),
                    "tokens": int(model_data.get("tokens", 0))
                }

        # Get sutra breakdown
        for sutra_key in self.redis.scan_iter("analytics:sutra:*"):
            sutra = sutra_key.split(":")[-1]
            if sutra:  # Skip empty sutra keys
                sutra_data = self.redis.hgetall(sutra_key)
                if sutra_data:
                    analytics["by_sutra"][sutra] = {
                        "queries": int(sutra_data.get("queries", 0))
                    }

        return analytics


def main():
    """Main entry point for cron job."""
    processor = AnalyticsProcessor()

    # Acquire lock
    fd = processor.acquire_lock(LOCKFILE)
    if fd is None:
        logger.error("Could not acquire lock - another instance running?")
        sys.exit(1)

    try:
        # Process logs
        logger.info("Starting analytics processing...")
        summary = processor.process_all_logs()

        logger.info(
            f"Analytics processing complete | "
            f"Lines: {summary['total_lines']} | "
            f"Updates: {summary['total_updates']} | "
            f"Errors: {summary['total_errors']}"
        )

        # Print summary
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    finally:
        # Release lock
        processor.release_lock(fd, LOCKFILE)


if __name__ == "__main__":
    main()
