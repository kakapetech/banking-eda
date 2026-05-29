# ================================================================
# run.py — P05 Banking SQL | Entry Point
# ================================================================
# The Darko Method 2026
#
# python run.py
#
# WHAT HAPPENS:
#   1. Demo SQL concepts live in the terminal:
#        basics -> aggregation -> joins -> window functions
#   2. Run the full extraction query (05_extract_raw_data.sql)
#      joining banking.transactions + customers + accounts
#      + loans + fraud_alerts
#   3. Save raw-data.csv to data/  <- deliverable for Module 05 ETL
# ================================================================

import sys, pathlib

# run.py lives at the project root — config.py is in the same directory.
# No while loop needed: .parent already points at the project root.
_root = pathlib.Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import SCHEMA, DB_AVAILABLE, logger
from src.query_runner   import SQLQueryRunner
from src.data_extractor import DataExtractor


def main() -> None:
    # ── Startup announcement ──────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("  P05 BANKING SQL — THE DARKO METHOD 2026")
    logger.info(f"  Project      : P05 Banking SQL")
    logger.info(f"  Schema       : {SCHEMA}")
    logger.info(f"  DB Available : {DB_AVAILABLE}")
    logger.info("=" * 60)

    # One SQLQueryRunner instance reused across all four demos.
    # self.history accumulates every run in a single audit log.
    runner = SQLQueryRunner()

    # ── DEMO 1: Basics — row counts and distinct values ───────────────
    print("\n── DEMO 1: Basic SELECT, DISTINCT, and Row Counts")
    runner.demo_basics()

    # ── DEMO 2: Aggregations — volumes, fraud rates, loan portfolio ───
    print("\n── DEMO 2: Aggregations — Transaction Volumes, Fraud by Channel, Loan Portfolio")
    runner.demo_aggregation()

    # ── DEMO 3: Joins — transactions + customers + accounts + loans + alerts
    print("\n── DEMO 3: JOINs — Five-Table Join: Transactions, Customers, Accounts, Loans, Fraud Alerts")
    runner.demo_joins()

    # ── DEMO 4: CTEs and window functions ─────────────────────────────
    print("\n── DEMO 4: CTEs and Window Functions — Customer Risk Profiles and Volume Rankings")
    runner.demo_window_functions()

    # ── Production extraction — the real deliverable ──────────────────
    # DataExtractor().extract().save().report() reads as a sentence:
    #   Create an extractor → extract the data → save it → report on it.
    logger.info("\n[EXTRACT] Starting production extraction...")
    DataExtractor().extract().save().report()


if __name__ == "__main__":
    main()