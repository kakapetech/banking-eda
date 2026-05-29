import pathlib
import sys

_root = pathlib.Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from config import INDUSTRY, logger
from src.etl_pipeline import ETLPipeline, PROC_DATA_PATH, RAW_DATA_PATH


def main() -> None:
    logger.info("=" * 60)
    logger.info("  NEXBANK BANKING ETL PIPELINE STARTING")
    logger.info(f"  Schema : {INDUSTRY}")
    logger.info(f"  Input  : {RAW_DATA_PATH}")
    logger.info(f"  Output : {PROC_DATA_PATH}")
    logger.info("=" * 60)

    pipeline = ETLPipeline()
    pipeline.extract().validate().transform().load().report()

    logger.info(f"Pipeline complete: {pipeline}")


if __name__ == "__main__":
    main()