from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """配置文件无法正确读取时抛出的异常"""


@dataclass(frozen=True)
class Settings:
    """程序运行所需配置"""

    app_name: str
    environment: str
    log_level: str
    data_dir: Path
    qdrant_url: str
    collection_name: str


def _require_string(data: dict[str, Any], key: str) -> str:
    """读取并验证一个非空字符串配置项"""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"配置项 {key!r} 必须是非空字符串")

    return value.strip()


def load_settings(config_path: Path) -> Settings:
    """从JSON文件中读取,验证并返回配置对象"""

    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件 {config_path} 不存在") from exc
    except OSError as exc:
        raise ConfigError(f"无法读取配置文件 {config_path}") from exc

    try:
        parsed: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"配置文件JSON格式错误line={exc.lineno},column={exc.colno}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ConfigError("配置文件必须是一个JSON对象")

    data: dict[str, Any] = parsed

    log_level = _require_string(data, "log_level").upper()
    allowed_levels = {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }

    if log_level not in allowed_levels:
        raise ConfigError(
            f"不支持的日志等级:{log_level};允许值为:{sorted(allowed_levels)}"
        )

    project_root = config_path.resolve().parent.parent
    data_dir_value = _require_string(data, "data_dir")

    return Settings(
        app_name=_require_string(data, "app_name"),
        environment=_require_string(data, "environment"),
        log_level=log_level,
        data_dir=(project_root / data_dir_value).resolve(),
        qdrant_url=_require_string(data, "qdrant_url"),
        collection_name=_require_string(data, "collection_name"),
    )
