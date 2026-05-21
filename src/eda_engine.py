# ================================================================
# src/eda_engine.py
# ================================================================
# CONTEXT:
#   We have processed-data.csv — clean, typed, enriched by Module 05.
#   Now we need to UNDERSTAND what is in it.
#
# THE BUSINESS QUESTION:
#   The VP of People wants to know:
#     - How are salaries distributed across departments?
#     - Do experience and salary correlate as expected?
#     - Are there time trends in our hiring or performance data?
#
# THE ANALOGY:
#   Imagine you just received a report from every department in the company.
#   Before presenting to the board, you need to read it, find the patterns,
#   and summarise the key findings.
#   EDAEngine reads the data report, finds the patterns, and summarises them.
#
# WHY A CLASS AND NOT JUST FUNCTIONS?
#   Because we need to run 4 different types of analysis and keep ALL results.
#   A class stores everything in self.results so any other module can access:
#     engine.results["group_analysis"]  → group stats
#     engine.results["correlation"]     → correlation pairs
#   Functions would run and throw away results. The class remembers.
#
# DESIGN PRINCIPLE: READ-ONLY
#   EDAEngine never modifies the DataFrame. It only reads and summarises.
#   (Same as DataValidator in Module 05 — analysts inspect, they do not edit.)
# ================================================================

# ── IMPORTS ───────────────────────────────────────────────────────
import sys        # sys: for manipulating Python's module search path
import pathlib    # pathlib: cross-platform file paths

# Walk up from this file's directory until we find config.py
# This makes the import work whether the file is run from any directory
_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd    # pandas: the core Python data library
import numpy as np     # numpy: numerical operations used for correlation matrix

# Import our settings from config.py
from config import (
    INDUSTRY,              # which industry schema ("bootcamp_data")
    DATA_PATH,             # where processed-data.csv lives
    REPORTS_DIR,           # where to save the report
    TOP_N_GROUPS,          # how many top groups to show (8)
    CORRELATION_THRESHOLD, # minimum r to include (0.3)
    logger                 # shared logger
)

import pathlib

import math
import pathlib

import pandas as pd

try:
    from scipy.stats import chi2_contingency
except ModuleNotFoundError:
    chi2_contingency = None

from config import (
    ALPHA,
    ANALYSIS_REPORT_PATH,
    ANOMALIES_PATH,
    PROCESSED_DATA_PATH,
    SEGMENT_PROFILE_PATH,
    logger,
)

from src.anomaly_detector import AnomalyDetector


class SegmentProfiler:
    """Compute transaction and fraud statistics by customer segment."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.profile = pd.DataFrame()

    def compute(self) -> pd.DataFrame:
        amount_col = "transaction_value" if "transaction_value" in self.df.columns else "amount"

        grouped = self.df.groupby("segment", dropna=False).agg(
            transaction_count=("transaction_id", "count"),
            unique_customers=("customer_id", "nunique"),
            total_amount=(amount_col, "sum"),
            avg_amount=(amount_col, "mean"),
            median_amount=(amount_col, "median"),
            max_amount=(amount_col, "max"),
            fraud_count=("is_fraud", "sum"),
        )

        grouped["fraud_rate"] = grouped["fraud_count"] / grouped["transaction_count"]
        grouped["amount_per_customer"] = grouped["total_amount"] / grouped["unique_customers"]
        grouped = grouped.sort_values("transaction_count", ascending=False)

        self.profile = grouped.reset_index()
        return self.profile.copy()


class EDAEngine:
    """Run NexBank EDA: fraud patterns, segment profiling, chi-square, anomalies."""

    def __init__(self, data_path=PROCESSED_DATA_PATH):
        self.data_path = pathlib.Path(data_path)
        self.df = pd.DataFrame()
        self.profile = {}
        self.fraud_tables = {}
        self.segment_profile = pd.DataFrame()
        self.chi_square_result = {}
        self.anomalies = pd.DataFrame()
        self.anomaly_summary = {}

    def load_data(self) -> "EDAEngine":
        if not self.data_path.exists():
            raise FileNotFoundError(f"Processed data not found: {self.data_path}")

        self.df = pd.read_csv(self.data_path, low_memory=False)

        if "is_fraud" in self.df.columns:
            self.df["is_fraud"] = self.df["is_fraud"].astype(str).str.lower().isin(["true", "1", "yes"])

        for col in ["transaction_date", "alert_date", "opened_date", "customer_since", "date_of_birth"]:
            if col in self.df.columns:
                self.df[col] = pd.to_datetime(self.df[col], errors="coerce")

        if "transaction_hour" not in self.df.columns and "transaction_time" in self.df.columns:
            self.df["transaction_hour"] = pd.to_datetime(
                self.df["transaction_time"], format="%H:%M", errors="coerce"
            ).dt.hour

        logger.info(f"Loaded {len(self.df):,} rows from {self.data_path}")
        return self

    def profile_data(self) -> "EDAEngine":
        self.profile = {
            "rows": len(self.df),
            "columns": len(self.df.columns),
            "unique_transactions": int(self.df["transaction_id"].nunique()),
            "unique_customers": int(self.df["customer_id"].nunique()),
            "fraud_rows": int(self.df["is_fraud"].sum()),
            "fraud_rate": float(self.df["is_fraud"].mean()),
            "total_transaction_value": float(self._amount_series().sum()),
            "avg_transaction_value": float(self._amount_series().mean()),
        }
        return self

    def fraud_patterns(self) -> "EDAEngine":
        dimensions = ["merchant_category", "channel", "transaction_hour", "transaction_month", "segment"]

        for dim in dimensions:
            if dim not in self.df.columns:
                continue

            table = self.df.groupby(dim, dropna=False).agg(
                transaction_count=("transaction_id", "count"),
                fraud_count=("is_fraud", "sum"),
                avg_amount=(self._amount_col(), "mean"),
                total_amount=(self._amount_col(), "sum"),
            )
            table["fraud_rate"] = table["fraud_count"] / table["transaction_count"]
            self.fraud_tables[dim] = table.sort_values(
                ["fraud_rate", "fraud_count"], ascending=False
            ).reset_index()

        return self

    def group_analysis(self) -> "EDAEngine":
        self.segment_profile = SegmentProfiler(self.df).compute()
        return self

    def chi_square_test(self, category_col: str = "merchant_category") -> "EDAEngine":
        contingency = pd.crosstab(self.df[category_col], self.df["is_fraud"])
        if chi2_contingency is not None:
            chi2, p_value, dof, expected = chi2_contingency(contingency)
        else:
            chi2, p_value, dof = self._chi_square_fallback(contingency)

        self.chi_square_result = {
            "category_col": category_col,
            "chi2": float(chi2),
            "p_value": float(p_value),
            "degrees_of_freedom": int(dof),
            "alpha": ALPHA,
            "is_significant": bool(p_value < ALPHA),
        }
        return self

    def detect_anomalies(self) -> "EDAEngine":
        detector = AnomalyDetector(self.df)
        detector.add_amount_scores().flag_fraud_anomalies()

        self.anomalies = detector.get_anomalies()
        self.anomaly_summary = detector.summary()
        return self

    def save_outputs(self) -> "EDAEngine":
        self.segment_profile.to_csv(SEGMENT_PROFILE_PATH, index=False)
        self.anomalies.to_csv(ANOMALIES_PATH, index=False)
        self.write_report()
        return self

    def write_report(self) -> None:
        lines = [
            "NEXBANK BANKING EDA REPORT",
            "=" * 60,
            "",
            "DATA PROFILE",
            f"Rows: {self.profile['rows']:,}",
            f"Columns: {self.profile['columns']:,}",
            f"Unique transactions: {self.profile['unique_transactions']:,}",
            f"Unique customers: {self.profile['unique_customers']:,}",
            f"Fraud rows: {self.profile['fraud_rows']:,}",
            f"Fraud rate: {self.profile['fraud_rate']:.2%}",
            "",
            "CHI-SQUARE TEST",
            f"Variable tested: {self.chi_square_result['category_col']}",
            f"Chi-square statistic: {self.chi_square_result['chi2']:.4f}",
            f"p-value: {self.chi_square_result['p_value']:.6f}",
            f"Significant at alpha={ALPHA}: {self.chi_square_result['is_significant']}",
            "",
            "ANOMALY SUMMARY",
        ]

        for key, value in self.anomaly_summary.items():
            lines.append(f"{key}: {value:,}" if isinstance(value, int) else f"{key}: {value}")

        lines.extend(["", "TOP FRAUD PATTERNS"])

        for name, table in self.fraud_tables.items():
            lines.append("")
            lines.append(name.upper())
            lines.append(table.head(10).to_string(index=False))

        lines.extend(["", "SEGMENT PROFILE", self.segment_profile.to_string(index=False)])

        ANALYSIS_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Wrote report to {ANALYSIS_REPORT_PATH}")

    def run_all(self) -> "EDAEngine":
        return (
            self.load_data()
            .profile_data()
            .fraud_patterns()
            .group_analysis()
            .chi_square_test()
            .detect_anomalies()
            .save_outputs()
        )

    def _amount_col(self) -> str:
        return "transaction_value" if "transaction_value" in self.df.columns else "amount"

    def _amount_series(self) -> pd.Series:
        return pd.to_numeric(self.df[self._amount_col()], errors="coerce")

    @staticmethod
    def _chi_square_fallback(contingency: pd.DataFrame) -> tuple:
        """Compute chi-square and approximate p-value when SciPy is unavailable."""
        observed = contingency.astype(float)
        total = observed.to_numpy().sum()
        row_totals = observed.sum(axis=1)
        col_totals = observed.sum(axis=0)
        expected = pd.DataFrame(
            {
                col: row_totals * col_totals[col] / total
                for col in observed.columns
            },
            index=observed.index,
        )

        chi2 = (((observed - expected) ** 2) / expected).to_numpy().sum()
        dof = (observed.shape[0] - 1) * (observed.shape[1] - 1)
        p_value = EDAEngine._chi_square_survival(float(chi2), int(dof))
        return float(chi2), float(p_value), int(dof)

    @staticmethod
    def _chi_square_survival(x: float, dof: int) -> float:
        """Regularized upper incomplete gamma Q(dof/2, x/2)."""
        if x < 0 or dof < 1:
            return float("nan")

        a = dof / 2.0
        z = x / 2.0
        if z == 0:
            return 1.0

        return EDAEngine._gammaincc(a, z)

    @staticmethod
    def _gammaincc(a: float, x: float) -> float:
        eps = 1e-14
        max_iter = 200
        gln = math.lgamma(a)

        if x < a + 1.0:
            ap = a
            term = 1.0 / a
            total = term
            for _ in range(max_iter):
                ap += 1.0
                term *= x / ap
                total += term
                if abs(term) < abs(total) * eps:
                    break
            lower = total * math.exp(-x + a * math.log(x) - gln)
            return max(0.0, min(1.0, 1.0 - lower))

        b = x + 1.0 - a
        c = 1.0 / 1e-300
        d = 1.0 / b
        h = d
        for i in range(1, max_iter + 1):
            an = -i * (i - a)
            b += 2.0
            d = an * d + b
            if abs(d) < 1e-300:
                d = 1e-300
            c = b + an / c
            if abs(c) < 1e-300:
                c = 1e-300
            d = 1.0 / d
            delta = d * c
            h *= delta
            if abs(delta - 1.0) < eps:
                break
        return max(0.0, min(1.0, math.exp(-x + a * math.log(x) - gln) * h))
