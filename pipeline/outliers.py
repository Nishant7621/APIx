import logging
import numpy as np
from typing import Dict, Any, List, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session
from database.models import FareQuote

logger = logging.getLogger("apix.pipeline.outliers")

def detect_outliers_iqr_mad(
    session: Session,
    iqr_multiplier: float = 1.5,
    mad_threshold: float = 3.5,
    method: str = "both"  # "iqr", "mad", or "both"
) -> Dict[str, Any]:
    """
    Flags outliers per (origin, destination, advance_window_days) using transparent statistical rules.
    - IQR: [Q1 - 1.5*IQR, Q3 + 1.5*IQR]
    - MAD: Modified Z-score = 0.6745 * |x - median| / MAD > 3.5

    STRICT PILOT RULE: Outliers are flagged with outlier_flag=True for transparency,
    never automatically deleted.
    """
    quotes = (
        session.query(FareQuote)
        .filter(FareQuote.duplicate_flag == False)
        .all()
    )

    # Group by (origin, destination, advance_window_days)
    groups = defaultdict(list)
    for q in quotes:
        key = (q.origin, q.destination, q.advance_window_days)
        groups[key].append(q)

    total_evaluated = len(quotes)
    iqr_outliers_count = 0
    mad_outliers_count = 0
    total_flagged_count = 0

    for key, group_quotes in groups.items():
        if len(group_quotes) < 4:
            # Need minimum observations for meaningful statistical percentiles
            continue

        prices = np.array([float(q.total_fare) for q in group_quotes], dtype=float)

        # 1. IQR Calculation
        q25, q75 = np.percentile(prices, [25, 75])
        iqr = q75 - q25
        lower_iqr = q25 - (iqr_multiplier * iqr)
        upper_iqr = q75 + (iqr_multiplier * iqr)

        # 2. MAD Calculation
        median_price = np.median(prices)
        abs_deviations = np.abs(prices - median_price)
        mad = np.median(abs_deviations)

        for q in group_quotes:
            is_outlier = False
            reasons = []

            price = float(q.total_fare)

            # Check IQR
            if method in ("iqr", "both"):
                if price < lower_iqr or price > upper_iqr:
                    is_outlier = True
                    iqr_outliers_count += 1
                    reasons.append(f"IQR outlier (bounds: [{lower_iqr:.1f}, {upper_iqr:.1f}])")

            # Check MAD
            if method in ("mad", "both") and mad > 0:
                mod_z = 0.6745 * abs(price - median_price) / mad
                if mod_z > mad_threshold:
                    is_outlier = True
                    mad_outliers_count += 1
                    reasons.append(f"MAD outlier (mod_z={mod_z:.2f} > {mad_threshold})")

            if is_outlier:
                if not q.outlier_flag:
                    q.outlier_flag = True
                    total_flagged_count += 1
                note_str = f"[OUTLIER: {', '.join(reasons)}]"
                existing = q.validation_notes or ""
                if note_str not in existing:
                    q.validation_notes = f"{existing} | {note_str}" if existing else note_str
            else:
                q.outlier_flag = False

    session.commit()
    logger.info(
        f"Outlier detection completed. Evaluated: {total_evaluated}, "
        f"IQR outliers: {iqr_outliers_count}, MAD outliers: {mad_outliers_count}, Total flagged: {total_flagged_count}"
    )

    return {
        "total_evaluated": total_evaluated,
        "iqr_outliers": iqr_outliers_count,
        "mad_outliers": mad_outliers_count,
        "total_flagged_outliers": total_flagged_count,
        "outlier_rate_pct": round((total_flagged_count / total_evaluated * 100), 2) if total_evaluated > 0 else 0.0
    }

def run_isolation_forest_secondary_flag(session: Session) -> Dict[str, Any]:
    """
    Optional secondary anomaly scorer using Isolation Forest.
    Runs as an auxiliary audit tool, NOT replacing the transparent IQR/MAD rules.
    """
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        logger.info("scikit-learn is not installed; Isolation Forest secondary scoring skipped.")
        return {"status": "SKIPPED", "reason": "scikit-learn not installed"}

    quotes = session.query(FareQuote).filter(FareQuote.duplicate_flag == False).all()
    if len(quotes) < 20:
        return {"status": "SKIPPED", "reason": "insufficient records"}

    prices = np.array([[float(q.total_fare)] for q in quotes])
    iso = IsolationForest(contamination=0.02, random_state=42)
    preds = iso.fit_predict(prices)  # -1 for anomaly, 1 for normal

    flagged = 0
    for q, pred in zip(quotes, preds):
        if pred == -1:
            flagged += 1
            note = "[AUX_ANOMALY: IsolationForest secondary score]"
            existing = q.validation_notes or ""
            if note not in existing:
                q.validation_notes = f"{existing} | {note}" if existing else note

    session.commit()
    return {"status": "SUCCESS", "isolation_forest_anomalies": flagged}
