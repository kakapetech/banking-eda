# ================================================================
# tests/test_eda.py — Unit Tests for Module 06
# ================================================================
# WHY TEST EDA CODE?
# ──────────────────
# EDA results feed into ML feature selection, LLM context, and
# MLOps monitoring. If the EDAEngine computes incorrect statistics,
# every downstream module makes decisions on wrong information.
# Tests catch bugs before they contaminate the entire pipeline.
#
# HOW TO RUN:
#   python tests/test_eda.py
# or with pytest:
#   pytest tests/
# ================================================================

import sys, pathlib
_root = pathlib.Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd
import numpy as np
import tempfile
from src.eda_engine       import EDAEngine
from src.anomaly_detector import AnomalyDetector
from src.eda_engine import EDAEngine, SegmentProfiler


def make_df() -> pd.DataFrame:
    return pd.DataFrame({
        "transaction_id": range(1, 13),
        "customer_id": [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6],
        "transaction_date": ["2024-01-01"] * 12,
        "transaction_time": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"] * 2,
        "transaction_value": [20, 25, 30, 35, 40, 45, 1000, 55, 60, 65, 70, 75],
        "amount": [20, 25, 30, 35, 40, 45, 1000, 55, 60, 65, 70, 75],
        "merchant_category": ["Grocery", "Grocery", "Travel", "Travel", "Gas", "Gas", "Travel", "Grocery", "Gas", "Travel", "Grocery", "Gas"],
        "channel": ["Online", "ATM", "Mobile", "Branch", "Online", "ATM", "Mobile", "Branch", "Online", "ATM", "Mobile", "Branch"],
        "segment": ["Retail", "Retail", "Premium", "Premium", "Business", "Business", "Student", "Student", "Retail", "Premium", "Business", "Student"],
        "is_fraud": [False, False, True, False, False, True, False, False, True, False, False, True],
    })


def test_segment_profiler_returns_dataframe():
    profile = SegmentProfiler(make_df()).compute()
    assert isinstance(profile, pd.DataFrame)


def test_segment_profiler_has_fraud_rate():
    profile = SegmentProfiler(make_df()).compute()
    assert "fraud_rate" in profile.columns


def test_segment_profiler_has_all_segments():
    profile = SegmentProfiler(make_df()).compute()
    assert set(profile["segment"]) == {"Retail", "Premium", "Business", "Student"}


def test_anomaly_detector_adds_scores():
    detector = AnomalyDetector(make_df()).add_amount_scores()
    assert "amount_z_score" in detector.df.columns


def test_anomaly_detector_flags_anomaly_column():
    detector = AnomalyDetector(make_df()).add_amount_scores()
    assert "amount_anomaly" in detector.df.columns


def test_anomaly_detector_flags_fraud_normal_amount():
    detector = AnomalyDetector(make_df()).add_amount_scores().flag_fraud_anomalies()
    assert "fraud_with_normal_amount" in detector.df.columns


def test_anomaly_detector_returns_anomalies_dataframe():
    anomalies = AnomalyDetector(make_df()).flag_fraud_anomalies().get_anomalies()
    assert isinstance(anomalies, pd.DataFrame)


def test_anomaly_summary_has_total_flagged_rows():
    summary = AnomalyDetector(make_df()).flag_fraud_anomalies().summary()
    assert "total_flagged_rows" in summary


def test_engine_loads_data_from_csv():
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "processed-data.csv"
        make_df().to_csv(path, index=False)
        engine = EDAEngine(data_path=path).load_data()
        assert len(engine.df) == 12


def test_engine_profiles_data():
    engine = EDAEngine()
    engine.df = make_df()
    engine.profile_data()
    assert engine.profile["rows"] == 12


def test_engine_fraud_patterns_creates_tables():
    engine = EDAEngine()
    engine.df = make_df()
    engine.fraud_patterns()
    assert "merchant_category" in engine.fraud_tables


def test_engine_chi_square_test_returns_p_value():
    engine = EDAEngine()
    engine.df = make_df()
    engine.chi_square_test()
    assert "p_value" in engine.chi_square_result


def test_engine_detect_anomalies_sets_dataframe():
    engine = EDAEngine()
    engine.df = make_df()
    engine.detect_anomalies()
    assert isinstance(engine.anomalies, pd.DataFrame)


def test_engine_group_analysis_sets_segment_profile():
    engine = EDAEngine()
    engine.df = make_df()
    engine.group_analysis()
    assert not engine.segment_profile.empty