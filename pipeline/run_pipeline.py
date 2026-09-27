import sys
import logging
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from database.connection import get_session_maker
from pipeline.deduplication import flag_duplicates
from pipeline.cleaner_validator import standardize_and_validate
from pipeline.outliers import detect_outliers_iqr_mad, run_isolation_forest_secondary_flag
from pipeline.missing_data_report import generate_missing_data_report, print_missing_data_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s]: %(message)s")

def execute_pipeline():
    """
    Executes the complete Data Quality Pipeline:
    1. Deduplication
    2. Standardization & Component Validation
    3. Transparent Outlier Detection (IQR & MAD)
    4. Secondary Anomaly Scoring
    5. Missing Data & Coverage Audit
    """
    print("\n" + "=" * 68)
    print("      AIRLINE PRICE INDEX (APIx) - DATA QUALITY PIPELINE")
    print("=" * 68)

    SessionLocal = get_session_maker()
    session = SessionLocal()

    try:
        # Step 1: Deduplication
        print("\n[STEP 1/4] Running Deduplication...")
        dedup_res = flag_duplicates(session)
        print(f"  - Total records evaluated : {dedup_res['total_records']:,}")
        print(f"  - Duplicate records flagged: {dedup_res['duplicates_flagged']:,} ({dedup_res['duplicate_rate_pct']}%)")
        print(f"  - Unique records retained : {dedup_res['unique_records']:,}")

        # Step 2: Standardization & Validation
        print("\n[STEP 2/4] Running Standardization & Component Validation...")
        val_res = standardize_and_validate(session)
        print(f"  - Total records checked    : {val_res['total_records']:,}")
        print(f"  - Fields standardized      : {val_res['standardized_fields_count']:,}")
        print(f"  - Records with issues flagged: {val_res['records_with_validation_issues']:,}")
        print(f"  - Clean record rate        : {val_res['clean_record_percentage']}%")

        # Step 3: Outlier Detection (IQR & MAD)
        print("\n[STEP 3/4] Running Outlier Detection (IQR & MAD)...")
        out_res = detect_outliers_iqr_mad(session, iqr_multiplier=1.5, mad_threshold=3.5, method="both")
        print(f"  - Group observations evaluated : {out_res['total_evaluated']:,}")
        print(f"  - IQR outliers flagged         : {out_res['iqr_outliers']:,}")
        print(f"  - MAD outliers flagged         : {out_res['mad_outliers']:,}")
        print(f"  - Outlier flag rate            : {out_res['outlier_rate_pct']}%")
        print("  - Policy: All records preserved; none deleted.")

        # Optional: Secondary Isolation Forest
        iso_res = run_isolation_forest_secondary_flag(session)
        if iso_res.get("status") == "SUCCESS":
            print(f"  - Auxiliary Isolation Forest : {iso_res.get('isolation_forest_anomalies', 0)} secondary anomalies noted")

        # Step 4: Missing Data & Completeness Report
        print("\n[STEP 4/4] Generating Coverage & Completeness Report...")
        report = generate_missing_data_report(session)
        print_missing_data_report(report)

        print("\n[SUCCESS] Phase 3 Data Quality Pipeline executed successfully!\n")

    finally:
        session.close()

if __name__ == "__main__":
    execute_pipeline()
