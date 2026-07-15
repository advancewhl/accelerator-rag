import json

import pytest

from accelerator_rag.config import ConfigError, load_settings


def test_load_settings(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    config_path = config_dir / "settings.json"

    config_path.write_text(
        json.dumps(
            {
                "app_name": "test-app",
                "environment": "test",
                "log_level": "debug",
                "data_dir": "data",
                "qdrant_url": "http://localhost:6333",
                "collection_name": "test_docs",
            }
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.app_name == "test-app"
    assert settings.log_level == "DEBUG"
    assert settings.data_dir == (tmp_path / "data").resolve()


def test_invalid_json_raises_config_error(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    config_path = config_dir / "settings.json"
    config_path.write_text(
        "{invalid json}",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_settings(config_path)
