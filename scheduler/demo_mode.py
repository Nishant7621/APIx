import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from collector.example_adapter import ExamplePermittedAdapter
from scheduler.safety_guard import SafetyGuard

logger = logging.getLogger("apix.scheduler.demo")

class DemoScheduler:
    """
    Demo Mode:
    - 1 approved source (PERMITTED_EXAMPLE_FEED)
    - 1 route (DEL-BOM)
    - 1 booking window (T+7)
    - Interval: every 2 minutes (120s, or custom for tests)
    - Maximum runs: Exactly 3 runs, then auto-shutdown
    """
    def __init__(self, interval_seconds: int = 120, max_runs: int = 3):
        self.interval_seconds = interval_seconds
        self.max_runs = max_runs
        self.current_runs = 0
        self.scheduler = BackgroundScheduler()
        self.adapter = ExamplePermittedAdapter()
        self.is_finished = False

    def _execute_demo_run(self):
        """Callback for single demo cycle."""
        self.current_runs += 1
        print(f"\n[DEMO SCHEDULER] --- Starting Demo Run {self.current_runs} of {self.max_runs} ---")

        def task():
            return self.adapter.collect(origin="DEL", destination="BOM", advance_window_days=7)

        result = SafetyGuard.execute_with_safety(
            source_name=self.adapter.source_name,
            domain="mock-feed.local",
            collection_func=task,
            max_retries=1,
            inter_request_delay_seconds=0.1
        )

        print(f"[DEMO SCHEDULER] Run {self.current_runs} Status: {result.get('status')}")
        print(f"[DEMO SCHEDULER] Quotes Collected: {result.get('records_collected', 0)}")

        if self.current_runs >= self.max_runs:
            print(f"[DEMO SCHEDULER] Reached maximum allowed runs ({self.max_runs}). Automatically stopping scheduler.")
            self.stop()
            self.is_finished = True

    def start(self, blocking: bool = True):
        """Starts the scheduled demo job."""
        print("=" * 65)
        print("           APIx SCHEDULER - SAFE DEMO MODE INITIALIZED")
        print("=" * 65)
        print(f"Target Source    : {self.adapter.source_name}")
        print(f"Target Route     : DEL -> BOM")
        print(f"Advance Window   : T+7")
        print(f"Schedule Interval: Every {self.interval_seconds} seconds")
        print(f"Maximum Runs     : {self.max_runs}")
        print("=" * 65)

        # Trigger immediately for the first run, then on interval
        self.scheduler.add_job(
            self._execute_demo_run,
            "interval",
            seconds=self.interval_seconds,
            id="demo_collection_job"
        )
        self.scheduler.start()

        # Run first execution immediately
        self._execute_demo_run()

        if blocking:
            try:
                while not self.is_finished:
                    time.sleep(0.5)
            except (KeyboardInterrupt, SystemExit):
                print("\n[INFO] Demo scheduler interrupted by user.")
                self.stop()

    def stop(self):
        """Gracefully shuts down the APScheduler instance."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Demo scheduler stopped.")
