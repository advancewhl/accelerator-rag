"""Schema v2 contract: identities, status rules and legacy compatibility."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from accelerator_rag.corpus.registry import load_registry
from accelerator_rag.corpus.schema_v2 import (
    DispositionRecord,
    DocumentFamily,
    RegistryV2,
    RevisionRecord,
    from_legacy_records,
    load_registry_v2,
    to_document_record,
    write_registry_v2,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BATCH_ID = "2026-11-02-shine-control"
SOURCE = (
    "data/l0_raw/incoming/2026-11-02-shine-control/资料/演示联锁设计报告.pdf"
)


def revision_data(**overrides):
    data = {
        "family_id": "shine-interlock-design",
        "revision_id": "shine-interlock-design-r1-2018",
        "title": "SHINE 联锁系统初步设计报告",
        "revision_label": "初步设计-2018",
        "batch_id": BATCH_ID,
        "original_asset_id": "asset-shine-interlock-r1-original",
        "source_path": SOURCE,
        "source_format": "pdf",
        "language": "zh",
        "document_kind": "subsystem_design",
        "category": "control_system",
        "topic": "interlock",
        "evidence_role": "design_target",
        "usage_status": "reference",
        "approval_status": "unknown",
        "disposition": "text_index",
        "reason": "设计正文，供检索；批准状态待确认。",
        "received_at": "2026-11-02",
        "document_date": "2018-09",
        "date_precision": "month",
        "owner": "unknown",
        "source_authority": "batch-analysis",
        "access_scope": "internal",
        "parser_profile": "pending-kb2-build",
        "scope": ["SHINE 硬线联锁"],
        "applicable_versions": ["SHINE-2018"],
    }
    data.update(overrides)
    return data


def make_revision(**overrides):
    return RevisionRecord.from_dict(revision_data(**overrides))


def make_family(revision, **overrides):
    data = {
        "family_id": revision.family_id,
        "title": "SHINE 联锁系统设计",
        "description": "联锁系统设计版本族。",
        "revision_ids": [revision.revision_id],
        "created_at": "2026-11-02",
    }
    data.update(overrides)
    return DocumentFamily.from_dict(data)


def make_disposition(revision, **overrides):
    data = {
        "batch_id": revision.batch_id,
        "batch_relative_path": "演示联锁设计报告.pdf",
        "source_path": revision.source_path,
        "source_format": revision.source_format,
        "document_kind": revision.document_kind,
        "priority": "P1",
        "disposition": revision.disposition,
        "planned_action": "convert",
        "reason": revision.reason,
        "target_family_id": revision.family_id,
    }
    data.update(overrides)
    return DispositionRecord.from_dict(data)


def test_revision_round_trip_preserves_all_fields():
    revision = make_revision()

    assert RevisionRecord.from_dict(revision.to_dict()) == revision
    assert revision.ingestible
    assert revision.document_date == "2018-09"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"family_id": "Bad ID"}, "family_id 只能使用"),
        ({"revision_id": ""}, "revision_id 不能为空"),
        ({"title": "   "}, "title 不能为空"),
        ({"source_path": "/tmp/demo.pdf"}, "安全相对路径"),
        ({"source_path": "data/l0_raw/demo.docx"}, "扩展名要求"),
        ({"source_format": "banana"}, "不支持的 source_format"),
        ({"topic": "not-a-topic"}, "不支持 topic"),
        ({"category": "unknown_category"}, "不支持的 category"),
        ({"document_kind": "banana"}, "不支持的 document_kind"),
        (
            {"usage_status": "current", "scope": [], "applicable_versions": []},
            "必须说明 scope",
        ),
        (
            {"usage_status": "current", "approval_status": "withdrawn"},
            "withdrawn/draft",
        ),
        ({"usage_status": "excluded"}, "要求 disposition=excluded"),
        ({"disposition": "excluded"}, "要求 usage_status=excluded"),
        ({"document_date": "2018-9"}, "不符合 date_precision"),
        ({"effective_from": "2020-01", "effective_to": "2019-01"}, "不能早于"),
        ({"source_format": "ppt"}, "不支持的 source_format"),
    ],
)
def test_revision_rejects_invalid_governance(overrides, message):
    with pytest.raises(ValueError, match=message):
        make_revision(**overrides)


def test_array_fields_reject_json_objects():
    with pytest.raises(ValueError, match="字符串数组"):
        RevisionRecord.from_dict(
            {**revision_data(), "tags": {"not": "an array"}}
        )


def test_current_approved_requires_review_record():
    with pytest.raises(ValueError, match="reviewed_by"):
        make_revision(
            usage_status="current",
            approval_status="approved",
        )


def test_structured_index_rejects_non_tabular_sources():
    with pytest.raises(ValueError, match="structured_index"):
        make_revision(disposition="structured_index")


def test_disposition_action_must_match():
    revision = make_revision()
    with pytest.raises(ValueError, match="不一致"):
        make_disposition(revision, planned_action="catalog")
    with pytest.raises(ValueError, match="priority"):
        make_disposition(revision, priority="urgent")


def test_registry_validates_family_and_disposition_consistency():
    revision = make_revision()
    family = make_family(revision)
    disposition = make_disposition(revision)
    registry = RegistryV2(
        schema_version=2,
        release_target="kb-2.0.0",
        generated_on="2026-11-02",
        revisions=(revision,),
        families=(family,),
        dispositions=(disposition,),
    )
    assert registry.summary()["revision_count"] == 1

    with pytest.raises(ValueError, match="重复 revision_id"):
        RegistryV2(
            schema_version=2,
            release_target="kb-2.0.0",
            generated_on="2026-11-02",
            revisions=(revision, revision),
            families=(family,),
            dispositions=(disposition,),
        )
    with pytest.raises(ValueError, match="缺少对应 disposition"):
        RegistryV2(
            schema_version=2,
            release_target="kb-2.0.0",
            generated_on="2026-11-02",
            revisions=(revision,),
            families=(family,),
            dispositions=(),
        )
    with pytest.raises(ValueError, match="missing-family"):
        RegistryV2(
            schema_version=2,
            release_target="kb-2.0.0",
            generated_on="2026-11-02",
            revisions=(replace(revision, family_id="missing-family"),),
            families=(family,),
            dispositions=(disposition,),
        )


def test_registry_round_trip_and_batch_coverage(tmp_path):
    revision = make_revision()
    registry = RegistryV2(
        schema_version=2,
        release_target="kb-2.0.0",
        generated_on="2026-11-02",
        revisions=(revision,),
        families=(make_family(revision),),
        dispositions=(make_disposition(revision),),
    )
    path = tmp_path / "registry-v2.json"
    write_registry_v2(registry, path)

    loaded = load_registry_v2(path)

    assert loaded == registry
    loaded.validate_batch_coverage(BATCH_ID, [SOURCE])
    with pytest.raises(ValueError, match="处置不完整"):
        loaded.validate_batch_coverage(BATCH_ID, [SOURCE, "data/l0_raw/other.pdf"])


def test_load_registry_rejects_unknown_fields(tmp_path):
    path = tmp_path / "registry-v2.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "release_target": "kb-2.0.0",
                "generated_on": "2026-11-02",
                "revisions": [],
                "families": [],
                "dispositions": [],
                "surprise": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="未知字段"):
        load_registry_v2(path)


def test_legacy_migration_preserves_ids_and_does_not_overclaim():
    records = load_registry(PROJECT_ROOT / "data/documents/registry.json") + (
        load_registry(PROJECT_ROOT / "data/documents/registry-md.json")
    )
    registry = from_legacy_records(records, generated_on="2026-11-02")

    assert len(registry.revisions) == 17
    by_id = {revision.revision_id: revision for revision in registry.revisions}
    assert by_id["waveform-storage-dataflow"].usage_status == "current"
    assert by_id["epics-application-developers-guide-r3-16-2"].usage_status == (
        "reference"
    )
    assert by_id["epics-application-developers-guide-r3-16-2"].approval_status == (
        "unknown"
    )
    assert by_id["shine-accelerator-preliminary-design-report-2017"].document_date == (
        "2017-12-26"
    )
    assert all(revision.family_id == revision.revision_id for revision in registry.revisions)
    assert {
        revision.revision_id for revision in registry.revisions
    } == {record.doc_id for record in records}
    for revision in registry.revisions:
        if revision.ingestible:
            record = to_document_record(revision)
            assert record.doc_id == revision.revision_id
            assert record.source_path == revision.source_path
            assert record.document_type == revision.source_format


def test_legacy_adapter_rejects_non_ingestible_formats():
    revision = make_revision(
        source_format="docx", source_path=SOURCE.replace(".pdf", ".docx")
    )
    with pytest.raises(ValueError, match="only accepts pdf/md"):
        to_document_record(revision)


def test_legacy_adapter_rejects_excluded_revision():
    revision = make_revision(
        disposition="excluded", usage_status="excluded", reason="测试排除"
    )
    with pytest.raises(ValueError, match="excluded"):
        to_document_record(revision)
