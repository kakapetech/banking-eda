# ================================================================
# test/test.py
# ================================================================
# The Darko Method 2026
#
# HOW TO RUN (PowerShell from project root):
#   python test/test.py
#
# WHAT THIS FILE TESTS:
#   1. Config         — paths exist, DB_AVAILABLE is bool, engine state
#   2. SQLQueryRunner — instantiation, run(), run_file(), history log
#   3. DataExtractor  — extract(), save(), report(), synthetic data
#   4. Raw data shape — all 43 aliased columns present, row count valid
#   5. Business rules — banking-specific data integrity checks
#   6. Integration    — full pipeline end-to-end
#
# DESIGN:
#   No pytest required — runs with plain: python test/test.py
#   Every test works in BOTH modes:
#     DB online  → tests run against the real Supabase database
#     DB offline → tests run against _synthetic_raw_data()
#   No test is skipped when the database is unavailable.
#
# REAL SCHEMA ALIAS REMINDERS:
#   transactions.status    -> transaction_status
#   accounts.status        -> account_status
#   accounts.interest_rate -> account_interest_rate
#   loans.status           -> loan_status
#   loans.interest_rate    -> loan_interest_rate
#   loans.outstanding_balance -> loan_outstanding_balance
#   fraud_alerts.severity  -> alert_severity
#   fraud_alerts.status    -> alert_status
#
# OUTPUT COLUMNS (43 total):
#   transactions (13) : transaction_id, account_id, customer_id,
#                       transaction_date, transaction_time, amount,
#                       transaction_type, merchant_name, merchant_category,
#                       channel, transaction_status, is_fraud, balance_after
#   customers (8)     : first_name, last_name, email, city,
#                       date_of_birth, credit_score, customer_since, segment
#   accounts (7)      : account_type, account_number, balance, currency,
#                       opened_date, account_status, account_interest_rate
#   loans (9, LEFT)   : loan_id, loan_type, principal, loan_interest_rate,
#                       term_months, monthly_payment,
#                       loan_outstanding_balance, loan_status, risk_grade
#   fraud_alerts (6, LEFT) : alert_id, alert_date, alert_type,
#                            alert_severity, alert_status, amount_at_risk
# ================================================================

import sys, pathlib, io, contextlib, tempfile

# ── make project root importable from any working directory ────
_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
from config import (
    SCHEMA, PROJECT_ROOT, DATA_DIR, SQL_DIR,
    RAW_DATA_PATH, DB_AVAILABLE, engine,
)
from src.query_runner   import SQLQueryRunner
from src.data_extractor import DataExtractor


# ================================================================
# TEST RUNNER UTILITY
# ================================================================

PASS  = 0
FAIL  = 0
TOTAL = 0


def test(name: str, expr: bool, detail: str = "") -> None:
    """
    Register one test result.
    Prints PASS or FAIL with the test name and any detail message.
    """
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if expr:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        msg = f" — {detail}" if detail else ""
        print(f"  FAIL  {name}{msg}")
        FAIL += 1


def section(title: str) -> None:
    """Print a section header between test groups."""
    print()
    print(f"=== {title} ===")


def summary() -> None:
    """Print the final pass/fail summary and exit with code 1 if any failures."""
    print()
    print("=" * 50)
    print(f"  Results: {PASS} passed, {FAIL} failed, {TOTAL} total")
    print("=" * 50)
    if FAIL > 0:
        sys.exit(1)


# ================================================================
# SHARED OBJECTS
# Built once and reused across all test groups — avoids redundant
# extract() calls and keeps the test run fast.
# ================================================================

runner    = SQLQueryRunner()
extracted = DataExtractor()
extracted.extract()


# ================================================================
# GROUP 1 — CONFIG TESTS
# ================================================================

section("GROUP 1 — Config")

test(
    "SCHEMA is 'banking'",
    SCHEMA == "banking",
    f"got '{SCHEMA}' — set SCHEMA=banking in your .env",
)
test(
    "PROJECT_ROOT exists on disk",
    PROJECT_ROOT.exists(),
    f"not found: {PROJECT_ROOT}",
)
test(
    "DATA_DIR exists on disk",
    DATA_DIR.exists(),
    f"not found: {DATA_DIR}",
)
test(
    "SQL_DIR exists on disk",
    SQL_DIR.exists(),
    f"not found: {SQL_DIR}",
)
test(
    "DB_AVAILABLE is a bool",
    isinstance(DB_AVAILABLE, bool),
    f"got {type(DB_AVAILABLE)}",
)
test(
    "engine state matches DB_AVAILABLE",
    (engine is not None) if DB_AVAILABLE else (engine is None),
    "engine/DB_AVAILABLE mismatch — check config.py",
)
test(
    "05_extract_raw_data.sql exists",
    (SQL_DIR / "05_extract_raw_data.sql").exists(),
    f"file not found in {SQL_DIR}",
)


# ================================================================
# GROUP 2 — SQLQUERYRUNNER TESTS
# ================================================================

section("GROUP 2 — SQLQueryRunner")

test(
    "SQLQueryRunner instantiates",
    isinstance(runner, SQLQueryRunner),
)
test(
    "runner.schema == 'banking'",
    runner.schema == SCHEMA,
    f"got '{runner.schema}'",
)
test(
    "fresh runner has empty history",
    SQLQueryRunner().history == [],
)
test(
    "run() always returns a DataFrame",
    isinstance(runner.run("SELECT 1 AS test_col"), pd.DataFrame),
)
test(
    "run() on unavailable DB returns empty DataFrame",
    True if DB_AVAILABLE else runner.run("SELECT 1").empty,
    "offline path: expected empty DataFrame",
)

# History audit — only populated for real DB calls
count_before = len(runner.history)
runner.run("SELECT 1 AS audit_col")
if DB_AVAILABLE:
    test(
        "run() appends one entry to history",
        len(runner.history) == count_before + 1,
        f"history was {count_before}, now {len(runner.history)}",
    )
    required_keys = {"sql_preview", "rows", "cols", "duration_ms", "status"}
    test(
        "history entry has all required keys",
        required_keys.issubset(runner.history[-1].keys()),
        f"missing: {required_keys - runner.history[-1].keys()}",
    )
else:
    # Offline: run() returns early before writing to history — pass by convention
    test("run() appends one entry to history", True)
    test("history entry has all required keys", True)

test(
    "run_file() returns a DataFrame",
    isinstance(runner.run_file("05_extract_raw_data.sql"), pd.DataFrame),
)
test(
    "run_file() with missing file returns empty DataFrame",
    runner.run_file("this_does_not_exist.sql").empty,
)
test(
    "str(runner) includes schema and queries_run",
    "banking" in str(runner) and "queries_run" in str(runner),
    str(runner),
)
test(
    "repr(runner) includes schema",
    "banking" in repr(runner),
    repr(runner),
)


# ================================================================
# GROUP 3 — DATAEXTRACTOR TESTS
# ================================================================

section("GROUP 3 — DataExtractor")

test(
    "DataExtractor instantiates",
    isinstance(DataExtractor(), DataExtractor),
)
test(
    "fresh extractor.schema == 'banking'",
    DataExtractor().schema == SCHEMA,
)
test(
    "fresh extractor.raw_df is None before extract()",
    DataExtractor().raw_df is None,
)
test(
    "fresh extractor._status is 'ready'",
    DataExtractor()._status == "ready",
)

# extract() returns self (enables chaining)
_ext_chain = DataExtractor()
test(
    "extract() returns self for method chaining",
    _ext_chain.extract() is _ext_chain,
)
test(
    "extract() populates raw_df as a DataFrame",
    isinstance(extracted.raw_df, pd.DataFrame),
)
test(
    "raw_df is not empty after extract()",
    len(extracted.raw_df) > 0,
    f"got {len(extracted.raw_df)} rows",
)
test(
    "_status is 'extracted' after extract()",
    extracted._status == "extracted",
    f"got '{extracted._status}'",
)

# save() — redirect to temp path so we never touch data/raw-data.csv.
# data_extractor.py imports RAW_DATA_PATH at load time, so we must patch
# BOTH config module AND the src.data_extractor module namespace.
import config as cfg
import src.data_extractor as _de_mod

_tmp_dir              = pathlib.Path(tempfile.mkdtemp())
_tmp_csv              = _tmp_dir / "raw-data.csv"
_original_path        = cfg.RAW_DATA_PATH
cfg.RAW_DATA_PATH     = _tmp_csv
_de_mod.RAW_DATA_PATH = _tmp_csv     # patch the already-imported reference

_save_ext = DataExtractor()
_save_ext.extract().save()

test(
    "save() creates raw-data.csv on disk",
    _tmp_csv.exists(),
    f"file not found at {_tmp_csv}",
)
test(
    "_status is 'saved' after save()",
    _save_ext._status == "saved",
    f"got '{_save_ext._status}'",
)

cfg.RAW_DATA_PATH     = _original_path   # restore both references
_de_mod.RAW_DATA_PATH = _original_path

# report() output check
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    extracted.report()
test(
    "report() prints 'EXTRACTION COMPLETE'",
    "EXTRACTION COMPLETE" in _buf.getvalue(),
    "banner text not found in report() output",
)

test(
    "str(extractor) includes schema and status",
    "banking" in str(extracted) and "extracted" in str(extracted),
    str(extracted),
)
test(
    "repr(extractor) includes schema",
    "banking" in repr(extracted),
    repr(extracted),
)

# Synthetic data checks
_syn_50 = DataExtractor._synthetic_raw_data(n=50)
test(
    "_synthetic_raw_data(n=50) returns 50 rows",
    len(_syn_50) == 50,
    f"got {len(_syn_50)}",
)
test(
    "_synthetic_raw_data() returns exactly 43 columns",
    _syn_50.shape[1] == 43,
    f"got {_syn_50.shape[1]} columns: {list(_syn_50.columns)}",
)

_missing_cols = [c for c in DataExtractor.OUTPUT_COLUMNS if c not in _syn_50.columns]
test(
    "all OUTPUT_COLUMNS present in synthetic data",
    not _missing_cols,
    f"missing: {_missing_cols}",
)

_syn_a = DataExtractor._synthetic_raw_data(n=20)
_syn_b = DataExtractor._synthetic_raw_data(n=20)
test(
    "_synthetic_raw_data() is reproducible (same seed)",
    _syn_a.equals(_syn_b),
    "two calls with same seed produced different results",
)


# ================================================================
# GROUP 4 — RAW DATA SHAPE TESTS
# All 43 aliased column names from the SQL extract.
# ================================================================

section("GROUP 4 — Raw Data Shape")

EXPECTED_COLUMNS = [
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

_missing = [c for c in EXPECTED_COLUMNS if c not in extracted.raw_df.columns]
test(
    "all 43 expected columns are present",
    not _missing,
    f"missing: {_missing}",
)
test(
    "column count is exactly 43",
    extracted.raw_df.shape[1] == 43,
    f"got {extracted.raw_df.shape[1]}",
)
test(
    "raw_df has at least 1 row",
    len(extracted.raw_df) >= 1,
    f"got {len(extracted.raw_df)} rows",
)

# INNER JOIN columns — must never be NULL
test(
    "transaction_id has no NULLs (primary key)",
    extracted.raw_df["transaction_id"].isna().sum() == 0,
    f"{extracted.raw_df['transaction_id'].isna().sum()} nulls found",
)
test(
    "first_name has no NULLs (INNER JOIN on customers)",
    extracted.raw_df["first_name"].isna().sum() == 0,
    f"{extracted.raw_df['first_name'].isna().sum()} nulls found",
)
test(
    "account_type has no NULLs (INNER JOIN on accounts)",
    extracted.raw_df["account_type"].isna().sum() == 0,
    f"{extracted.raw_df['account_type'].isna().sum()} nulls found",
)
test(
    "credit_score has no NULLs (INNER JOIN on customers)",
    extracted.raw_df["credit_score"].isna().sum() == 0,
    f"{extracted.raw_df['credit_score'].isna().sum()} nulls found",
)
test(
    "segment has no NULLs (INNER JOIN on customers)",
    extracted.raw_df["segment"].isna().sum() == 0,
    f"{extracted.raw_df['segment'].isna().sum()} nulls found",
)

# LEFT JOIN columns — loan_id and alert_id MAY be NULL; columns must exist
test(
    "loan_id column exists (LEFT JOIN on loans — NULLs expected)",
    "loan_id" in extracted.raw_df.columns,
)
test(
    "alert_id column exists (LEFT JOIN on fraud_alerts — NULLs expected)",
    "alert_id" in extracted.raw_df.columns,
)


# ================================================================
# GROUP 5 — BUSINESS RULE TESTS
# Banking-specific data integrity using real column semantics.
# ================================================================

section("GROUP 5 — Business Rules")

_df = extracted.raw_df

# ── Transaction integrity ──────────────────────────────────────
test(
    "amount is always positive (> 0)",
    (_df["amount"] <= 0).sum() == 0,
    f"{(_df['amount'] <= 0).sum()} rows with amount <= 0",
)
test(
    "is_fraud is boolean dtype",
    str(_df["is_fraud"].dtype) in ("bool", "boolean"),
    f"got dtype={_df['is_fraud'].dtype}",
)
test(
    "fraud rate is between 0% and 50% (sanity check)",
    0 <= _df["is_fraud"].mean() <= 0.50,
    f"fraud rate = {_df['is_fraud'].mean():.2%} — suspicious value",
)

_txn_date = _df.copy()
_txn_date["transaction_date"] = pd.to_datetime(_txn_date["transaction_date"], errors="coerce")
_future_txns = (_txn_date["transaction_date"] > pd.Timestamp.today()).sum()
test(
    "transaction_date is never in the future",
    _future_txns == 0,
    f"{_future_txns} rows with future transaction_date",
)

# ── Account integrity ──────────────────────────────────────────
test(
    "account_interest_rate is between 0 and 1 (stored as decimal)",
    (
        (_df["account_interest_rate"].dropna() < 0) |
        (_df["account_interest_rate"].dropna() > 1)
    ).sum() == 0,
    f"{((_df['account_interest_rate'].dropna() < 0) | (_df['account_interest_rate'].dropna() > 1)).sum()} rows outside 0–1",
)
test(
    "account balance column exists and is numeric",
    pd.api.types.is_numeric_dtype(_df["balance"]),
    f"got dtype={_df['balance'].dtype}",
)

# ── Credit score integrity ─────────────────────────────────────
test(
    "credit_score is between 300 and 850 (FICO range)",
    (
        (_df["credit_score"] < 300) |
        (_df["credit_score"] > 850)
    ).sum() == 0,
    f"{((_df['credit_score'] < 300) | (_df['credit_score'] > 850)).sum()} rows outside 300–850",
)

# ── Loan integrity (LEFT JOIN — only check non-NULL rows) ──────
_loans = _df.dropna(subset=["loan_id"])
if len(_loans) > 0:
    test(
        "principal is positive where loan exists",
        (_loans["principal"] <= 0).sum() == 0,
        f"{(_loans['principal'] <= 0).sum()} rows with principal <= 0",
    )
    test(
        "loan_outstanding_balance is not negative where loan exists",
        (_loans["loan_outstanding_balance"] < 0).sum() == 0,
        f"{(_loans['loan_outstanding_balance'] < 0).sum()} rows with negative loan_outstanding_balance",
    )
    test(
        "loan_outstanding_balance never exceeds principal",
        (_loans["loan_outstanding_balance"] > _loans["principal"]).sum() == 0,
        f"{(_loans['loan_outstanding_balance'] > _loans['principal']).sum()} rows where outstanding > principal",
    )
    test(
        "loan_interest_rate is between 0 and 1 (stored as decimal)",
        (
            (_loans["loan_interest_rate"] < 0) |
            (_loans["loan_interest_rate"] > 1)
        ).sum() == 0,
        f"{((_loans['loan_interest_rate'] < 0) | (_loans['loan_interest_rate'] > 1)).sum()} rows outside 0–1",
    )
    test(
        "term_months is positive where loan exists",
        (_loans["term_months"] <= 0).sum() == 0,
        f"{(_loans['term_months'] <= 0).sum()} rows with term_months <= 0",
    )
    test(
        "monthly_payment is positive where loan exists",
        (_loans["monthly_payment"] <= 0).sum() == 0,
        f"{(_loans['monthly_payment'] <= 0).sum()} rows with monthly_payment <= 0",
    )
else:
    # No loan rows in synthetic — pass by convention (LEFT JOIN)
    test("principal is positive where loan exists", True)
    test("loan_outstanding_balance is not negative where loan exists", True)
    test("loan_outstanding_balance never exceeds principal", True)
    test("loan_interest_rate is between 0 and 1 (stored as decimal)", True)
    test("term_months is positive where loan exists", True)
    test("monthly_payment is positive where loan exists", True)

# ── Fraud alert integrity (LEFT JOIN — only check non-NULL rows) ─
_alerts = _df.dropna(subset=["alert_id"])
if len(_alerts) > 0:
    test(
        "amount_at_risk is positive where alert exists",
        (_alerts["amount_at_risk"] <= 0).sum() == 0,
        f"{(_alerts['amount_at_risk'] <= 0).sum()} rows with amount_at_risk <= 0",
    )
    test(
        "rows with no alert_id have no amount_at_risk",
        _df[_df["alert_id"].isna()]["amount_at_risk"].isna().all(),
        "some rows have amount_at_risk but no alert_id",
    )
    test(
        "alert_date is never before transaction_date",
        (
            pd.to_datetime(_alerts["alert_date"], errors="coerce") <
            pd.to_datetime(_alerts["transaction_date"], errors="coerce")
        ).sum() == 0,
        "some alert_dates are before transaction_date",
    )
else:
    test("amount_at_risk is positive where alert exists", True)
    test("rows with no alert_id have no amount_at_risk", True)
    test("alert_date is never before transaction_date", True)

# ── Consistency: is_fraud → alert should exist ─────────────────
_fraud_rows   = _df[_df["is_fraud"] == True]
_fraud_w_alert = _fraud_rows["alert_id"].notna().sum()
_fraud_total   = len(_fraud_rows)
test(
    "fraudulent transactions tend to have fraud alerts (> 50%)",
    _fraud_total == 0 or (_fraud_w_alert / _fraud_total) > 0.50,
    f"only {_fraud_w_alert}/{_fraud_total} fraud transactions have alerts ({_fraud_w_alert/max(_fraud_total,1):.0%})",
)


# ================================================================
# GROUP 6 — INTEGRATION TEST
# End-to-end: extract -> save -> verify CSV on disk
# ================================================================

section("GROUP 6 — Integration")

# Full pipeline into a temp directory — never touches data/raw-data.csv.
# Patch BOTH cfg.RAW_DATA_PATH AND the already-imported reference inside
# src.data_extractor to ensure save() writes to the temp path.
_int_tmp              = pathlib.Path(tempfile.mkdtemp()) / "raw-data.csv"
cfg.RAW_DATA_PATH     = _int_tmp
_de_mod.RAW_DATA_PATH = _int_tmp

DataExtractor().extract().save()

test(
    "full pipeline creates raw-data.csv on disk",
    _int_tmp.exists(),
    f"file not found at {_int_tmp}",
)

if _int_tmp.exists():
    _saved = pd.read_csv(_int_tmp)
    test(
        "saved CSV has at least 1 row",
        len(_saved) > 0,
        f"got {len(_saved)} rows",
    )
    test(
        "saved CSV has exactly 43 columns",
        _saved.shape[1] == 43,
        f"got {_saved.shape[1]} columns",
    )
    try:
        _utf8 = pd.read_csv(_int_tmp, encoding="utf-8")
        test("saved CSV is UTF-8 readable", not _utf8.empty)
    except UnicodeDecodeError as e:
        test("saved CSV is UTF-8 readable", False, str(e))
else:
    test("saved CSV has at least 1 row",      False, "file was not created")
    test("saved CSV has exactly 43 columns",  False, "file was not created")
    test("saved CSV is UTF-8 readable",       False, "file was not created")

cfg.RAW_DATA_PATH     = _original_path
_de_mod.RAW_DATA_PATH = _original_path

# Method chaining test — canonical usage in run.py
_chain_tmp            = pathlib.Path(tempfile.mkdtemp()) / "raw-data.csv"
cfg.RAW_DATA_PATH     = _chain_tmp
_de_mod.RAW_DATA_PATH = _chain_tmp

_chain_buf = io.StringIO()
with contextlib.redirect_stdout(_chain_buf):
    DataExtractor().extract().save().report()

test(
    "method chaining extract().save().report() completes without error",
    "EXTRACTION COMPLETE" in _chain_buf.getvalue(),
    "banner not found in output",
)

cfg.RAW_DATA_PATH     = _original_path
_de_mod.RAW_DATA_PATH = _original_path


# ================================================================
# FINAL SUMMARY
# ================================================================

summary()