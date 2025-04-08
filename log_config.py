# log_config.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_PATH = Path(__file__).parent / "fitness_pipeline.log"

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:  # Prevent duplicate handlers on import
        handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
