import pathlib
import sys

import pandas as pd

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import logger


class DataValidator:
    """Validate the raw NexBank banking extract without modifying it."""

    EXPECTED_COLUMNS = [
        "transaction_id", "account_id", "customer_id", "transaction_date",
        "transaction_time", "amount", "transaction_type", "merchant_name",
        "merchant_category", "channel", "transaction_status", "is_fraud",
        "balance_after", "first_name", "last_name", "email", "city",
        "date_of_birth", "credit_score", "customer_since", "segment",
        "account_type", "account_number", "balance", "currency",
        "opened_date", "account_status", "account_interest_rate", "loan_id",
        "loan_type", "principal", "loan_interest_rate", "term_months",
        "monthly_payment", "loan_outstanding_balance", "loan_status",
        "risk_grade", "alert_id", "alert_date", "alert_type",
        "alert_severity", "alert_status", "amount_at_risk",
    ]

    REQUIRED_COLUMNS = [
        "transaction_id", "account_id", "customer_id", "transaction_date",
        "transaction_time", "amount", "transaction_type", "merchant_name",
        "transaction_status", "is_fraud", "balance_after", "first_name",
        "last_name", "city", "date_of_birth", "credit_score",
        "customer_since", "segment", "account_type", "account_number",
        "currency", "opened_date", "account_status", "account_interest_rate",
    ]

    OPTIONAL_PROFILE_COLUMNS = ["email", "merchant_category", "channel", "balance"]

    OPTIONAL_LOAN_COLUMNS = [
        "loan_id", "loan_type", "principal", "loan_interest_rate",
        "term_months", "monthly_payment", "loan_outstanding_balance",
        "loan_status", "risk_grade",
    ]

    OPTIONAL_ALERT_COLUMNS = [
        "alert_id", "alert_date", "alert_type", "alert_severity",
        "alert_status", "amount_at_risk",
    ]

    NON_NEGATIVE_COLUMNS = [
        "credit_score", "account_interest_rate", "principal",
        "loan_interest_rate", "term_months", "monthly_payment",
        "loan_outstanding_balance", "amount_at_risk",
    ]

    DATE_COLUMNS = [
        "transaction_date", "date_of_birth", "customer_since",
        "opened_date", "alert_date",
    ]

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.issues = []
        self.stats = {}
        self._passed = True

    def check_not_empty(self) -> "DataValidator":
        if self.df.empty:
            self._add_issue("CRITICAL", "row_count", "DataFrame has no rows.")
            self._passed = False
        else:
            logger.info(f"[VALIDATE] Row count: {len(self.df):,}")
        return self

    def check_schema(self) -> "DataValidator":
        missing = [col for col in self.EXPECTED_COLUMNS if col not in self.df.columns]
        extra = [col for col in self.df.columns if col not in self.EXPECTED_COLUMNS]

        if missing:
            self._add_issue("CRITICAL", "schema", f"Missing columns: {missing}")
            self._passed = False
        if extra:
            self._add_issue("WARNING", "schema", f"Unexpected extra columns: {extra}")
        if not missing:
            logger.info("[VALIDATE] Schema check passed.")
        return self

    def check_nulls(self) -> "DataValidator":
        if self.df.empty:
            return self

        for col in self.REQUIRED_COLUMNS:
            if col not in self.df.columns:
                continue
            count = int(self.df[col].isna().sum())
            if count:
                pct = round(count / len(self.df) * 100, 1)
                self._add_issue("CRITICAL", col, f"{count:,} missing required values ({pct}%).")
                self._passed = False

        for col in self.OPTIONAL_PROFILE_COLUMNS:
            self._record_optional_nulls(col, "WARNING", "missing profile or transaction context values")

        for col in self.OPTIONAL_LOAN_COLUMNS:
            self._record_optional_nulls(col, "INFO", "blank loan values for customers without joined loans")

        for col in self.OPTIONAL_ALERT_COLUMNS:
            self._record_optional_nulls(col, "INFO", "blank fraud alert values for transactions without alerts")

        return self

    def check_duplicates(self) -> "DataValidator":
        duplicate_rows = int(self.df.duplicated().sum())

        if duplicate_rows:
            pct = round(duplicate_rows / len(self.df) * 100, 1)
            self._add_issue("WARNING", "duplicates", f"{duplicate_rows:,} exact duplicate rows ({pct}%).")
        else:
            logger.info("[VALIDATE] Exact duplicate check passed.")

        if "transaction_id" in self.df.columns:
            repeated = int(self.df["transaction_id"].duplicated().sum())
            if repeated:
                self._add_issue(
                    "INFO",
                    "transaction_id",
                    f"{repeated:,} repeated transaction_id rows caused by loan/alert joins.",
                )
        return self

    def check_dates(self) -> "DataValidator":
        for col in self.DATE_COLUMNS:
            if col not in self.df.columns:
                continue
            parsed = pd.to_datetime(self.df[col], errors="coerce")
            invalid = int(parsed.isna().sum() - self.df[col].isna().sum())
            if invalid:
                self._add_issue("CRITICAL", col, f"{invalid:,} invalid date values.")
                self._passed = False
        return self

    def check_numeric_ranges(self) -> "DataValidator":
        for col in self.NON_NEGATIVE_COLUMNS:
            if col not in self.df.columns:
                continue
            values = pd.to_numeric(self.df[col], errors="coerce")
            negative_count = int((values < 0).sum())
            if negative_count:
                self._add_issue("CRITICAL", col, f"{negative_count:,} negative values found.")
                self._passed = False

        if "credit_score" in self.df.columns:
            score = pd.to_numeric(self.df["credit_score"], errors="coerce")
            bad_score = int(((score < 300) | (score > 850)).sum())
            if bad_score:
                self._add_issue("CRITICAL", "credit_score", f"{bad_score:,} values outside 300-850.")
                self._passed = False

        return self

    def check_business_rules(self) -> "DataValidator":
        if "amount" in self.df.columns:
            amount = pd.to_numeric(self.df["amount"], errors="coerce")
            negative_amounts = int((amount < 0).sum())
            if negative_amounts:
                self._add_issue(
                    "WARNING",
                    "amount",
                    f"{negative_amounts:,} negative transaction amounts found. "
                    "These are treated as signed banking movements, not fatal errors.",
                )

        if {"is_fraud", "alert_id"}.issubset(self.df.columns):
            fraud = self.df["is_fraud"].astype(str).str.lower().isin(["true", "1", "yes", "y"])
            missing_alert = int((fraud & self.df["alert_id"].isna()).sum())
            if missing_alert:
                self._add_issue("WARNING", "alert_id", f"{missing_alert:,} fraud rows have no alert record.")

        if {"loan_id", "loan_outstanding_balance", "principal"}.issubset(self.df.columns):
            outstanding = pd.to_numeric(self.df["loan_outstanding_balance"], errors="coerce")
            principal = pd.to_numeric(self.df["principal"], errors="coerce")
            has_loan = self.df["loan_id"].notna()
            over_principal = int((has_loan & outstanding.notna() & principal.notna() & (outstanding > principal)).sum())
            if over_principal:
                self._add_issue("WARNING", "loan_outstanding_balance", f"{over_principal:,} rows above principal.")

        return self

    def compute_stats(self) -> "DataValidator":
        self.stats = {
            "rows": len(self.df),
            "columns": len(self.df.columns),
            "total_nulls": int(self.df.isna().sum().sum()),
            "duplicate_rows": int(self.df.duplicated().sum()),
            "issues": len(self.issues),
            "critical_count": sum(1 for i in self.issues if i["severity"] == "CRITICAL"),
            "warning_count": sum(1 for i in self.issues if i["severity"] == "WARNING"),
            "info_count": sum(1 for i in self.issues if i["severity"] == "INFO"),
            "passed": self._passed,
        }
        logger.info(f"[VALIDATE] Result: {'PASSED' if self._passed else 'FAILED'} with {len(self.issues)} issue note(s).")
        return self

    def _record_optional_nulls(self, col: str, severity: str, label: str) -> None:
        if col not in self.df.columns:
            return
        count = int(self.df[col].isna().sum())
        if count:
            pct = round(count / len(self.df) * 100, 1)
            self._add_issue(severity, col, f"{count:,} {label} ({pct}%).")

    def _add_issue(self, severity: str, column: str, message: str) -> None:
        self.issues.append({"severity": severity, "column": column, "message": message})
        if severity == "CRITICAL":
            logger.error(f"[VALIDATE] {severity} | {column} | {message}")
        elif severity == "WARNING":
            logger.warning(f"[VALIDATE] {severity} | {column} | {message}")
        else:
            logger.info(f"[VALIDATE] {severity} | {column} | {message}")
