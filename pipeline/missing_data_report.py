import logging
from typing import Dict, Any, List
from collections import defaultdict
from sqlalchemy import text
from sqlalchemy.orm import Session
from database.models import FareQuote

logger = logging.getLogger("apix.pipeline.missing_data")

PILOT_ROUTES = ["DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "BLR-HYD", "MAA-DEL"]
PILOT_WINDOWS = [1, 7, 15, 30, 45]

def generate_missing_data_report(session: Session, min_expected_per_cell: int = 4) -> Dict[str, Any]:
    """
    Computes data completeness and missing observation audits:
    - By Route (DEL-BOM, DEL-BLR, etc.)
    - By Booking Window (T+1, T+7, T+15, T+30, T+45)
    - By Source (DEMO_REPLAY_FEED, AIRLINE_PORTAL, etc.)
    """
    # 1. Route Breakdown
    route_stats = {}
    for r in PILOT_ROUTES:
        orig, dest = r.split("-")
        count = (
            session.query(FareQuote)
            .filter(
                FareQuote.origin == orig,
                FareQuote.destination == dest,
                FareQuote.duplicate_flag == False
            )
            .count()
        )
        # Expected minimum = windows * airlines * flights
        expected = len(PILOT_WINDOWS) * min_expected_per_cell
        coverage = min(100.0, round((count / expected * 100), 1)) if expected > 0 else 0.0
        route_stats[r] = {
            "observed_quotes": count,
            "expected_minimum": expected,
            "missing_count": max(0, expected - count),
            "coverage_pct": coverage
        }

    # 2. Booking Window Breakdown
    window_stats = {}
    for w in PILOT_WINDOWS:
        count = (
            session.query(FareQuote)
            .filter(
                FareQuote.advance_window_days == w,
                FareQuote.duplicate_flag == False
            )
            .count()
        )
        expected = len(PILOT_ROUTES) * min_expected_per_cell
        coverage = min(100.0, round((count / expected * 100), 1)) if expected > 0 else 0.0
        window_stats[f"T+{w}"] = {
            "observed_quotes": count,
            "expected_minimum": expected,
            "missing_count": max(0, expected - count),
            "coverage_pct": coverage
        }

    # 3. Source Breakdown
    source_rows = (
        session.query(FareQuote.source_name, FareQuote.source_type)
        .filter(FareQuote.duplicate_flag == False)
        .all()
    )
    source_counts = defaultdict(int)
    for s_name, s_type in source_rows:
        source_counts[f"{s_name} ({s_type})"] += 1

    # 4. Overall Health Metrics
    total_valid = session.query(FareQuote).filter(FareQuote.duplicate_flag == False).count()
    total_raw = session.query(FareQuote).count()
    duplicate_count = session.query(FareQuote).filter(FareQuote.duplicate_flag == True).count()
    outlier_count = session.query(FareQuote).filter(FareQuote.outlier_flag == True).count()

    total_cells = len(PILOT_ROUTES) * len(PILOT_WINDOWS)
    filled_cells = 0
    for r in PILOT_ROUTES:
        orig, dest = r.split("-")
        for w in PILOT_WINDOWS:
            has_data = (
                session.query(FareQuote.id)
                .filter(
                    FareQuote.origin == orig,
                    FareQuote.destination == dest,
                    FareQuote.advance_window_days == w,
                    FareQuote.duplicate_flag == False
                )
                .first()
            )
            if has_data:
                filled_cells += 1

    matrix_coverage_pct = round((filled_cells / total_cells * 100), 2)

    return {
        "overall": {
            "total_raw_quotes": total_raw,
            "valid_clean_quotes": total_valid,
            "duplicate_quotes": duplicate_count,
            "outlier_quotes": outlier_count,
            "matrix_cells_total": total_cells,
            "matrix_cells_covered": filled_cells,
            "matrix_coverage_pct": matrix_coverage_pct
        },
        "by_route": route_stats,
        "by_window": window_stats,
        "by_source": dict(source_counts)
    }

def print_missing_data_report(report: Dict[str, Any]):
    """Pretty prints the missing data report to console in ASCII table format."""
    print("=" * 68)
    print("         DATA QUALITY & MISSING OBSERVATIONS AUDIT REPORT")
    print("=" * 68)

    ov = report["overall"]
    print(f"Total Raw Quotes        : {ov['total_raw_quotes']:,}")
    print(f"Valid Non-Duplicate     : {ov['valid_clean_quotes']:,}")
    print(f"Flagged Duplicates      : {ov['duplicate_quotes']:,}")
    print(f"Flagged Outliers        : {ov['outlier_quotes']:,}")
    print(f"Route-Window Matrix Cov : {ov['matrix_cells_covered']}/{ov['matrix_cells_total']} ({ov['matrix_coverage_pct']}%)")
    print("-" * 68)

    print(f"{'ROUTE':<12} | {'OBSERVED':<10} | {'EXPECTED':<10} | {'MISSING':<10} | {'COVERAGE':<10}")
    print("-" * 68)
    for route, s in report["by_route"].items():
        print(f"{route:<12} | {s['observed_quotes']:<10} | {s['expected_minimum']:<10} | {s['missing_count']:<10} | {s['coverage_pct']:>8.1f}%")
    print("-" * 68)

    print(f"{'WINDOW':<12} | {'OBSERVED':<10} | {'EXPECTED':<10} | {'MISSING':<10} | {'COVERAGE':<10}")
    print("-" * 68)
    for win, s in report["by_window"].items():
        print(f"{win:<12} | {s['observed_quotes']:<10} | {s['expected_minimum']:<10} | {s['missing_count']:<10} | {s['coverage_pct']:>8.1f}%")
    print("-" * 68)

    print("BY SOURCE:")
    for src, cnt in report["by_source"].items():
        print(f"  - {src:<40}: {cnt:,} valid quotes")
    print("=" * 68)
