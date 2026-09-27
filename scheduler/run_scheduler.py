import sys
import argparse
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from scheduler.demo_mode import DemoScheduler
from scheduler.research_mode import ResearchScheduler

def main():
    parser = argparse.ArgumentParser(description="APIx Flight Fare Collection Scheduler")
    parser.add_argument(
        "--mode",
        choices=["demo", "research"],
        default="demo",
        help="Scheduling mode: 'demo' (3 runs on DEL-BOM T+7) or 'research' (Daily 10:00 AM / 6:00 PM)"
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=120,
        help="Interval in seconds for demo mode (default: 120s; set lower like 2s for quick tests)"
    )
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="In research mode, trigger one cycle immediately before listening for cron triggers"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly override safety lock if automated scheduler is needed"
    )
    args = parser.parse_args()

    import os
    from dotenv import load_dotenv
    load_dotenv(root_dir / ".env")

    automated_enabled = os.getenv("AUTOMATED_SCRAPING_ENABLED", "false").lower() in ("true", "1", "yes")

    if not automated_enabled and not args.force:
        print("\n" + "=" * 65)
        print(" [SAFETY LOCK] AUTOMATED SCRAPING IS DISABLED")
        print("=" * 65)
        print("Your system is configured for STRICTLY MANUAL collection.")
        print("Automated background cron/interval collection will NOT run.")
        print("\nTo trigger a collection manually on-demand, run:")
        print("  python -m collector.run_single_collection")
        print("=" * 65 + "\n")
        sys.exit(0)

    if args.mode == "demo":
        scheduler = DemoScheduler(interval_seconds=args.interval_seconds, max_runs=3)
        scheduler.start(blocking=True)
    elif args.mode == "research":
        scheduler = ResearchScheduler(include_evening_run=True)
        if args.run_now:
            scheduler.execute_research_cycle()
        scheduler.start(blocking=True)

if __name__ == "__main__":
    main()
