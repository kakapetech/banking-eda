# ================================================================
# config.py — Retail ETL Pipeline Configuration
# ================================================================
# ShopStream Global
# The Darko Method 2026
#
# This file provides shared settings to every module in the pipeline.
# Import from here — never hardcode paths or schema names elsewhere.
#
# WHAT THIS FILE PROVIDES:
#   SCHEMA              — 'retail' (source schema name)
#   PROJECT_ROOT        — absolute path to this project folder
#   RAW_DATA_PATH       — data/raw/raw-data.csv  (input)
#   PROCESSED_DATA_PATH — data/processed/processed-data.csv  (output)
#   logger              — pre-configured Python Logger for the pipeline
#
# COLUMNS IN raw-data.csv (34 total, from retail schema):
#   From sales (10):
#     sale_id, store_id, product_id, sale_date, sale_quantity,
#     sale_unit_price, discount_pct, total_amount,
#     payment_method, customer_type
#   From products (8):
#     product_name, category, sub_category, brand, sku,
#     unit_cost, unit_price, margin_pct
#   From stores (6):
#     store_name, city, region, store_type, sqft, store_is_active
#   From inventory (4, LEFT JOIN — 16 nulls each):
#     current_stock, reorder_level, last_restocked, supplier
#   From returns (6, LEFT JOIN — 272 nulls each):
#     return_id, return_date, return_quantity, return_reason,
#     refund_amount, return_status
#
# KNOWN DATA QUALITY ISSUES (Validator finds, Transformer fixes):
#   current_stock     — 16 nulls (5.3%)  — LEFT JOIN inventory
#   reorder_level     — 16 nulls (5.3%)  — LEFT JOIN inventory
#   last_restocked    — 16 nulls (5.3%)  — LEFT JOIN inventory
#   supplier          — 16 nulls (5.3%)  — LEFT JOIN inventory
#   return_id         — 272 nulls (90.7%) — LEFT JOIN returns (expected)
#   return_date       — 272 nulls (90.7%) — LEFT JOIN returns (expected)
#   return_quantity   — 272 nulls (90.7%) — LEFT JOIN returns (expected)
#   return_reason     — 272 nulls (90.7%) — LEFT JOIN returns (expected)
#   refund_amount     — 272 nulls (90.7%) — LEFT JOIN returns (expected)
#   return_status     — 272 nulls (90.7%) — LEFT JOIN returns (expected)
#   store_is_active   — stored as string 'True' — needs bool cast
#   sale_date         — stored as string — needs datetime parse
# ================================================================

import os
import pathlib
import logging
from dotenv import load_dotenv


# load the dotenv which reads that file and makes those values available
load_dotenv()

# Industry setting
INDUSTRY = os.getenv("INDUSTRY", "banking")

LEARNER_SCHEMA = os.getenv("LEARNER SCHEMA", "learner_41")

# File paths

# pathlib.Path(__file__) gives the path to this config.py file
# .resolve() converts it to an absolute path (no relative ".." parts)
# .parent gives the folder that config.py lives in.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent

# The data/ folder is next to config.py in the project root.
DATA_DIR = PROJECT_ROOT / "data"             # /path/to/project/data
RAW_DATA_DIR = DATA_DIR / "raw"              # /path/to/project/data/raw
PROC_DATA_DIR = DATA_DIR / "processed"       # /path/to/project/data/processed

# The  actual file paths we will read from and write to
RAW_DATA_PATH = RAW_DATA_DIR / "raw-data.csv"
PROC_DATA_PATH = PROC_DATA_DIR / "processed-data.csv"

# create directories
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROC_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Database connection
DB_URL = os.getenv(
    "DB_URL",
    ""
)

try:
    from sqlalchemy import create_engine
    engine = create_engine(DB_URL, pool_pre_ping=True)
    # pool_pre_ping=True: test each connection before using it
    # If the connection dropped, SQLAlchemy gets a fresh one automatically
except Exception as _e:
    engine = None   # No database — CSV-based pipeline will still work

# Logging setup
def _setup_logger(name: str = "kakape") -> logging.Logger:
    """
    Create and configure the project logger.

    This function creates one logger that is reused everywhere.
    ALL modules import 'logger' from config.py:
        from config import logger
        logger.info("Something happened")
    """

    # create or get a logger with the given name
    lgr = logging.getLogger(name)

    # set the minimum level - messagess below INFO ae ignored
    lgr.setLevel(logging.INFO)

    # Only add handlers if none exist yet (prevent duplicate log lines)
    if not lgr.handlers:
        # StreamHandler sends log messages to the terminal (stdout)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)

        # Formatter defines what each log line looks like
        # %(asctime)s   → timestamp: 2026-01-15 10:23:01
        # %(levelname)s → severity:  INFO / WARNING / ERROR
        # %(message)s   → your message
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(fmt)
        lgr.addHandler(handler)

    return lgr

# Create the shared logger -  all modules import this
logger = _setup_logger("kakape")

# Validation thresholds
# These numbers define what counts as "acceptable" data quality.
# They are constants — all caps by Python convention — and live here
# so they can be changed in one place.
MAX_NULL_PERCENT      = 50.0   # columns with >50% nulls are flagged CRITICAL
MAX_DUPLICATE_PERCENT = 5.0    # more than 5% duplicate rows is CRITICAL
