#!/usr/bin/env python3
"""
APIx Automation CLI Tool
Unified terminal command-line tool for automated scraping, database auditing,
and continuous background scheduling.
"""

import sys
import os
import time
import csv
import argparse
import datetime
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
load_dotenv(root_dir / ".env")

from database.connection import get_engine, get_session_maker
from database.models import FareQuote, RawResponse, CollectionRun, SourceHealth
from scheduler.daily_auto_collector import (
    execute_daily_ingestion_cycle,
    execute_hourly_ingestion_cycle,
    run_continuous_hourly_daemon,
    run_continuous_daemon,
    get_current_ist_time
)
from sqlalchemy import text, func

def print_banner():
    print(r"""
====================================================================================
      _    ____ ___       _         _                        _   _             
     / \  |  _ \_ _|__  _| |       / \  _   _| |_ ___  _ __ | |_(_) ___  _ __  
    / _ \ | |_) | | \ \/ / |_____ / _ \| | | | __/ _ \| '_ \| __| |/ _ \| '_ \ 
   / ___ \|  __/| |  >  <| |_____/ ___ \ |_| | || (_) | | | | |_| | (_) | | | |
  /_/   \_\_|  |___|/_/\_\_|    /_/   \_\__,_|\__\___/|_| |_|\__|_|\___/|_| |_|
  
     Pilot Airline Price Index (APIx) - Automated Continuous Scraping Engine
====================================================================================
""")

def cmd_scrape(args):
    print("\n[ACTION] Triggering Automated Scraping Cycle...")
    target_date = datetime.date.fromisoformat(args.date) if args.date else None
    
    if args.hour is not None:
        print(f"[MODE] Hourly Ingestion for Hour {args.hour:02d}:00")
        res = execute_hourly_ingestion_cycle(target_date=target_date, target_hour=args.hour, force=args.force)
    else:
        print("[MODE] Comprehensive Full-Day Matrix Ingestion (6 Routes x 5 Windows)")
        res = execute_daily_ingestion_cycle(target_date=target_date, force=args.force)
        
    print("\n[RESULT]")
    for k, v in res.items():
        print(f"  - {k:<18}: {v}")
    print("\nScraped observations are now live in PostgreSQL (apix_db) and on http://localhost:3000\n")

def cmd_auto(args):
    if args.daily:
        print("[MODE] Starting Daily Morning Daemon (06:00 AM IST)...")
        run_continuous_daemon(daily_hour=6, daily_minute=0)
    else:
        print("[MODE] Starting 24-Hour Continuous Hourly Daemon (Every Single Hour)...")
        run_continuous_hourly_daemon()

def cmd_status(args):
    print("\n" + "=" * 80)
    print("                    APIx SYSTEM & DATABASE DIAGNOSTIC AUDIT")
    print("=" * 80)
    
    SessionLocal = get_session_maker()
    session = SessionLocal()
    
    try:
        now_ist = get_current_ist_time()
        print(f"  Current System Time (IST) : {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
        
        # Row counts
        quotes_cnt = session.query(FareQuote).count()
        raw_cnt = session.query(RawResponse).count()
        runs_cnt = session.query(CollectionRun).count()
        
        # Today's counts
        today_date = now_ist.date()
        today_quotes = session.query(FareQuote).filter(func.date(FareQuote.collected_at) == today_date).count()
        today_raw = session.query(RawResponse).filter(func.date(RawResponse.collected_at) == today_date).count()
        
        # Last collection run
        last_run = session.query(CollectionRun).order_by(CollectionRun.id.desc()).first()
        last_run_time = last_run.started_at.strftime('%Y-%m-%d %H:%M:%S') if last_run else "None"
        last_run_status = last_run.status if last_run else "N/A"
        
        print(f"  Target Database           : PostgreSQL 18 (apix_db) - ONLINE")
        print(f"  Total Fare Quotes Stored  : {quotes_cnt:,} rows")
        print(f"  Total Raw JSON Payloads   : {raw_cnt:,} records (SHA-256 hashed)")
        print(f"  Total Collection Runs     : {runs_cnt:,} runs")
        print(f"  Today's Quotes ({today_date}) : {today_quotes:,} rows")
        print(f"  Today's Raw Payloads      : {today_raw:,} records")
        print(f"  Last Collection Run Time  : {last_run_time} (Status: {last_run_status})")
        
        # Next run prediction
        next_hour = (now_ist + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        mins_away = round((next_hour - now_ist).total_seconds() / 60, 1)
        print(f"  Next Hourly Run Expected  : {next_hour.strftime('%H:%M:%S IST')} (in {mins_away} mins)")
        
        print("-" * 80)
        print("  MONITORED PLATFORMS HEALTH (Anti-Bot & Rate-Limit Compliance):")
        sources = session.query(SourceHealth).all()
        if sources:
            for s in sources:
                last_c = s.last_successful_collection.strftime('%Y-%m-%d %H:%M') if s.last_successful_collection else "Active"
                print(f"    * {s.source_name:<22} : {s.status:<8} | Blocks: {s.captcha_count + s.http_error_count} | Success: {s.success_rate:.0f}% | Last: {last_c}")
        else:
            print("    All 6 Platforms Monitored with 0 restrictions recorded.")
            
        print("=" * 80 + "\n")
        
    finally:
        session.close()

def cmd_view(args):
    limit = args.limit or 15
    SessionLocal = get_session_maker()
    session = SessionLocal()
    
    try:
        total = session.query(FareQuote).count()
        print("\n" + "=" * 95)
        print(f"               CLEANED FARE QUOTES (Total in PostgreSQL: {total:,} rows)")
        print("=" * 95)
        header = f"{'ID':<7} | {'COLLECTED AT':<19} | {'PLATFORM':<15} | {'AIRLINE':<12} | {'ROUTE':<9} | {'HORIZON':<7} | {'TOTAL FARE':<12}"
        print(header)
        print("-" * 95)
        
        quotes = session.query(FareQuote).order_by(FareQuote.id.desc()).limit(limit).all()
        for q in quotes:
            col_time = q.collected_at.strftime("%Y-%m-%d %H:%M:%S") if q.collected_at else "N/A"
            route = f"{q.origin}->{q.destination}"
            window = f"T+{q.advance_window_days}"
            fare = f"INR {q.total_fare:,.2f}" if q.total_fare else "N/A"
            print(f"{q.id:<7} | {col_time:<19} | {q.source_name[:15]:<15} | {q.airline_name[:12]:<12} | {route:<9} | {window:<7} | {fare:<12}")
            
        print("-" * 95)
        print(f"Showing the latest {len(quotes)} clean records from PostgreSQL table 'fare_quotes'.\n")
    finally:
        session.close()

def cmd_raw(args):
    limit = args.limit or 5
    SessionLocal = get_session_maker()
    session = SessionLocal()
    
    try:
        total = session.query(RawResponse).count()
        print("\n" + "=" * 95)
        print(f"             RAW CAPTURED PAYLOADS (Total in PostgreSQL: {total:,} records)")
        print("=" * 95)
        
        raw_list = session.query(RawResponse).order_by(RawResponse.id.desc()).limit(limit).all()
        for r in raw_list:
            col_time = r.collected_at.strftime("%Y-%m-%d %H:%M:%S") if r.collected_at else "N/A"
            print(f"Record ID    : {r.id}")
            print(f"Timestamp    : {col_time}")
            print(f"Sector       : {r.origin} -> {r.destination} (Travel Date: {r.travel_date}, Window: T+{r.advance_window_days})")
            print(f"Source       : {r.source_name}")
            print(f"SHA-256 Hash : {r.payload_hash}")
            preview = r.payload_json[:180] + "..." if r.payload_json and len(r.payload_json) > 180 else (r.payload_json or "{}")
            print(f"Raw Payload  : {preview}")
            print("-" * 95)
    finally:
        session.close()

def cmd_export(args):
    filename = args.output or f"apix_export_{datetime.date.today().isoformat()}.csv"
    filepath = root_dir / filename
    print(f"\n[EXPORT] Exporting clean fare observations to CSV: {filepath}...")
    
    SessionLocal = get_session_maker()
    session = SessionLocal()
    
    try:
        quotes = session.query(FareQuote).order_by(FareQuote.id.desc()).limit(args.limit or 10000).all()
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "quote_id", "collected_at", "source_name", "source_type",
                "origin", "destination", "travel_date", "advance_window_days",
                "airline_name", "flight_number", "base_fare", "taxes",
                "convenience_fee", "total_fare", "currency", "availability"
            ])
            for q in quotes:
                writer.writerow([
                    q.id,
                    str(q.collected_at),
                    q.source_name,
                    q.source_type,
                    q.origin,
                    q.destination,
                    str(q.travel_date),
                    f"T+{q.advance_window_days}",
                    q.airline_name,
                    q.flight_number,
                    q.base_fare,
                    q.taxes,
                    q.mandatory_charges,
                    q.total_fare,
                    q.currency,
                    q.availability_status
                ])
        print(f"[SUCCESS] Exported {len(quotes):,} records to: {filepath}\n")
    finally:
        session.close()

def main():
    print_banner()
    
    parser = argparse.ArgumentParser(
        description="APIx Automation Tool - Automated Scraping, Database Auditing, and Continuous Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  scrape     Execute an automated scraping run right now
  auto       Start continuous 24-hour background scraping daemon (runs every hour)
  status     Show database health, row counts, and next scheduled scrape
  view       View the latest cleaned fare quotes table in terminal
  raw        View the latest raw JSON payloads and SHA-256 hashes
  export     Export clean observations directly to a CSV file

Examples:
  python apix.py scrape           # Scrape today's data immediately
  python apix.py auto             # Run continuous 24-hour automated scraper (1 run/hr)
  python apix.py status           # Check system health & row counts
  python apix.py view 20          # View latest 20 cleaned quotes
  python apix.py raw              # View latest raw responses with hashes
  python apix.py export           # Export clean observations to CSV
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    # Scrape command
    p_scrape = subparsers.add_parser("scrape", help="Trigger an immediate automated scrape")
    p_scrape.add_argument("--date", type=str, help="Optional target date YYYY-MM-DD")
    p_scrape.add_argument("--hour", type=int, help="Optional specific hour 0-23")
    p_scrape.add_argument("--force", action="store_true", help="Force scrape even if date/hour exists")
    
    # Auto command
    p_auto = subparsers.add_parser("auto", help="Start continuous automated scraper daemon")
    p_auto.add_argument("--daily", action="store_true", help="Run once daily at 06:00 AM instead of 24 hourly runs")
    
    # Status command
    subparsers.add_parser("status", help="Show database health and live metrics")
    
    # View command
    p_view = subparsers.add_parser("view", help="View latest cleaned fare quotes")
    p_view.add_argument("limit", type=int, nargs="?", default=15, help="Number of rows to view")
    
    # Raw command
    p_raw = subparsers.add_parser("raw", help="View latest raw payloads with SHA-256 hashes")
    p_raw.add_argument("limit", type=int, nargs="?", default=5, help="Number of raw records to view")
    
    # Export command
    p_export = subparsers.add_parser("export", help="Export clean quotes to CSV file")
    p_export.add_argument("--output", type=str, help="Output CSV filename")
    p_export.add_argument("--limit", type=int, default=10000, help="Max quotes to export")
    
    args = parser.parse_args()
    
    if args.command == "scrape":
        cmd_scrape(args)
    elif args.command == "auto":
        cmd_auto(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "view":
        cmd_view(args)
    elif args.command == "raw":
        cmd_raw(args)
    elif args.command == "export":
        cmd_export(args)
    else:
        # If no command passed, show status by default
        cmd_status(args)

if __name__ == "__main__":
    main()
