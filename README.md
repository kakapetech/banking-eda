# NexBank Banking Analytics Workspace

This repository is an end-to-end NexBank banking analytics workspace. It now contains three connected project stages:

1. `nexbank-sql-extractor/` extracts raw banking records from PostgreSQL/Supabase.
2. `nexbank-etl-pipeline/` validates, cleans, transforms, and enriches the raw CSV.
3. The root `banking-eda` project analyzes the processed data for fraud patterns, segment behavior, chi-square significance, and transaction anomalies.

## Business Context

NexBank's Risk Analytics team needs evidence of fraud concentration, customer segment behavior, and suspicious transaction activity. The full workflow starts from normalized banking database tables and ends with EDA reports and anomaly exports.

## End-to-End Pipeline

```mermaid
flowchart TD
    A["Supabase/PostgreSQL banking schema"] --> B["nexbank-sql-extractor"]
    B --> C["nexbank-sql-extractor/data/raw-data.csv"]
    C --> D["nexbank-etl-pipeline"]
    D --> E["nexbank-etl-pipeline/data/processed/processed-data.csv"]
    E --> F["data/processed-data.csv"]
    F --> G["Root Banking EDA"]
    G --> H["reports/analysis_report.txt"]
    G --> I["reports/anomalies.csv"]
    G --> J["reports/segment_profile.csv"]
```

## Repository Structure

```text
banking-eda/
├── config.py
├── run.py
├── requirements.txt
├── README.md
├── data/
│   └── processed-data.csv
├── notebooks/
│   └── 01_eda_exploration.ipynb
├── reports/
│   ├── analysis_report.txt
│   ├── anomalies.csv
│   └── segment_profile.csv
├── setup/
│   └── verify_connection.py
├── src/
│   ├── anomaly_detector.py
│   └── eda_engine.py
├── test/
│   └── test_eda.py
├── nexbank-sql-extractor/
│   ├── config.py
│   ├── run.py
│   ├── requirements.txt
│   ├── sql/
│   │   └── 05_extract_raw_data.sql
│   ├── src/
│   │   ├── data_extractor.py
│   │   └── query_runner.py
│   └── test/
│       └── test.py
└── nexbank-etl-pipeline/
    ├── config.py
    ├── run.py
    ├── requirements.txt
    ├── src/
    │   ├── etl_pipeline.py
    │   ├── transformer.py
    │   └── validator.py
    └── test/
        └── test_pipeline.py
```

## Stage 1: SQL Extraction

`nexbank-sql-extractor/` connects to the `banking` schema and creates a 43-column raw transaction extract.

### Source Tables

```mermaid
erDiagram
    CUSTOMERS ||--o{ ACCOUNTS : owns
    CUSTOMERS ||--o{ TRANSACTIONS : makes
    ACCOUNTS ||--o{ TRANSACTIONS : records
    CUSTOMERS ||--o{ LOANS : has
    TRANSACTIONS ||--o| FRAUD_ALERTS : may_trigger

    CUSTOMERS {
        int customer_id
        string segment
        int credit_score
    }
    ACCOUNTS {
        int account_id
        int customer_id
        string account_type
        numeric balance
    }
    TRANSACTIONS {
        int transaction_id
        int account_id
        int customer_id
        numeric amount
        bool is_fraud
    }
    LOANS {
        int loan_id
        int customer_id
        string risk_grade
    }
    FRAUD_ALERTS {
        int alert_id
        int transaction_id
        string severity
    }
```

### SQL Extract Output

```text
nexbank-sql-extractor/data/raw-data.csv
```

The raw extract includes transaction, customer, account, loan, and fraud alert fields. Transactions are the anchor records. Customer and account joins are required; loans and fraud alerts are left joins, so nulls are expected.

## Stage 2: ETL Pipeline

`nexbank-etl-pipeline/` reads raw banking data, validates the schema, fixes data types, handles nulls, removes duplicates, and adds derived banking features.

### ETL Steps

```mermaid
sequenceDiagram
    participant Raw as raw-data.csv
    participant Pipeline as ETLPipeline
    participant Validator as DataValidator
    participant Transformer as DataTransformer
    participant Processed as processed-data.csv

    Raw->>Pipeline: extract()
    Pipeline->>Validator: validate schema, nulls, dates, ranges, business rules
    Pipeline->>Transformer: fix types, clean text, fill nulls, add features
    Transformer->>Processed: load()
```

### ETL Output

```text
nexbank-etl-pipeline/data/processed/processed-data.csv
```

Key derived fields include:

- `customer_name`
- `signed_amount`
- `transaction_value`
- `amount_was_negative`
- `has_loan`
- `has_fraud_alert`
- `balance_before_estimate`
- `loan_remaining_pct`
- `credit_score_band`
- `transaction_year`
- `transaction_month`

## Stage 3: Banking EDA

The root project reads `data/processed-data.csv` and generates fraud analytics reports.

### EDA Questions

- Where does fraud concentrate by merchant category, channel, hour, month, and segment?
- How do customer segments differ by transaction value, frequency, and fraud rate?
- Is fraud statistically independent of `merchant_category`?
- Which transaction amounts are anomalous by IQR and Z-score?
- Which fraud records have normal-looking amounts and may be harder to detect?

### EDA Outputs

| Output | Description |
|---|---|
| `reports/analysis_report.txt` | Human-readable analysis report with data profile, chi-square result, fraud patterns, anomaly summary, and segment profile. |
| `reports/anomalies.csv` | Rows flagged as amount anomalies, fraud with normal amount, or suspicious amount not marked fraud. |
| `reports/segment_profile.csv` | Segment-level transaction counts, customer counts, value metrics, fraud counts, and fraud rates. |

## Setup

Create and activate a virtual environment, then install dependencies for the stage you want to run.

Root EDA:

```powershell
cd C:\banking-eda
pip install -r requirements.txt
```

SQL extractor:

```powershell
cd C:\banking-eda\nexbank-sql-extractor
pip install -r requirements.txt
```

ETL pipeline:

```powershell
cd C:\banking-eda\nexbank-etl-pipeline
pip install -r requirements.txt
```

## Environment Variables

For the SQL extractor, create `nexbank-sql-extractor/.env`:

```text
SCHEMA=banking
DB_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres
```

The SQL extractor can generate synthetic banking data when the database is unavailable, so local demos and tests can still run.

## How to Run the Full Workflow

### 1. Extract Raw Banking Data

```powershell
cd C:\banking-eda\nexbank-sql-extractor
python run.py
```

This creates:

```text
C:\banking-eda\nexbank-sql-extractor\data\raw-data.csv
```

### 2. Move Raw Data into the ETL Input Folder

```powershell
Copy-Item C:\banking-eda\nexbank-sql-extractor\data\raw-data.csv C:\banking-eda\nexbank-etl-pipeline\data\raw\raw-data.csv
```

### 3. Run the ETL Pipeline

```powershell
cd C:\banking-eda\nexbank-etl-pipeline
python run.py
```

This creates:

```text
C:\banking-eda\nexbank-etl-pipeline\data\processed\processed-data.csv
```

### 4. Move Processed Data into the EDA Input Folder

```powershell
Copy-Item C:\banking-eda\nexbank-etl-pipeline\data\processed\processed-data.csv C:\banking-eda\data\processed-data.csv
```

### 5. Run the EDA

```powershell
cd C:\banking-eda
python run.py
```

This writes the final reports to:

```text
C:\banking-eda\reports\
```

## Testing

Run each stage's tests from its own folder.

SQL extractor:

```powershell
cd C:\banking-eda\nexbank-sql-extractor
python test\test.py
```

ETL pipeline:

```powershell
cd C:\banking-eda\nexbank-etl-pipeline
python -m pytest test
```

Root EDA:

```powershell
cd C:\banking-eda
python -m pytest test
```

## Key Python Components

| Path | Responsibility |
|---|---|
| `nexbank-sql-extractor/src/query_runner.py` | Executes SQL strings and SQL files against PostgreSQL. |
| `nexbank-sql-extractor/src/data_extractor.py` | Runs the production extract and saves `raw-data.csv`. |
| `nexbank-etl-pipeline/src/validator.py` | Validates raw schema, required columns, nulls, dates, numeric ranges, and business rules. |
| `nexbank-etl-pipeline/src/transformer.py` | Cleans types/text, fills expected nulls, removes duplicates, and adds banking features. |
| `nexbank-etl-pipeline/src/etl_pipeline.py` | Orchestrates extract, validate, transform, load, and reporting. |
| `src/eda_engine.py` | Runs profiling, fraud pattern analysis, segment profiling, chi-square testing, anomaly detection, and output writing. |
| `src/anomaly_detector.py` | Detects suspicious amount behavior using IQR and Z-score consensus. |

## Data and Git Hygiene

Generated data and reports should stay out of Git:

- `.env`
- virtual environments
- `data/*.csv`
- `reports/*.txt`
- `reports/*.csv`

Keep source code, SQL, tests, notebooks, and documentation committed.

## License

This project is licensed under the MIT License. See `LICENSE` for details.
