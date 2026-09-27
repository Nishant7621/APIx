import time
import logging
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from collector.example_adapter import ExamplePermittedAdapter
from scheduler.safety_guard import SafetyGuard

logger = logging.getLogger("apix.scheduler.research")

PILOT_ROUTES = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL")
]

PILOT_WINDOWS = [1, 7, 15, 30, 45]

class ResearchScheduler:
    """
    Research Mode:
    - Runs once daily at 10:00 AM (with optional second run at 6:00 PM / 18:00)
    - Staggers requests across all 6 pilot routes and 5 booking windows
    - Enforces 1 active session per domain and conservative delays
    """
    def __init__(self, include_evening_run: bool = True):
        self.scheduler = BackgroundScheduler()
        self.adapter = ExamplePermittedAdapter()
        self.include_evening_run = include_evening_run

    def execute_research_cycle(self):
        """
        Executes a complete research collection cycle:
        6 routes * 5 windows = 30 matrix combinations.
        Applies conservative domain delays and checks circuit breakers.
        """
        print("\n" + "=" * 65)
        print("    APIx RESEARCH MODE - STARTING FULL COLLECTION CYCLE")
        print("=" * 65)

        total_collected = 0
        total_attempts = 0

        for origin, dest in PILOT_ROUTES:
            for window in PILOT_WINDOWS:
                total_attempts += 1
                if SafetyGuard.is_source_blocked(self.adapter.source_name):
                    print(f"[RESEARCH] Halting cycle: source '{self.adapter.source_name}' is blocked by circuit breaker.")
                    return

                def task():
                    return self.adapter.collect(origin=origin, destination=dest, advance_window_days=window)

                result = SafetyGuard.execute_with_safety(
                    source_name=self.adapter.source_name,
                    domain="mock-feed.local",
                    collection_func=task,
                    max_retries=1,
                    inter_request_delay_seconds=0.2
                )

                if result.get("status") == "SUCCESS":
                    total_collected += result.get("records_collected", 0)
                elif result.get("status") == "BLOCKED":
                    print(f"[RESEARCH] Circuit breaker tripped during {origin}-{dest} T+{window}. Halting.")
                    return

        print("-" * 65)
        print(f"[RESEARCH] Cycle completed: {total_collected} quotes across {total_attempts} route-window cells.")
        print("=" * 65)

    def start(self, blocking: bool = True):
        """Registers the 10:00 AM and optional 6:00 PM cron jobs."""
        print("=" * 65)
        print("          APIx SCHEDULER - RESEARCH MODE INITIALIZED")
        print("=" * 65)
        print("Scheduled Run 1: Daily at 10:00 AM")
        if self.include_evening_run:
            print("Scheduled Run 2: Daily at 06:00 PM (18:00)")
        print("=" * 65)

        # 10:00 AM Cron
        self.scheduler.add_job(
            self.execute_research_cycle,
            CronTrigger(hour=10, minute=0),
            id="research_morning_job"
        )

        # 6:00 PM Cron (optional)
        if self.include_evening_run:
            self.scheduler.add_job(
                self.execute_research_cycle,
                CronTrigger(hour=18, minute=0),
                id="research_evening_job"
            )

        self.scheduler.start()

        if blocking:
            try:
                while True:
                    time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                self.stop()

    def stop(self):
        """Shuts down scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Research scheduler stopped.")
