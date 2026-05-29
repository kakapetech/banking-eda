# ================================================================
# src/query_runner.py
# ================================================================
# The Darko Method 2026
#
# CONTEXT:
#   We wrote SQL in .sql files targeting the banking schema.
#   Now we need to EXECUTE those queries from Python and get back
#   pandas DataFrames we can work with in the rest of the pipeline.
#
# THE ANALOGY:
#   Think of SQLQueryRunner as a bank analyst pulling reports.
#   You hand it a request (a SQL query string).
#   It sends that request to the PostgreSQL database.
#   PostgreSQL retrieves the records.
#   SQLQueryRunner packages those records as a DataFrame.
#
# KEY pandas FUNCTION: pd.read_sql()
#   pd.read_sql(sql_string, engine) executes SQL and returns a DataFrame.
#   This is what powers every Python + database workflow.
#
# WHY A CLASS AND NOT JUST pd.read_sql() DIRECTLY?
#   The class adds:
#     - Error handling  (what if the query fails?)
#     - Logging         (track what ran and when)
#     - Timing          (how long did each query take in milliseconds?)
#     - Audit history   (self.history — every run recorded as a dict)
#     - File loading    (run SQL straight from .sql files via run_file)
#   These extras make it production-grade rather than just a script.
#
# REAL SCHEMA COLUMNS USED IN THIS FILE:
#   customers    : customer_id, first_name, last_name, email, phone,
#                  date_of_birth, city, credit_score, customer_since,
#                  segment, is_active
#   accounts     : account_id, customer_id, account_type, account_number,
#                  balance, currency, opened_date, status, branch,
#                  interest_rate
#   transactions : transaction_id, account_id, customer_id,
#                  transaction_date, transaction_time, amount,
#                  transaction_type, merchant_name, merchant_category,
#                  channel, status, is_fraud, balance_after
#   loans        : loan_id, customer_id, loan_type, principal,
#                  interest_rate, term_months, monthly_payment,
#                  disbursed_date, outstanding_balance, status, risk_grade
#   fraud_alerts : alert_id, transaction_id, customer_id, alert_date,
#                  alert_type, severity, status, amount_at_risk
# ================================================================

import sys, pathlib, time

# ── make project root importable from any working directory ────
_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from config import engine, DB_AVAILABLE, SQL_DIR, SCHEMA, logger


class SQLQueryRunner:
    """
    Executes SQL queries against the Supabase / PostgreSQL database.
    Returns results as pandas DataFrames.

    All queries target the 'banking' schema which contains:
        customers, accounts, transactions, loans, fraud_alerts

    Attributes
    ----------
    schema   str           the configured schema name ('banking')
    history  list[dict]    audit log of every query run this session
                           each entry: {sql_preview, rows, cols, duration_ms, status}
    """

    def __init__(self):
        self.schema  = SCHEMA
        self.history = []
        logger.info(f"SQLQueryRunner ready — schema: {self.schema} | db_available: {DB_AVAILABLE}")

    # ================================================================
    # LAYER 2 — CORE EXECUTION
    # All other methods delegate here. One implementation of all logic.
    # ================================================================

    def run(self, sql: str, params: dict = None) -> pd.DataFrame:
        """
        Execute a SQL query string and return results as a DataFrame.

        This is the single method that actually talks to the database.
        Every other method in this class delegates here — meaning all
        error handling, timing, logging, and audit recording happen
        in exactly ONE place.

        Args:
            sql     SQL query to execute. Use {schema} as a placeholder
                    for the schema name — it is substituted automatically.
                    e.g. 'SELECT * FROM {schema}.transactions LIMIT 10'
            params  optional dict for parameterised queries.

        Returns:
            pd.DataFrame — always. Empty DataFrame on failure, never None.
        """
        if not DB_AVAILABLE or engine is None:
            logger.warning("[SQL] Database not available — returning empty DataFrame.")
            return pd.DataFrame()

        sql = sql.replace("{schema}", self.schema)
        start_time = time.time()

        try:
            df = pd.read_sql(sql, engine, params=params)
            duration_ms = round((time.time() - start_time) * 1000, 1)

            self.history.append({
                "sql_preview": sql[:80].strip(),
                "rows":        len(df),
                "cols":        len(df.columns),
                "duration_ms": duration_ms,
                "status":      "success",
            })
            logger.info(
                f"[SQL] Query complete — "
                f"{len(df):,} rows x {len(df.columns)} cols | {duration_ms} ms"
            )
            return df

        except Exception as e:
            self.history.append({
                "sql_preview": sql[:80].strip(),
                "rows":        0,
                "cols":        0,
                "duration_ms": round((time.time() - start_time) * 1000, 1),
                "status":      f"error: {str(e)[:100]}",
            })
            logger.error(f"[SQL] Query failed: {e}")
            return pd.DataFrame()

    # ================================================================
    # LAYER 3 — CONVENIENCE WRAPPER
    # ================================================================

    def run_file(self, filename: str) -> pd.DataFrame:
        """
        Load a .sql file from the sql/ directory and execute it.

        Args:
            filename   e.g. "05_extract_raw_data.sql"

        Returns:
            pd.DataFrame with query results (empty DataFrame if not found).
        """
        sql_path = SQL_DIR / filename
        if not sql_path.exists():
            logger.error(f"[SQL] File not found: {sql_path}")
            return pd.DataFrame()
        logger.info(f"[SQL] Loading: {filename}")
        return self.run(sql_path.read_text(encoding="utf-8"))

    # ================================================================
    # LAYER 4 — DOMAIN KNOWLEDGE (demo methods)
    # Mirror the four SQL sections in 05_extract_raw_data.sql.
    # ================================================================

    def demo_basics(self) -> None:
        """
        Section 1 — Explore each table individually.
        Row counts and distinct categorical values across all five tables.
        """
        demos = [
            (
                "Row counts across all five tables",
                f"""
                SELECT 'customers'    AS table_name, COUNT(*) AS row_count
                FROM {self.schema}.customers
                UNION ALL
                SELECT 'accounts',    COUNT(*) FROM {self.schema}.accounts
                UNION ALL
                SELECT 'transactions',COUNT(*) FROM {self.schema}.transactions
                UNION ALL
                SELECT 'loans',       COUNT(*) FROM {self.schema}.loans
                UNION ALL
                SELECT 'fraud_alerts',COUNT(*) FROM {self.schema}.fraud_alerts
                """,
            ),
            (
                "Distinct account types",
                f"SELECT DISTINCT account_type FROM {self.schema}.accounts ORDER BY account_type",
            ),
            (
                "Distinct transaction types",
                f"SELECT DISTINCT transaction_type FROM {self.schema}.transactions ORDER BY transaction_type",
            ),
            (
                "Distinct transaction channels",
                f"SELECT DISTINCT channel FROM {self.schema}.transactions ORDER BY channel",
            ),
            (
                "Distinct customer segments",
                f"SELECT DISTINCT segment FROM {self.schema}.customers ORDER BY segment",
            ),
            (
                "Distinct loan types and risk grades",
                f"""
                SELECT DISTINCT loan_type, risk_grade
                FROM {self.schema}.loans
                ORDER BY loan_type, risk_grade
                """,
            ),
            (
                "Distinct fraud alert types and severities",
                f"""
                SELECT DISTINCT alert_type, severity
                FROM {self.schema}.fraud_alerts
                ORDER BY alert_type, severity
                """,
            ),
            (
                "Fraud rate overview",
                f"""
                SELECT
                    COUNT(*)                                    AS total_transactions,
                    COUNT(CASE WHEN is_fraud THEN 1 END)        AS fraud_transactions,
                    ROUND(
                        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
                        / NULLIF(COUNT(*), 0) * 100, 2
                    )                                           AS fraud_rate_pct
                FROM {self.schema}.transactions
                """,
            ),
        ]

        for title, sql in demos:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    def demo_aggregation(self) -> None:
        """
        Section 2 — Aggregations.
        Transaction volumes, fraud rates by channel and merchant category,
        loan portfolio summary, and average balance by account type.
        """
        queries = [
            (
                "Overall transaction summary",
                f"""
                SELECT
                    COUNT(*)                                    AS total_transactions,
                    SUM(amount)                                AS total_volume,
                    ROUND(AVG(amount)::NUMERIC, 2)             AS avg_transaction,
                    COUNT(CASE WHEN is_fraud THEN 1 END)        AS fraud_count,
                    ROUND(
                        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
                        / NULLIF(COUNT(*), 0) * 100, 2
                    )                                           AS fraud_rate_pct
                FROM {self.schema}.transactions
                """,
            ),
            (
                "Transaction volume and fraud rate by channel",
                f"""
                SELECT
                    channel,
                    COUNT(*)                                    AS total_transactions,
                    SUM(amount)                                AS total_volume,
                    COUNT(CASE WHEN is_fraud THEN 1 END)        AS fraud_count,
                    ROUND(
                        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
                        / NULLIF(COUNT(*), 0) * 100, 2
                    )                                           AS fraud_rate_pct
                FROM {self.schema}.transactions
                GROUP BY channel
                ORDER BY total_volume DESC
                """,
            ),
            (
                "Fraud rate by merchant category",
                f"""
                SELECT
                    merchant_category,
                    COUNT(*)                                    AS total_transactions,
                    SUM(amount)                                AS total_volume,
                    COUNT(CASE WHEN is_fraud THEN 1 END)        AS fraud_count,
                    ROUND(
                        COUNT(CASE WHEN is_fraud THEN 1 END)::NUMERIC
                        / NULLIF(COUNT(*), 0) * 100, 2
                    )                                           AS fraud_rate_pct
                FROM {self.schema}.transactions
                GROUP BY merchant_category
                ORDER BY fraud_rate_pct DESC
                """,
            ),
            (
                "Average balance and transaction count by account type",
                f"""
                SELECT
                    a.account_type,
                    COUNT(DISTINCT a.account_id)               AS total_accounts,
                    ROUND(AVG(a.balance)::NUMERIC, 2)          AS avg_balance,
                    SUM(a.balance)                             AS total_balance,
                    COUNT(t.transaction_id)                    AS total_transactions
                FROM {self.schema}.accounts a
                LEFT JOIN {self.schema}.transactions t ON a.account_id = t.account_id
                GROUP BY a.account_type
                ORDER BY total_balance DESC
                """,
            ),
            (
                "Loan portfolio summary by type and risk grade",
                f"""
                SELECT
                    loan_type,
                    risk_grade,
                    COUNT(*)                                    AS total_loans,
                    SUM(principal)                             AS total_principal,
                    SUM(outstanding_balance)                   AS total_outstanding,
                    ROUND(AVG(interest_rate * 100)::NUMERIC, 2) AS avg_interest_rate_pct
                FROM {self.schema}.loans
                GROUP BY loan_type, risk_grade
                ORDER BY loan_type, risk_grade
                """,
            ),
            (
                "Monthly transaction volume trend",
                f"""
                SELECT
                    DATE_TRUNC('month', transaction_date)      AS month,
                    COUNT(*)                                    AS total_transactions,
                    SUM(amount)                                AS total_volume,
                    COUNT(CASE WHEN is_fraud THEN 1 END)        AS fraud_count
                FROM {self.schema}.transactions
                GROUP BY month
                ORDER BY month
                """,
            ),
        ]

        for title, sql in queries:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    def demo_joins(self) -> None:
        """
        Section 3 — Joins.
        Transactions combined with customers, accounts, loans,
        and fraud_alerts into one unified view per transaction.
        """
        queries = [
            (
                "Transactions with customer and account details (top 15)",
                f"""
                SELECT
                    t.transaction_id,
                    t.transaction_date,
                    t.transaction_type,
                    t.amount,
                    t.channel,
                    t.is_fraud,
                    c.first_name,
                    c.last_name,
                    c.segment,
                    c.credit_score,
                    a.account_type,
                    a.balance
                FROM {self.schema}.transactions t
                JOIN {self.schema}.customers c ON t.customer_id = c.customer_id
                JOIN {self.schema}.accounts  a ON t.account_id  = a.account_id
                ORDER BY t.transaction_date DESC
                LIMIT 15
                """,
            ),
            (
                "Fraudulent transactions with alert details (top 10)",
                f"""
                SELECT
                    t.transaction_id,
                    t.transaction_date,
                    t.amount,
                    t.merchant_name,
                    t.merchant_category,
                    t.channel,
                    c.first_name || ' ' || c.last_name         AS customer_name,
                    c.segment,
                    c.credit_score,
                    fa.alert_type,
                    fa.severity,
                    fa.status                                   AS alert_status,
                    fa.amount_at_risk
                FROM {self.schema}.transactions t
                JOIN {self.schema}.customers c  ON t.customer_id     = c.customer_id
                LEFT JOIN {self.schema}.fraud_alerts fa ON t.transaction_id = fa.transaction_id
                WHERE t.is_fraud = TRUE
                ORDER BY t.transaction_date DESC
                LIMIT 10
                """,
            ),
            (
                "Full five-table join — one row per transaction (top 10)",
                f"""
                SELECT
                    t.transaction_id,
                    t.transaction_date,
                    t.amount,
                    t.transaction_type,
                    t.merchant_category,
                    t.channel,
                    t.is_fraud,
                    c.first_name,
                    c.last_name,
                    c.segment,
                    c.credit_score,
                    a.account_type,
                    a.balance                                   AS account_balance,
                    l.loan_type,
                    l.risk_grade,
                    l.outstanding_balance                       AS loan_outstanding,
                    fa.alert_type,
                    fa.severity                                 AS alert_severity
                FROM {self.schema}.transactions t
                JOIN {self.schema}.customers c   ON t.customer_id     = c.customer_id
                JOIN {self.schema}.accounts a    ON t.account_id      = a.account_id
                LEFT JOIN {self.schema}.loans l  ON t.customer_id     = l.customer_id
                LEFT JOIN {self.schema}.fraud_alerts fa ON t.transaction_id = fa.transaction_id
                ORDER BY t.transaction_date DESC
                LIMIT 10
                """,
            ),
            (
                "Customers with both a loan and recent fraud alert",
                f"""
                SELECT DISTINCT
                    c.customer_id,
                    c.first_name || ' ' || c.last_name         AS customer_name,
                    c.segment,
                    c.credit_score,
                    l.loan_type,
                    l.risk_grade,
                    l.outstanding_balance,
                    fa.severity                                 AS alert_severity,
                    fa.amount_at_risk
                FROM {self.schema}.customers c
                JOIN {self.schema}.loans l          ON c.customer_id     = l.customer_id
                JOIN {self.schema}.transactions t   ON c.customer_id     = t.customer_id
                JOIN {self.schema}.fraud_alerts fa  ON t.transaction_id  = fa.transaction_id
                ORDER BY l.outstanding_balance DESC
                LIMIT 10
                """,
            ),
        ]

        for title, sql in queries:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    def demo_window_functions(self) -> None:
        """
        Section 4 — CTEs and window functions.
        Customer risk profiles (CTE), ranking customers by transaction
        volume, running balance over time, and fraud detection patterns.
        """
        queries = [
            (
                "CTE — Customer risk profile summary",
                f"""
                WITH customer_risk AS (
                    SELECT
                        c.customer_id,
                        c.first_name || ' ' || c.last_name     AS customer_name,
                        c.segment,
                        c.credit_score,
                        c.city,
                        COUNT(t.transaction_id)                AS total_transactions,
                        SUM(t.amount)                          AS total_volume,
                        COUNT(CASE WHEN t.is_fraud THEN 1 END)  AS fraud_count,
                        ROUND(AVG(t.amount)::NUMERIC, 2)       AS avg_transaction,
                        COUNT(fa.alert_id)                     AS total_alerts
                    FROM {self.schema}.customers c
                    JOIN {self.schema}.transactions t ON c.customer_id = t.customer_id
                    LEFT JOIN {self.schema}.fraud_alerts fa ON t.transaction_id = fa.transaction_id
                    GROUP BY
                        c.customer_id, c.first_name, c.last_name,
                        c.segment, c.credit_score, c.city
                )
                SELECT * FROM customer_risk ORDER BY fraud_count DESC LIMIT 10
                """,
            ),
            (
                "Window function — Rank customers by transaction volume",
                f"""
                SELECT
                    c.customer_id,
                    c.first_name || ' ' || c.last_name         AS customer_name,
                    c.segment,
                    SUM(t.amount)                              AS total_volume,
                    RANK() OVER (
                        ORDER BY SUM(t.amount) DESC
                    )                                           AS volume_rank
                FROM {self.schema}.customers c
                JOIN {self.schema}.transactions t ON c.customer_id = t.customer_id
                GROUP BY c.customer_id, c.first_name, c.last_name, c.segment
                ORDER BY volume_rank
                LIMIT 20
                """,
            ),
            (
                "Window function — Rank customers by volume within each segment",
                f"""
                SELECT
                    c.first_name || ' ' || c.last_name         AS customer_name,
                    c.segment,
                    SUM(t.amount)                              AS total_volume,
                    RANK() OVER (
                        PARTITION BY c.segment
                        ORDER BY SUM(t.amount) DESC
                    )                                           AS rank_in_segment
                FROM {self.schema}.customers c
                JOIN {self.schema}.transactions t ON c.customer_id = t.customer_id
                GROUP BY c.customer_id, c.first_name, c.last_name, c.segment
                ORDER BY c.segment, rank_in_segment
                LIMIT 20
                """,
            ),
            (
                "Window function — Running balance after each transaction",
                f"""
                SELECT
                    transaction_id,
                    transaction_date,
                    amount,
                    transaction_type,
                    balance_after,
                    LAG(balance_after) OVER (
                        PARTITION BY account_id ORDER BY transaction_date, transaction_time
                    )                                           AS prev_balance
                FROM {self.schema}.transactions
                ORDER BY account_id, transaction_date, transaction_time
                LIMIT 20
                """,
            ),
            (
                "CTE + Window — Month-over-month transaction volume growth",
                f"""
                WITH monthly_volume AS (
                    SELECT
                        DATE_TRUNC('month', transaction_date)  AS month,
                        SUM(amount)                            AS volume
                    FROM {self.schema}.transactions
                    GROUP BY month
                )
                SELECT
                    month,
                    volume,
                    LAG(volume) OVER (ORDER BY month)          AS prev_month_volume,
                    ROUND(
                        (volume - LAG(volume) OVER (ORDER BY month))
                        / NULLIF(LAG(volume) OVER (ORDER BY month), 0) * 100, 2
                    )                                           AS pct_growth
                FROM monthly_volume
                ORDER BY month
                """,
            ),
        ]

        for title, sql in queries:
            print(f"\n── {title}:")
            df = self.run(sql)
            if not df.empty:
                print(df.to_string(index=False))

    # ================================================================
    # DUNDER METHODS
    # ================================================================

    def __str__(self) -> str:
        return (
            f"SQLQueryRunner("
            f"schema={self.schema!r}, "
            f"queries_run={len(self.history)})"
        )

    def __repr__(self) -> str:
        return f"SQLQueryRunner(schema={self.schema!r})"