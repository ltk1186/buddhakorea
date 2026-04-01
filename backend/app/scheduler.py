"""Simple scheduler for background tasks using asyncio."""

import asyncio
from datetime import datetime, time, timezone, timedelta
from loguru import logger
from typing import Optional, Callable, Awaitable


class SimpleScheduler:
    """Minimal task scheduler for daily tasks."""

    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self._running = False

    def schedule_daily(
        self,
        name: str,
        task: Callable[[], Awaitable[None]],
        run_time: time = time(2, 0)  # 2 AM UTC by default
    ):
        """
        Schedule a task to run daily at specified time.

        Args:
            name: Task name
            task: Async callable to run
            run_time: time object specifying when to run (default 2 AM UTC)
        """
        self.tasks[name] = {
            "task": task,
            "run_time": run_time,
            "last_run": None
        }
        logger.info(f"Scheduled task '{name}' to run daily at {run_time.strftime('%H:%M UTC')}")

    async def _run_task(self, name: str, task: Callable[[], Awaitable[None]]) -> None:
        """Run a single task with error handling."""
        try:
            logger.info(f"Running scheduled task: {name}")
            await task()
            logger.info(f"Completed scheduled task: {name}")
        except Exception as e:
            logger.error(f"Error in scheduled task '{name}': {e}")

    async def start(self):
        """Start the scheduler."""
        self._running = True
        logger.info("Scheduler started")

        while self._running:
            now = datetime.now(timezone.utc)
            current_time = now.time()

            for name, config in self.tasks.items():
                run_time = config["run_time"]
                last_run = config["last_run"]

                # Check if it's time to run and we haven't run today
                if (current_time.hour == run_time.hour and
                    current_time.minute == run_time.minute and
                    (last_run is None or last_run.date() != now.date())):

                    config["last_run"] = now
                    task = config["task"]
                    asyncio.create_task(self._run_task(name, task))

            # Check every minute
            await asyncio.sleep(60)

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        logger.info("Scheduler stopped")


# Global scheduler instance
scheduler = SimpleScheduler()
