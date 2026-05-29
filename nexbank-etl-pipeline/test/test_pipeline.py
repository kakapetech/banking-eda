import pathlib
import sys
import tempfile

import pandas as pd

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.etl_pipeline import ETLPipeline
from src.transformer import DataTransformer
from src.validator import DataValidator


def make_clean_banking_df(rows: int = 6) -> pd.DataFrame:
    return pd.DataFrame({
        "transaction_id": range(1, rows + 1),
        "account_id": [101, 102, 103, 104, 105, 106][:rows],
        "customer_id": [201, 202, 203, 204, 205, 206][:rows],
        "transaction_date": ["2024-12-01", "2024-12-02", "2024-12-03", "2024-12-04", "2024-12-05", "2024-12-06"][:rows],
        "transaction_time": ["08:00", "09:15", "10:30", "11:45", "12:00", "13:20"][:rows],
        "amount": [25.0, 100.0, 55.5, 210.0, 15.75, 80.0][:rows],
        "transaction_type": ["Debit", "Credit", "Payment", "Transfer", "ATM", "Debit"][:rows],
        "merchant_name": ["Amazon", "Shell", "Target", "Walmart", "Starbucks", "Apple"][:rows],
        "merchant_category": ["Grocery", "Gas", "Retail", "Utilities", "Restaurant", "Electronics"][:rows],
        "channel": ["Online", "ATM", "Mobile", "Branch", "Online", "Mobile"][:rows],
        "transaction_status": ["Completed"] * rows,
        "is_fraud": [False] * rows,
        "balance_after": [1000.0, 1500.0, 900.0, 2500.0, 700.0, 1200.0][:rows],
        "first_name": ["Ama", "Kojo", "Efua", "Kwame", "Akosua", "Yaw"][:rows],
        "last_name": ["Mensah", "Owusu", "Taylor", "Singh", "Lewis", "Brown"][:rows],
        "email": ["a@example.com", "b@example.com", "c@example.com", "d@example.com", "e@example.com", "f@example.com"][:rows],
        "city": ["Accra", "Kumasi", "London", "Toronto", "Nairobi", "Sydney"][:rows],
        "date_of_birth": ["1988-01-01"] * rows,
        "credit_score": [650, 720, 580, 800, 690, 610][:rows],
        "customer_since": ["2015-01-01"] * rows,
        "segment": ["Retail", "Premium", "Student", "Business", "Senior", "Retail"][:rows],
        "account_type": ["Checking", "Savings", "Business", "CD", "Money Market", "Checking"][:rows],
        "account_number": [f"ACC{i:08d}" for i in range(1, rows + 1)],
        "balance": [2000.0, 3000.0, 1000.0, 5000.0, 1200.0, 2500.0][:rows],
        "currency": ["GHS", "USD", "GBP", "EUR", "CAD", "GHS"][:rows],
        "opened_date": ["2016-01-01"] * rows,
        "account_status": ["Active"] * rows,
        "account_interest_rate": [0.02] * rows,
        "loan_id": [pd.NA] * rows,
        "loan_type": [pd.NA] * rows,
        "principal": [pd.NA] * rows,
        "loan_interest_rate": [pd.NA] * rows,
        "term_months": [pd.NA] * rows,
        "monthly_payment": [pd.NA] * rows,
        "loan_outstanding_balance": [pd.NA] * rows,
        "loan_status": [pd.NA] * rows,
        "risk_grade": [pd.NA] * rows,
        "alert_id": [pd.NA] * rows,
        "alert_date": [pd.NA] * rows,
        "alert_type": [pd.NA] * rows,
        "alert_severity": [pd.NA] * rows,
        "alert_status": [pd.NA] * rows,
        "amount_at_risk": [pd.NA] * rows,
    })


def test_validator_passes_clean_banking_data():
    validator = (
        DataValidator(make_clean_banking_df())
        .check_not_empty()
        .check_schema()
        .check_nulls()
        .check_duplicates()
        .check_dates()
        .check_numeric_ranges()
        .check_business_rules()
        .compute_stats()
    )
    assert validator._passed is True
    assert validator.stats["critical_count"] == 0


def test_validator_fails_missing_required_column():
    df = make_clean_banking_df().drop(columns=["transaction_id"])
    validator = DataValidator(df).check_schema().compute_stats()
    assert validator._passed is False


def test_validator_fails_bad_credit_score():
    df = make_clean_banking_df()
    df.loc[0, "credit_score"] = 1000
    validator = DataValidator(df).check_numeric_ranges().compute_stats()
    assert validator._passed is False


def test_transformer_adds_banking_columns_and_metadata():
    transformer = (
        DataTransformer(make_clean_banking_df())
        .fix_types()
        .clean_text()
        .fill_nulls()
        .drop_duplicates()
        .add_derived_columns()
        .add_metadata()
    )
    for col in ["customer_name", "has_loan", "has_fraud_alert", "balance_before_estimate", "credit_score_band", "_processed_at"]:
        assert col in transformer.df.columns


def test_transformer_does_not_modify_original_dataframe():
    df = make_clean_banking_df()
    original_nulls = int(df["principal"].isna().sum())
    DataTransformer(df).fix_types().fill_nulls()
    assert int(df["principal"].isna().sum()) == original_nulls


def test_pipeline_runs_end_to_end_with_temp_files():
    df = make_clean_banking_df()
    with tempfile.TemporaryDirectory() as tmp:
        raw_path = pathlib.Path(tmp) / "raw-data.csv"
        out_path = pathlib.Path(tmp) / "processed-data.csv"
        df.to_csv(raw_path, index=False)
        pipeline = ETLPipeline(raw_path=raw_path, output_path=out_path)
        pipeline.extract().validate().transform().load()
        assert out_path.exists()
        processed = pd.read_csv(out_path)
        assert "credit_score_band" in processed.columns
        assert len(processed) == len(df)


if __name__ == "__main__":
    tests = [
        test_validator_passes_clean_banking_data,
        test_validator_fails_missing_required_column,
        test_validator_fails_bad_credit_score,
        test_transformer_adds_banking_columns_and_metadata,
        test_transformer_does_not_modify_original_dataframe,
        test_pipeline_runs_end_to_end_with_temp_files,
    ]

    passed = 0
    for test_fn in tests:
        test_fn()
        print(f"PASS: {test_fn.__name__}")
        passed += 1

    print(f"{passed} test(s) passed.")