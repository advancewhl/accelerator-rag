from __future__ import annotations

from logging.config import dictConfig
from pathlib import Path


def setup_logging(log_level: str, log_dir: Path) -> None:
    """配置终端日志和滚动文件日志。"""

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s | %(levelname)-8s | "
                        "%(name)s | %(message)s"
                    )
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": (
                        "logging.handlers.RotatingFileHandler"
                    ),
                    "level": log_level,
                    "formatter": "standard",
                    "filename": str(log_file),
                    "maxBytes": 1_000_000,
                    "backupCount": 3,
                    "encoding": "utf-8",
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["console", "file"],
            },
        }
    )