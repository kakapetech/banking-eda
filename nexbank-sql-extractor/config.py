# ================================================================
# config.py — P05 Banking SQL Configuration
# ================================================================
# The Darko Method 2026
#
# This file reads settings from the .env file.
# It never contains passwords or connection strings directly.
#
# WHAT THIS FILE PROVIDES TO THE REST OF THE PIPELINE:
#   SCHEMA         — 'banking' (the PostgreSQL schema name)
#   PROJECT_ROOT   — absolute path to the project root folder
#   DATA_DIR       — absolute path to the data/ folder
#   SQL_DIR        — absolute path to the sql/ folder
#   RAW_DATA_PATH  — full path to data/raw-data.csv
#   DB_URL         — Supabase connection string (from .env only)
#   engine         — SQLAlchemy connection pool (None if DB unavailable)
#   DB_AVAILABLE   — True if the database is reachable, False otherwise
#   logger         — pre-configured Python Logger for the whole pipeline
#
# REAL BANKING SCHEMA TABLES AND COLUMNS:
#   banking.customers     — customer_id, first_name, last_name, email,
#                           phone, date_of_birth, city, credit_score,
#                           customer_since, segment, is_active
#   banking.accounts      — account_id, customer_id, account_type,
#                           account_number, balance, currency,
#                           opened_date, status, branch, interest_rate
#   banking.transactions  — transaction_id, account_id, customer_id,
#                           transaction_date, transaction_time, amount,
#                           transaction_type, merchant_name,
#                           merchant_category, channel, status,
#                           is_fraud, balance_after
#   banking.loans         — loan_id, customer_id, loan_type, principal,
#                           interest_rate, term_months, monthly_payment,
#                           disbursed_date, outstanding_balance,
#                           status, risk_grade
#   banking.fraud_alerts  — alert_id, transaction_id, customer_id,
#                           alert_date, alert_type, severity, status,
#                           amount_at_risk
#
# JOIN STRUCTURE (transactions is the anchor table):
#   transactions
#     INNER JOIN customers  ON transactions.customer_id = customers.customer_id
#     INNER JOIN accounts   ON transactions.account_id  = accounts.account_id
#     LEFT  JOIN loans      ON transactions.customer_id = loans.customer_id
#     LEFT  JOIN fraud_alerts ON transactions.transaction_id = fraud_alerts.transaction_id
#
# PIPELINE POSITION:
#   This project (P05) extracts raw-data.csv from the banking schema.
#   raw-data.csv feeds into Module 05 ETL.
# ================================================================

import os, pathlib, logging
from dotenv import load_dotenv

# Load all variables from .env into the environment
load_dotenv()

# ── Schema / identity ──────────────────────────────────────────
SCHEMA         = os.getenv("SCHEMA",         "banking")
LEARNER_SCHEMA = os.getenv("LEARNER_SCHEMA", "learner_41")

# ── Paths ──────────────────────────────────────────────────────
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent
DATA_DIR     = PROJECT_ROOT / "data"
SQL_DIR      = PROJECT_ROOT / "sql"
DATA_DIR.mkdir(exist_ok=True)

RAW_DATA_PATH = DATA_DIR / "raw-data.csv"

# ── Database connection ────────────────────────────────────────
# DB_URL comes entirely from .env — no fallback with credentials here.
# If .env is missing or DB_URL is not set, DB_AVAILABLE will be False
# and the project will tell you clearly what to do.
#
# Set your .env like this:
#   DB_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.xxxx.supabase.co:5432/postgres
DB_URL = os.getenv("DB_URL", "")

try:
    from sqlalchemy import create_engine, text
    if not DB_URL:
        raise ValueError("DB_URL not set. Check your .env file.")
    engine = create_engine(
        DB_URL,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    DB_AVAILABLE = True
except Exception:
    engine       = None
    DB_AVAILABLE = False


# ── Logger ─────────────────────────────────────────────────────
def _setup_logger() -> logging.Logger:
    lgr = logging.getLogger("p05_banking")
    lgr.setLevel(logging.INFO)
    if not lgr.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        lgr.addHandler(h)
    return lgr

logger = _setup_logger()

if not DB_AVAILABLE:
    logger.warning(
        "Database not connected. "
        "Check your .env file — DB_URL must be set to your Supabase connection string."
    )