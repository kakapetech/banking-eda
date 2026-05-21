# ================================================================
# run.py — Module 06 Entry Point
# ================================================================
# This is the file you run to execute the full EDA pipeline.
#
# HOW TO RUN (from this project folder):
#   python run.py
#
# WHAT HAPPENS:
#   1. Load processed-data.csv (from Module 05)
#   2. Profile the dataset (shape, completeness, distributions)
#   3. Group analysis (metrics by category — e.g. salary by department)
#   4. Correlation (which numeric variables move together?)
#   5. Time trends (if a time column exists)
#   6. Print and save the analysis report
#   7. Run anomaly detection (IQR + Z-score consensus)
#   8. Save confirmed anomalies to reports/anomalies.csv
# ================================================================

import sys
import pathlib

# Add project root to Python path so imports work from any directory
_root = pathlib.Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import ANALYSIS_REPORT_PATH, ANOMALIES_PATH, SEGMENT_PROFILE_PATH, logger
from src.eda_engine       import EDAEngine
from src.anomaly_detector import AnomalyDetector


def main() -> None:
    logger.info("=" * 60)
    logger.info("  P02 BANKING EDA STARTING")
    logger.info("=" * 60)

    engine = EDAEngine().run_all()

    logger.info("EDA complete.")
    logger.info(f"Report: {ANALYSIS_REPORT_PATH}")
    logger.info(f"Anomalies: {ANOMALIES_PATH}")
    logger.info(f"Segment profile: {SEGMENT_PROFILE_PATH}")

    print()
    print("BANKING EDA COMPLETE")
    print(f"Rows analyzed: {engine.profile['rows']:,}")
    print(f"Fraud rate: {engine.profile['fraud_rate']:.2%}")
    print(f"Anomalies flagged: {len(engine.anomalies):,}")


if __name__ == "__main__":
    main()