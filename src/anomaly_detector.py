# ================================================================
# src/anomaly_detector.py
# ================================================================
# CONTEXT:
#   The EDAEngine found patterns. Now we need to find EXCEPTIONS.
#   Which specific employees have salaries that are statistically unusual?
#   Which production runs had defect rates that no normal run should produce?
#
# THE BUSINESS QUESTION:
#   "We know the average salary is £92k. But are there any employees whose
#    salaries are so far from normal that we should investigate them?
#    Either they are being underpaid (retention risk) or the record is wrong."
#
# THE ANALOGY:
#   Imagine plotting all salaries on a number line.
#   Most cluster in the middle. A few sit far to the left or right.
#   The AnomalyDetector finds those outliers using statistics.
#   It uses TWO methods and only flags something as confirmed if BOTH agree.
#   This "consensus" approach reduces false alarms.
#
# TWO DETECTION METHODS:
#   Method 1 — IQR (Interquartile Range):
#     Works on any distribution. No assumptions about shape.
#     Uses Q1 - 1.5×IQR as the lower fence and Q3 + 1.5×IQR as the upper fence.
#
#   Method 2 — Z-score:
#     Assumes normally distributed data.
#     Flags values more than 3 standard deviations from the mean.
#
# WHY USE TWO METHODS?
#   Each method has blind spots. IQR is robust to skewed data but can
#   miss outliers that cluster near the fence. Z-score catches extreme
#   values precisely but is sensitive to the mean being pulled by outliers.
#   Consensus (flagged by BOTH) gives us the most reliable results.
# ================================================================

import sys
import pathlib

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import numpy as np

from config import INDUSTRY, REPORTS_DIR, logger


class AnomalyDetector:
    """
    Detects statistical anomalies using IQR and Z-score methods.

    Uses consensus: a row is a CONFIRMED anomaly only if flagged by BOTH methods.
    Consensus reduces false positives compared to using either method alone.

    Attributes
    ──────────
    df         pd.DataFrame   the input DataFrame to scan
    results    dict           anomaly findings per column
    confirmed  pd.DataFrame   rows confirmed as anomalies (flagged by both methods)
    _n_checked int            number of columns that were checked
    """

    # Z-score threshold: values more than this many standard deviations
    # from the mean are flagged as outliers.
    # 3.0 is the standard (covers 99.73% of normal distribution inside the fence)
    ZSCORE_THRESHOLD = 3.0


class AnomalyDetector:
    """Detect suspicious banking transactions using IQR and Z-score rules."""

    def __init__(self, df: pd.DataFrame, amount_col: str = "transaction_value"):
        self.df = df.copy()
        self.amount_col = amount_col if amount_col in df.columns else "amount"
        self.anomalies = pd.DataFrame()

    def add_amount_scores(self) -> "AnomalyDetector":
        values = pd.to_numeric(self.df[self.amount_col], errors="coerce")

        q1 = values.quantile(0.25)
        q3 = values.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        mean = values.mean()
        std = values.std(ddof=0)

        self.df["amount_iqr_outlier"] = (values < lower) | (values > upper)
        self.df["amount_z_score"] = 0.0 if std == 0 else (values - mean) / std
        self.df["amount_z_outlier"] = self.df["amount_z_score"].abs() > 3.0
        self.df["amount_anomaly"] = self.df["amount_iqr_outlier"] & self.df["amount_z_outlier"]

        return self

    def flag_fraud_anomalies(self) -> "AnomalyDetector":
        if "amount_anomaly" not in self.df.columns:
            self.add_amount_scores()

        fraud = self.df["is_fraud"].astype(bool) if "is_fraud" in self.df.columns else False

        self.df["fraud_with_normal_amount"] = fraud & ~self.df["amount_anomaly"]
        self.df["suspicious_amount_not_marked_fraud"] = self.df["amount_anomaly"] & ~fraud

        self.anomalies = self.df[
            self.df["amount_anomaly"]
            | self.df["fraud_with_normal_amount"]
            | self.df["suspicious_amount_not_marked_fraud"]
        ].copy()

        return self

    def get_anomalies(self) -> pd.DataFrame:
        if self.anomalies.empty:
            self.flag_fraud_anomalies()
        return self.anomalies.copy()

    def summary(self) -> dict:
        if "amount_anomaly" not in self.df.columns:
            self.flag_fraud_anomalies()

        return {
            "rows_scanned": len(self.df),
            "amount_anomalies": int(self.df["amount_anomaly"].sum()),
            "fraud_with_normal_amount": int(self.df["fraud_with_normal_amount"].sum()),
            "suspicious_amount_not_marked_fraud": int(self.df["suspicious_amount_not_marked_fraud"].sum()),
            "total_flagged_rows": len(self.get_anomalies()),
        }
