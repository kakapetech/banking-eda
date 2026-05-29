# ================================================================
# src/data_extractor.py
# ================================================================
# The Darko Method 2026
#
# CONTEXT:
#   SQLQueryRunner can run ANY query.
#   DataExtractor runs ONE specific query: the production extraction
#   query in sql/05_extract_raw_data.sql.
#
#   DataExtractor is the DELIVERY of this project.
#   Its output — raw-data.csv — is the INPUT to Module 05 ETL.
#
# SINGLE RESPONSIBILITY:
#   Connect to the banking database, run the extraction SQL query,
#   load the results into a pandas DataFrame, and save it as
#   raw-data.csv. Nothing more. Nothing less.
#
# THE PIPELINE CONNECTION:
#   DataExtractor --> data/raw-data.csv --> Module 05 ETLPipeline
#
# JOIN STRUCTURE (transactions is the anchor table):
#   transactions
#     INNER JOIN customers     ON transactions.customer_id = customers.customer_id
#     INNER JOIN accounts      ON transactions.account_id  = accounts.account_id
#     LEFT  JOIN loans         ON transactions.customer_id = loans.customer_id
#     LEFT  JOIN fraud_alerts  ON transactions.transaction_id = fraud_alerts.transaction_id
#
#   Every transaction must have a customer and an account (INNER JOINs).
#   loans and fraud_alerts are LEFT JOINs — not every transaction has
#   a matching loan or fraud alert.
#
# ALIAS CONVENTIONS (prevents ambiguous column names in flat output):
#   accounts.status       -> account_status
#   accounts.interest_rate -> account_interest_rate
#   loans.status          -> loan_status
#   loans.interest_rate   -> loan_interest_rate
#   fraud_alerts.status   -> alert_status
#   transactions.status   -> transaction_status
#
# OUTPUT COLUMNS (38 total):
#   From transactions (13):
#     transaction_id, account_id, customer_id, transaction_date,
#     transaction_time, amount, transaction_type, merchant_name,
#     merchant_category, channel, transaction_status, is_fraud,
#     balance_after
#   From customers (8):
#     first_name, last_name, email, city, date_of_birth,
#     credit_score, customer_since, segment
#   From accounts (7):
#     account_type, account_number, balance, currency,
#     opened_date, account_status, account_interest_rate
#   From loans (8, LEFT JOIN — may be NULL):
#     loan_id, loan_type, principal, loan_interest_rate,
#     term_months, monthly_payment, loan_outstanding_balance,
#     loan_status, risk_grade
#   From fraud_alerts (7, LEFT JOIN — may be NULL):
#     alert_id, alert_date, alert_type, alert_severity,
#     alert_status, amount_at_risk
#
# NOTE: loans has 9 columns but loan_id makes it 9 from loans group.
#       Total: 13 + 8 + 7 + 9 + 6 = 43 columns (see OUTPUT_COLUMNS below)
# ================================================================

import sys, pathlib

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from config import SCHEMA, RAW_DATA_PATH, DB_AVAILABLE, logger
from src.query_runner import SQLQueryRunner


class DataExtractor:
    """
    Runs the production extraction query and saves data/raw-data.csv.

    This class has one job: extract the data and save it.
    SQLQueryRunner handles connection and execution.
    DataExtractor handles the business logic of which query to run.

    Output: 43 aliased columns ready for Module 05 ETL.
    """

    # All 43 output column names — used by report() and tests
    OUTPUT_COLUMNS = [
        # transactions (13)
        "transaction_id", "account_id", "customer_id",
        "transaction_date", "transaction_time", "amount",
        "transaction_type", "merchant_name", "merchant_category",
        "channel", "transaction_status", "is_fraud", "balance_after",
        # customers (8)
        "first_name", "last_name", "email", "city",
        "date_of_birth", "credit_score", "customer_since", "segment",
        # accounts (7)
        "account_type", "account_number", "balance", "currency",
        "opened_date", "account_status", "account_interest_rate",
        # loans (9, LEFT JOIN — may be NULL)
        "loan_id", "loan_type", "principal", "loan_interest_rate",
        "term_months", "monthly_payment", "loan_outstanding_balance",
        "loan_status", "risk_grade",
        # fraud_alerts (6, LEFT JOIN — may be NULL)
        "alert_id", "alert_date", "alert_type",
        "alert_severity", "alert_status", "amount_at_risk",
    ]

    def __init__(self):
        self.schema  = SCHEMA
        self.runner  = SQLQueryRunner()
        self.raw_df  = None
        self._status = "ready"

    # ================================================================
    # PUBLIC METHODS — pipeline chain: extract().save().report()
    # ================================================================

    def extract(self) -> "DataExtractor":
        """
        Run sql/05_extract_raw_data.sql and load results into self.raw_df.

        Falls back to synthetic banking data if the database is
        unavailable, so Module 05 can still be demonstrated offline.

        Returns self to enable method chaining.
        """
        logger.info(f"[EXTRACT] Starting extraction — schema: {self.schema}")

        if DB_AVAILABLE:
            self.raw_df = self.runner.run_file("05_extract_raw_data.sql")
        else:
            logger.warning("[EXTRACT] DB unavailable — generating synthetic raw data")
            self.raw_df = self._synthetic_raw_data()

        if self.raw_df is None or len(self.raw_df) == 0:
            logger.warning("[EXTRACT] Query returned 0 rows — using synthetic data")
            self.raw_df = self._synthetic_raw_data()

        self._status = "extracted"
        logger.info(
            f"[EXTRACT] {len(self.raw_df):,} rows x "
            f"{self.raw_df.shape[1]} columns extracted"
        )
        return self

    def save(self) -> "DataExtractor":
        """
        Save self.raw_df to data/raw-data.csv.
        This file is the input to Module 05 ETL.

        Returns self to enable method chaining.
        """
        if self.raw_df is None or len(self.raw_df) == 0:
            logger.error("[EXTRACT] No data to save. Run extract() first.")
            return self

        self.raw_df.to_csv(RAW_DATA_PATH, index=False, encoding="utf-8")
        file_size_kb = RAW_DATA_PATH.stat().st_size / 1024
        logger.info(
            f"[EXTRACT] Saved {len(self.raw_df):,} rows to "
            f"{RAW_DATA_PATH.name} ({file_size_kb:.1f} KB)"
        )
        self._status = "saved"
        return self

    def report(self) -> None:
        """
        Print a human-readable extraction summary to the terminal.

        Uses print() not logger — report() is formatted output for
        the analyst, not a system log entry.
        """
        if self.raw_df is None:
            print("No data extracted. Run extract() first.")
            return

        print()
        print("=" * 60)
        print("  P05 BANKING — EXTRACTION COMPLETE")
        print(f"  Schema : {self.schema.upper()}")
        print("=" * 60)
        print(f"  Rows extracted         : {len(self.raw_df):,}")
        print(f"  Columns                : {self.raw_df.shape[1]}")
        print(f"  Output file            : {RAW_DATA_PATH.name}")
        if RAW_DATA_PATH.exists():
            print(f"  File size              : {RAW_DATA_PATH.stat().st_size / 1024:.1f} KB")
        print()

        # ── NULL detection ─────────────────────────────────────────────
        left_join_cols = {
            "loan_id", "loan_type", "principal", "loan_interest_rate",
            "term_months", "monthly_payment", "loan_outstanding_balance",
            "loan_status", "risk_grade",
            "alert_id", "alert_date", "alert_type",
            "alert_severity", "alert_status", "amount_at_risk",
        }
        print("  DATA QUALITY IN RAW DATA (Module 05 will clean these):")
        nulls     = self.raw_df.isna().sum()
        null_cols = nulls[nulls > 0]
        if not null_cols.empty:
            for col in null_cols.index:
                pct  = round(null_cols[col] / len(self.raw_df) * 100, 1)
                note = " ← expected (LEFT JOIN)" if col in left_join_cols else ""
                print(f"    NULL {col}: {null_cols[col]:,} rows ({pct}%){note}")
        else:
            print("    No NULL values detected.")

        # ── Business metrics preview ───────────────────────────────────
        if "amount" in self.raw_df.columns:
            total_vol = self.raw_df["amount"].sum()
            avg_txn   = self.raw_df["amount"].mean()
            print(f"\n  Total transaction volume : ${total_vol:,.2f}")
            print(f"  Avg transaction amount   : ${avg_txn:,.2f}")

        if "is_fraud" in self.raw_df.columns:
            fraud_count = self.raw_df["is_fraud"].sum()
            fraud_pct   = fraud_count / len(self.raw_df) * 100
            print(f"  Fraudulent transactions  : {fraud_count:,} ({fraud_pct:.1f}%)")

        if "alert_id" in self.raw_df.columns:
            alerts    = self.raw_df["alert_id"].notna().sum()
            alert_pct = alerts / len(self.raw_df) * 100
            print(f"  Transactions with alerts : {alerts:,} ({alert_pct:.1f}%)")

        if "credit_score" in self.raw_df.columns:
            avg_score = self.raw_df["credit_score"].mean()
            print(f"  Avg customer credit score: {avg_score:.0f}")

        print()
        print("  NEXT STEP: Copy data/raw-data.csv to Module 05 and run:")
        print("    python module-05-data-engineering-and-etl/run.py")
        print("=" * 60)

    # ================================================================
    # PRIVATE METHOD — synthetic data fallback
    # ================================================================

    @staticmethod
    def _synthetic_raw_data(n: int = 300) -> pd.DataFrame:
        """
        Generate synthetic banking data matching the extraction output.

        Column names exactly match OUTPUT_COLUMNS.
        Seeds ensure reproducibility — same seed = same data every run.

        Args:
            n   number of rows to generate (default 300)

        Returns:
            pd.DataFrame with n rows and 43 columns
        """
        import random
        random.seed(42)

        segments       = ["Retail", "Premium", "Corporate", "Student"]
        account_types  = ["Checking", "Savings", "Business", "Investment"]
        txn_types      = ["Purchase", "Transfer", "Withdrawal",
                          "Deposit", "Payment", "Refund"]
        channels       = ["ATM", "Online", "Mobile", "Branch", "POS"]
        txn_statuses   = ["Completed", "Pending", "Failed", "Reversed"]
        acct_statuses  = ["Active", "Frozen", "Closed", "Active", "Active"]
        merch_cats     = ["Retail", "Food & Dining", "Travel",
                          "Entertainment", "Healthcare", "Utilities",
                          "Financial Services"]
        loan_types     = ["Personal", "Mortgage", "Auto", "Business", "Student"]
        risk_grades    = ["A", "B", "C", "D", "E"]
        loan_statuses  = ["Active", "Paid Off", "Delinquent", "Defaulted"]
        alert_types    = ["Unusual Activity", "High Value",
                          "Geographic Anomaly", "Velocity Check"]
        severities     = ["Low", "Medium", "High", "Critical"]
        alert_statuses = ["Open", "Investigating", "Resolved", "Dismissed"]
        currencies     = ["USD", "EUR", "GBP", "USD", "USD"]
        cities         = ["New York", "London", "Accra", "Lagos",
                          "Nairobi", "Dubai", None]
        first_names    = ["Alice", "Bob", "Carol", "David", "Eve",
                          "Frank", "Grace", "Henry", "Iris", "Jack"]
        last_names     = ["Smith", "Johnson", "Williams", "Brown",
                          "Jones", "Garcia", "Miller", "Davis"]
        branches       = ["Main Branch", "Downtown", "Westside",
                          "Airport", "Online"]
        merchants      = ["Amazon", "Walmart", "Uber", "Netflix",
                          "Starbucks", "Shell", "Apple Store",
                          "Delta Airlines", None]

        rows = []
        for i in range(1, n + 1):
            customer_id = random.randint(1, 80)
            account_id  = random.randint(1, 100)
            amount      = round(random.uniform(1.0, 8000.0), 2)
            is_fraud    = random.random() < 0.06          # 6% fraud rate
            has_loan    = random.random() > 0.45          # 55% have a loan
            has_alert   = is_fraud or (random.random() < 0.04)
            balance_bef = round(random.uniform(500, 50000), 2)
            balance_aft = round(balance_bef - amount if random.random() > 0.3
                                else balance_bef + amount, 2)
            year        = random.randint(2022, 2024)
            month       = random.randint(1, 12)
            day         = random.randint(1, 28)
            txn_date    = f"{year}-{month:02d}-{day:02d}"
            loan_principal   = round(random.uniform(5000, 200000), 2) if has_loan else None
            loan_outstanding = round(loan_principal * random.uniform(0.1, 0.95), 2) if has_loan else None

            rows.append({
                # transactions
                "transaction_id":       i,
                "account_id":           account_id,
                "customer_id":          customer_id,
                "transaction_date":     txn_date,
                "transaction_time":     f"{random.randint(0,23):02d}:{random.randint(0,59):02d}",
                "amount":               amount,
                "transaction_type":     random.choice(txn_types),
                "merchant_name":        random.choice(merchants),
                "merchant_category":    random.choice(merch_cats),
                "channel":              random.choice(channels),
                "transaction_status":   random.choice(txn_statuses),
                "is_fraud":             is_fraud,
                "balance_after":        balance_aft,
                # customers
                "first_name":           random.choice(first_names),
                "last_name":            random.choice(last_names),
                "email":                f"customer{customer_id}@bank.demo",
                "city":                 random.choice(cities),
                "date_of_birth":        f"{random.randint(1950, 2000)}-{random.randint(1,12):02d}-01",
                "credit_score":         random.randint(300, 850),
                "customer_since":       f"20{random.randint(5,20):02d}-01-01",
                "segment":              random.choice(segments),
                # accounts
                "account_type":         random.choice(account_types),
                "account_number":       f"ACC{account_id:08d}",
                "balance":              round(random.uniform(100, 100000), 2),
                "currency":             random.choice(currencies),
                "opened_date":          f"20{random.randint(5,20):02d}-06-01",
                "account_status":       random.choice(acct_statuses),
                "account_interest_rate":round(random.uniform(0.001, 0.08), 4),
                # loans (LEFT JOIN — ~45% NULL)
                "loan_id":              i + 1000 if has_loan else None,
                "loan_type":            random.choice(loan_types)    if has_loan else None,
                "principal":            loan_principal,
                "loan_interest_rate":   round(random.uniform(0.02, 0.18), 4) if has_loan else None,
                "term_months":          random.choice([12, 24, 36, 60, 120, 240]) if has_loan else None,
                "monthly_payment":      round(loan_principal / random.randint(12, 240), 2) if has_loan else None,
                "loan_outstanding_balance": loan_outstanding,
                "loan_status":          random.choice(loan_statuses) if has_loan else None,
                "risk_grade":           random.choice(risk_grades)   if has_loan else None,
                # fraud_alerts (LEFT JOIN — only fraud txns + small extra %)
                "alert_id":             i + 5000 if has_alert else None,
                "alert_date":           txn_date  if has_alert else None,
                "alert_type":           random.choice(alert_types)    if has_alert else None,
                "alert_severity":       random.choice(severities)     if has_alert else None,
                "alert_status":         random.choice(alert_statuses) if has_alert else None,
                "amount_at_risk":       amount if has_alert else None,
            })

        return pd.DataFrame(rows)

    # ================================================================
    # DUNDER METHODS
    # ================================================================

    def __str__(self) -> str:
        return f"DataExtractor(schema={self.schema!r}, status={self._status!r})"

    def __repr__(self) -> str:
        return f"DataExtractor(schema={self.schema!r})"