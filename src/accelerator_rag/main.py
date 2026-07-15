from __future__ import annotations

import logging
import sys
from pathlib import Path

from accelerator_rag.config import ConfigError, load_settings
from accelerator_rag.logging_config import setup_logging


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"


def main() -> int:
    """应用程序主入口。"""

    try:
        settings = load_settings(CONFIG_PATH)
    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 1

    setup_logging(
        log_level=settings.log_level,
        log_dir=PROJECT_ROOT / "logs",
    )

    logger = logging.getLogger(__name__)

    logger.info("应用启动: %s", settings.app_name)
    logger.info("运行环境: %s", settings.environment)
    logger.info("数据目录: %s", settings.data_dir)
    logger.info("Qdrant 地址: %s", settings.qdrant_url)
    logger.info("Collection: %s", settings.collection_name)
    logger.info("Day 2 项目骨架运行成功")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())