# ================================================================
# src/etl_pipeline.py
# ================================================================
# CONTEXT: We have built DataValidator (inspect) and DataTransformer (fix).
# Now we build the conductor that orchestrates both.
#
# THE ANALOGY:
# In an orchestra, individual musicians are experts at their instrument.
# The conductor does not play an instrument — they direct when each musician
# plays and ensure everything happens in the right order.
#
# ETLPipeline is the conductor.
# It owns a DataValidator and a DataTransformer.
# It tells them what to do and in what order.
# It collects their outputs and produces the final result.
#
# THIS IS THE "COORDINATOR" OOP PATTERN:
# Each class has ONE clear responsibility:
#   DataValidator    → inspect data, report problems
#   DataTransformer  → fix data, report changes
#   ETLPipeline      → orchestrate everything, manage files, produce report
#
# ETL stands for Extract → Transform → Load.
# In our pipeline:
#   Extract  = load raw-data.csv from disk (already extracted by Module 03)
#   Validate = run DataValidator
#   Transform= run DataTransformer
#   Load     = save processed-data.csv to disk
# ================================================================

import sys
import pathlib

_root = pathlib.Path(__file__).resolve().parent
while not (_root / "config.py").exists() and _root != _root.parent:
    _root = _root.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import pandas as pd           # for loading the CSV file

from config import (
    INDUSTRY,           # which industry schema we are processing
    RAW_DATA_PATH,      # where to find raw-data.csv
    PROC_DATA_PATH,     # where to save processed-data.csv
    logger              # shared logger
)
from src.validator   import DataValidator    # our quality inspector
from src.transformer import DataTransformer  # our data fixer


class ETLPipeline:
    """Extract, validate, transform, and load the NexBank banking CSV."""

    def __init__(self, raw_path=RAW_DATA_PATH, output_path=PROC_DATA_PATH):
        self.schema = INDUSTRY
        self.raw_path = pathlib.Path(raw_path)
        self.output_path = pathlib.Path(output_path)
        self.raw_df = None
        self.validator = None
        self.transformer = None
        self._status = "ready"
        self._run_log = []

    def extract(self) -> "ETLPipeline":
        if not self.raw_path.exists():
            raise FileNotFoundError(f"Raw data file not found: {self.raw_path}")
        self.raw_df = pd.read_csv(self.raw_path, low_memory=False)
        self._status = "extracted"
        self._log(f"Extracted {len(self.raw_df):,} rows x {self.raw_df.shape[1]} columns from {self.raw_path}.")
        return self

    def validate(self) -> "ETLPipeline":
        self.validator = DataValidator(self.raw_df)
        (
            self.validator
            .check_not_empty()
            .check_schema()
            .check_nulls()
            .check_duplicates()
            .check_dates()
            .check_numeric_ranges()
            .check_business_rules()
            .compute_stats()
        )

        critical = [issue for issue in self.validator.issues if issue["severity"] == "CRITICAL"]
        if critical:
            details = "\n".join(f"- {issue['column']}: {issue['message']}" for issue in critical)
            raise RuntimeError(f"Validation failed with {len(critical)} critical issue(s):\n{details}")

        self._status = "validated"
        self._log(f"Validation passed with {len(self.validator.issues)} issue note(s).")
        return self

    def transform(self) -> "ETLPipeline":
        self.transformer = DataTransformer(self.raw_df)
        (
            self.transformer
            .fix_types()
            .clean_text()
            .fill_nulls()
            .drop_duplicates()
            .add_derived_columns()
            .add_metadata()
        )
        self._status = "transformed"
        self._log(f"Transformation complete with {len(self.transformer.changes)} logged change(s).")
        return self

    def load(self) -> "ETLPipeline":
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.transformer.df.to_csv(self.output_path, index=False, encoding="utf-8")
        self._status = "loaded"
        self._log(f"Loaded {len(self.transformer.df):,} rows to {self.output_path}.")
        return self

    def report(self) -> None:
        transform_summary = self.transformer.summary()

        print()
        print("=" * 70)
        print("  NEXBANK BANKING ETL PIPELINE COMPLETE")
        print("=" * 70)
        print(f"  Schema:          {self.schema}")
        print(f"  Status:          {self._status.upper()}")
        print(f"  Source:          {self.raw_path}")
        print(f"  Output:          {self.output_path}")
        print()
        print("  VALIDATION")
        print(f"    Rows:          {self.validator.stats['rows']:,}")
        print(f"    Columns:       {self.validator.stats['columns']}")
        print(f"    Critical:      {self.validator.stats['critical_count']}")
        print(f"    Warnings:      {self.validator.stats['warning_count']}")
        print(f"    Info notes:    {self.validator.stats['info_count']}")
        print()
        print("  TRANSFORMATION")
        print(f"    Rows before:   {transform_summary['original_rows']:,}")
        print(f"    Rows after:    {transform_summary['final_rows']:,}")
        print(f"    Rows removed:  {transform_summary['rows_removed']:,}")
        print(f"    Columns now:   {transform_summary['final_columns']}")
        print()
        print("  CHANGE LOG")
        for change in transform_summary["change_log"]:
            print(f"    - {change}")
        print()
        print("  PIPELINE LOG")
        for entry in self._run_log:
            print(f"    - {entry}")
        print("=" * 70)

    def _log(self, message: str) -> None:
        self._run_log.append(message)
        logger.info(f"[PIPELINE] {message}")