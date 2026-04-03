import logging
import os
from logging.handlers import RotatingFileHandler
import sys
import json

from src.core.config import settings


class ColoredFormatter(logging.Formatter):
    """Custom formatter for colored log output in development"""

    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    format_str = (
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: blue + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging in production"""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "file": record.filename,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def setup_logging() -> logging.Logger:
    """Configure the root logger based on settings"""
    logger = logging.getLogger()

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    if logger.handlers:
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if settings.LOG_JSON_FORMAT:
        formatter = JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S")
    else:
        formatter = ColoredFormatter()

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if settings.LOG_FILE:
        os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)
        file_handler = RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
        )
        file_handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)
