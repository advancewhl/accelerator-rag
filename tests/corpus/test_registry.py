import json
from pathlib import Path

import pytest

from accelerator_rag.corpus.registry import (
    DocumentRecord,
    build_inventory,
    load_registry,
    validate_inventory,
)


def make_document_record(**overrides: str) -> DocumentRecord:
    data = {
        "doc_id": "demo-epics",
        "title": "EPICS Demo Document",
        "source_path": "data/raw/demo.pdf",
        "category": "control_system",
        "topic": "epics",
        "document_type": "pdf",
        "language": "en",
        "version": "unknown",
        "status": "active",
    }
    data.update(overrides)
    return DocumentRecord(**data)


def as_dict(record: DocumentRecord) -> dict[str, str]:
    return {
        "doc_id": record.doc_id,
        "title": record.title,
        "source_path": record.source_path,
        "category": record.category,
        "topic": record.topic,
        "document_type": record.document_type,
        "language": record.language,
        "version": record.version,
        "status": record.status,
    }


def write_registry(path: Path, records: object) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def test_document_record_accepts_valid_metadata() -> None:
    record = make_document_record()

    assert record.doc_id == "demo-epics"
    assert record.topic == "epics"
    assert record.document_type == "pdf"
    assert record.status == "active"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"title": "   "}, "title 不能为空"),
        ({"doc_id": "Bad ID"}, "doc_id 只能使用"),
        ({"document_type": "banana"}, "不支持的 document_type"),
        ({"language": "fr"}, "不支持的 language"),
        ({"status": "deleted"}, "不支持的 status"),
        ({"category": "random_category"}, "不支持的 category"),
        (
            {"category": "beam_diagnostics", "topic": "epics"},
            "不支持 topic",
        ),
        ({"source_path": "/tmp/demo.pdf"}, "安全相对路径"),
        ({"source_path": "data/raw/../demo.pdf"}, "安全相对路径"),
        ({"source_path": "docs/demo.pdf"}, "必须位于 data/raw"),
        (
            {"source_path": "data/raw/demo.pptx"},
            "扩展名必须与 document_type 一致",
        ),
    ],
)
def test_document_record_rejects_invalid_metadata(
    overrides: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        make_document_record(**overrides)


def test_load_registry_accepts_valid_records(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    write_registry(registry_path, [as_dict(make_document_record())])

    loaded = load_registry(registry_path)

    assert loaded == [make_document_record()]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "根节点必须是 JSON 数组"),
        (["invalid"], "必须是 JSON 对象"),
        ([{"doc_id": "epics-guide"}], "记录无效"),
    ],
)
def test_load_registry_rejects_invalid_structure(
    tmp_path: Path,
    payload: object,
    message: str,
) -> None:
    registry_path = tmp_path / "registry.json"
    write_registry(registry_path, payload)

    with pytest.raises(ValueError, match=message):
        load_registry(registry_path)


def test_load_registry_rejects_duplicate_doc_id(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    record = as_dict(make_document_record())
    write_registry(registry_path, [record, record])

    with pytest.raises(ValueError, match="重复 doc_id"):
        load_registry(registry_path)


def test_load_registry_rejects_duplicate_source_path(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    record = as_dict(make_document_record())
    duplicate = {**record, "doc_id": "other-document"}
    write_registry(registry_path, [record, duplicate])

    with pytest.raises(ValueError, match="重复 source_path"):
        load_registry(registry_path)


def test_load_registry_rejects_invalid_json(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="registry 文件不是合法 JSON"):
        load_registry(registry_path)


def test_inventory_reports_counts_and_consistency(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    raw_root.mkdir(parents=True)
    (raw_root / "demo.pdf").write_bytes(b"demo")
    records = [make_document_record()]

    inventory = build_inventory(records, tmp_path)

    assert inventory.is_consistent
    assert inventory.registered_count == 1
    assert inventory.raw_file_count == 1
    assert inventory.registered_size_bytes == 4
    assert inventory.by_category == {"control_system": 1}
    assert inventory.by_topic == {"epics": 1}
    validate_inventory(inventory)


def test_inventory_detects_missing_and_unregistered_files(tmp_path: Path) -> None:
    raw_root = tmp_path / "data" / "raw"
    raw_root.mkdir(parents=True)
    (raw_root / "unregistered.pdf").write_bytes(b"pdf")
    records = [make_document_record()]

    inventory = build_inventory(records, tmp_path)

    assert not inventory.is_consistent
    assert inventory.missing_files == ("data/raw/demo.pdf",)
    assert inventory.unregistered_files == ("data/raw/unregistered.pdf",)
    with pytest.raises(ValueError, match="登记但缺失.*存在但未登记"):
        validate_inventory(inventory)


def test_project_registry_has_thirteen_valid_records() -> None:
    project_root = Path(__file__).resolve().parents[2]

    records = load_registry(project_root / "data" / "documents" / "registry.json")

    assert len(records) == 13
    assert len({record.doc_id for record in records}) == 13
