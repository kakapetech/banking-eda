import datetime as dt

import pandas as pd


class DataTransformer:
    """Clean and enrich the NexBank banking extract."""

    NUMERIC_COLUMNS = [
        "transaction_id", "account_id", "customer_id", "amount",
        "balance_after", "credit_score", "balance", "account_interest_rate",
        "loan_id", "principal", "loan_interest_rate", "term_months",
        "monthly_payment", "loan_outstanding_balance", "alert_id",
        "amount_at_risk",
    ]

    DATE_COLUMNS = [
        "transaction_date", "date_of_birth", "customer_since",
        "opened_date", "alert_date",
    ]

    TEXT_COLUMNS = [
        "transaction_time", "transaction_type", "merchant_name",
        "merchant_category", "channel", "transaction_status", "first_name",
        "last_name", "email", "city", "segment", "account_type",
        "account_number", "currency", "account_status", "loan_type",
        "loan_status", "risk_grade", "alert_type", "alert_severity",
        "alert_status",
    ]

    ZERO_FILL_COLUMNS = [
        "principal", "loan_interest_rate", "term_months", "monthly_payment",
        "loan_outstanding_balance", "amount_at_risk",
    ]

    TEXT_FILL_VALUES = {
        "email": "Unknown",
        "merchant_category": "Unknown",
        "channel": "Unknown",
        "loan_type": "No Loan",
        "loan_status": "No Loan",
        "risk_grade": "No Loan",
        "alert_type": "No Alert",
        "alert_severity": "No Alert",
        "alert_status": "No Alert",
    }

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.original_len = len(df)
        self.changes = []

    def fix_types(self) -> "DataTransformer":
        for col in self.NUMERIC_COLUMNS:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

        for col in self.DATE_COLUMNS:
            if col in self.df.columns:
                self.df[col] = pd.to_datetime(self.df[col], errors="coerce").dt.date

        if "is_fraud" in self.df.columns:
            self.df["is_fraud"] = self.df["is_fraud"].map(self._to_bool)

        self._record_change("Standardized numeric, date, and boolean columns.")
        return self

    def clean_text(self) -> "DataTransformer":
        for col in self.TEXT_COLUMNS:
            if col not in self.df.columns:
                continue
            self.df[col] = self.df[col].astype("string").str.strip()
            self.df[col] = self.df[col].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "<NA>": pd.NA})

        if "segment" in self.df.columns:
            self.df["segment"] = self.df["segment"].str.title()
        if "currency" in self.df.columns:
            self.df["currency"] = self.df["currency"].str.upper()

        self._record_change("Trimmed text fields and normalized common category casing.")
        return self

    def fill_nulls(self) -> "DataTransformer":
        for col in self.ZERO_FILL_COLUMNS:
            self._fill_column(col, 0)

        for col, value in self.TEXT_FILL_VALUES.items():
            self._fill_column(col, value)

        if "balance" in self.df.columns:
            missing = int(self.df["balance"].isna().sum())
            if missing:
                median_value = self.df["balance"].median()
                self.df["balance"] = self.df["balance"].fillna(median_value)
                self._record_change(f"Filled {missing:,} missing values in balance with median {median_value:.2f}.")

        return self

    def drop_duplicates(self) -> "DataTransformer":
        before = len(self.df)
        self.df = self.df.drop_duplicates().reset_index(drop=True)
        removed = before - len(self.df)

        if removed:
            self._record_change(f"Removed {removed:,} exact duplicate rows.")
        else:
            self._record_change("No exact duplicate rows found.")
        return self

    def add_derived_columns(self) -> "DataTransformer":
        if {"first_name", "last_name"}.issubset(self.df.columns):
            self.df["customer_name"] = (
                self.df["first_name"].astype("string").fillna("")
                + " "
                + self.df["last_name"].astype("string").fillna("")
            ).str.strip()

        if "amount" in self.df.columns:
            self.df["signed_amount"] = self.df["amount"]
            self.df["transaction_value"] = self.df["amount"].abs()
            self.df["amount_was_negative"] = self.df["amount"] < 0

        self.df["has_loan"] = self.df["loan_id"].notna() if "loan_id" in self.df.columns else False
        self.df["has_fraud_alert"] = self.df["alert_id"].notna() if "alert_id" in self.df.columns else False

        if {"balance_after", "amount"}.issubset(self.df.columns):
            self.df["balance_before_estimate"] = (self.df["balance_after"] - self.df["amount"]).round(2)

        if {"loan_outstanding_balance", "principal"}.issubset(self.df.columns):
            principal = self.df["principal"].where(self.df["principal"] != 0, pd.NA)
            self.df["loan_remaining_pct"] = (
                self.df["loan_outstanding_balance"] / principal * 100
            ).fillna(0).round(2)

        if "credit_score" in self.df.columns:
            self.df["credit_score_band"] = pd.cut(
                self.df["credit_score"],
                bins=[0, 579, 669, 739, 799, 850],
                labels=["Poor", "Fair", "Good", "Very Good", "Excellent"],
                include_lowest=True,
            ).astype("string").fillna("Unknown")

        if "transaction_date" in self.df.columns:
            tx_date = pd.to_datetime(self.df["transaction_date"], errors="coerce")
            self.df["transaction_year"] = tx_date.dt.year
            self.df["transaction_month"] = tx_date.dt.month

        self._record_change("Added banking metrics and date features.")
        return self

    def add_metadata(self) -> "DataTransformer":
        self.df["_source_system"] = "nexbank_sql_extractor"
        self.df["_processed_at"] = dt.datetime.now().isoformat(timespec="seconds")
        self.df["_pipeline_version"] = "1.0.0"
        self._record_change("Added pipeline metadata columns.")
        return self

    def summary(self) -> dict:
        return {
            "original_rows": self.original_len,
            "final_rows": len(self.df),
            "rows_removed": self.original_len - len(self.df),
            "final_columns": len(self.df.columns),
            "changes_count": len(self.changes),
            "change_log": self.changes,
        }

    def _fill_column(self, col: str, value) -> None:
        if col not in self.df.columns:
            return
        missing = int(self.df[col].isna().sum())
        if missing:
            self.df[col] = self.df[col].fillna(value)
            self._record_change(f"Filled {missing:,} missing values in {col} with {value!r}.")

    def _record_change(self, message: str) -> None:
        self.changes.append(message)

    @staticmethod
    def _to_bool(value) -> bool:
        if pd.isna(value):
            return False
        return str(value).strip().lower() in {"true", "1", "yes", "y"}
