"""Catalog v2 metadata, family grouping and release identity exposure."""

import json
from types import SimpleNamespace

import fitz
from fastapi.testclient import TestClient

from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.rag.api import create_app
from accelerator_rag.rag.catalog import DocumentCatalog
from accelerator_rag.rag.release import (
    ReleaseIdentity,
    release_identity_from_config,
    release_status,
)


def make_pdf(path):
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(path)


def make_chunk(
    document_id,
    *,
    family_id,
    revision_label,
    usage_status,
    approval_status="approved",
    scope="",
    document_kind="subsystem_design",
    evidence_role="design_target",
    access_scope="internal",
    position_kind="pdf_page",
    title="Interlock design",
    chunk_id=None,
):
    return KnowledgeChunk(
        chunk_id=chunk_id or f"{document_id}:1",
        document_id=document_id,
        document_title=title,
        text="The interlock trips at 8 GeV.",
        source_path="data/l0_raw/interlock.pdf",
        document_version=revision_label,
        language="en",
        category="control_system",
        topic="interlock",
        page_start=1,
        page_end=1,
        family_id=family_id,
        revision_label=revision_label,
        document_kind=document_kind,
        evidence_role=evidence_role,
        usage_status=usage_status,
        approval_status=approval_status,
        scope=scope,
        position_kind=position_kind,
        access_scope=access_scope,
    )


def interlock_catalog(tmp_path):
    path = tmp_path / "private-server-location.pdf"
    make_pdf(path)
    catalog = DocumentCatalog()
    old = make_chunk(
        "interlock-v1",
        family_id="shine-interlock",
        revision_label="2019",
        usage_status="historical",
        scope="shine@2019;interlock",
    )
    new = make_chunk(
        "interlock-v2",
        family_id="shine-interlock",
        revision_label="2024",
        usage_status="current",
        scope="shine@2024;interlock",
    )
    for chunk in (old, new):
        catalog.add(chunk, path)  # E5 collection
        catalog.add(chunk, path)  # Qwen collection
    catalog.finish()
    return catalog


def test_family_groups_revisions_and_reports_metadata(tmp_path):
    catalog = interlock_catalog(tmp_path)
    snapshot = catalog.snapshot()
    assert snapshot["document_count"] == 2
    assert snapshot["indexed_section_count"] == 2
    document = next(
        row for row in snapshot["documents"] if row["document_id"] == "interlock-v2"
    )
    assert document["versions"] == ["2024"]
    assert document["revision_labels"] == ["2024"]
    assert document["family_ids"] == ["shine-interlock"]
    assert document["usage_statuses"] == ["current"]
    assert document["document_kinds"] == ["subsystem_design"]
    assert document["evidence_roles"] == ["design_target"]
    assert document["approval_statuses"] == ["approved"]
    assert document["access_scopes"] == ["internal"]
    assert document["position_kinds"] == ["pdf_page"]
    assert document["categories"] == ["control_system"]
    assert document["topics"] == ["interlock"]
    assert document["languages"] == ["en"]

    assert len(snapshot["families"]) == 1
    family = snapshot["families"][0]
    assert family["family_id"] == "shine-interlock"
    assert family["title"] == "Interlock design"
    assert family["revision_count"] == 2
    assert [row["document_id"] for row in family["revisions"]] == [
        "interlock-v1",
        "interlock-v2",
    ]
    old, new = family["revisions"]
    assert old["revision_label"] == "2019"
    assert old["usage_status"] == "historical"
    assert old["approval_status"] == "approved"
    assert old["scope"] == ["interlock", "shine@2019"]
    assert new["revision_label"] == "2024"
    assert new["usage_status"] == "current"


def test_catalog_never_exposes_paths(tmp_path):
    catalog = interlock_catalog(tmp_path)
    with TestClient(create_app(SimpleNamespace(catalog=catalog))) as client:
        response = client.get("/v1/rag/documents")
    payload = response.text
    assert response.status_code == 200
    assert "source_path" not in payload
    assert str(tmp_path) not in payload
    assert "private-server-location" not in payload
    assert json.loads(payload)["families"][0]["family_id"] == "shine-interlock"


def test_legacy_chunks_use_unknown_metadata_consistently(tmp_path):
    pdf_path = tmp_path / "legacy.pdf"
    make_pdf(pdf_path)
    md_path = tmp_path / "legacy.md"
    md_path.write_text("# Manual\n\nText.\n", encoding="utf-8")
    legacy = {
        "document_id": "legacy-design",
        "document_title": "Legacy design",
        "document_version": "2017",
        "category": "control_system",
        "topic": "ioc",
        "language": "en",
        "chunk_id": "legacy-design:1",
    }
    catalog = DocumentCatalog()
    catalog.add(SimpleNamespace(**legacy), pdf_path)
    markdown = {
        **legacy,
        "document_id": "legacy-manual",
        "document_title": "Legacy manual",
        "chunk_id": "legacy-manual:1",
    }
    catalog.add(SimpleNamespace(**markdown), md_path)
    catalog.finish()
    snapshot = catalog.snapshot()
    documents = {row["document_id"]: row for row in snapshot["documents"]}

    design = documents["legacy-design"]
    assert design["versions"] == ["2017"]  # legacy field is preserved
    assert design["revision_labels"] == ["unknown"]
    assert design["family_ids"] == ["legacy-design"]
    assert design["usage_statuses"] == ["unknown"]
    assert design["document_kinds"] == ["unknown"]
    assert design["evidence_roles"] == ["unknown"]
    assert design["approval_statuses"] == ["unknown"]
    assert design["access_scopes"] == ["unknown"]
    assert design["position_kinds"] == ["pdf_page"]
    assert documents["legacy-manual"]["position_kinds"] == ["section"]

    families = {row["family_id"]: row for row in snapshot["families"]}
    assert set(families) == {"legacy-design", "legacy-manual"}
    revision = families["legacy-design"]["revisions"][0]
    assert revision["revision_label"] == "unknown"
    assert revision["usage_status"] == "unknown"
    assert revision["approval_status"] == "unknown"
    assert revision["scope"] == []


def test_release_endpoint_reports_config_identity_and_counts(tmp_path):
    catalog = interlock_catalog(tmp_path)
    service = SimpleNamespace(
        catalog=catalog,
        config={"release_id": "kb-2.0.0", "build_id": "unrelated-config"},
    )
    with TestClient(create_app(service)) as client:
        response = client.get("/v1/rag/releases/current")
    assert response.status_code == 200
    assert response.json() == {
        "release_id": "kb-2.0.0",
        "build_id": "unknown",
        "document_count": 2,
        "revision_count": 2,
        "family_count": 1,
        "indexed_section_count": 2,
        "read_only_attachment_count": 0,
        "source": "runtime-config",
    }


def test_release_endpoint_does_not_invent_missing_identity():
    service = SimpleNamespace(catalog=None)
    with TestClient(create_app(service)) as client:
        response = client.get("/v1/rag/releases/current")
    assert response.json() == {
        "release_id": "unknown",
        "build_id": "unknown",
        "document_count": 0,
        "revision_count": 0,
        "family_count": 0,
        "indexed_section_count": 0,
        "read_only_attachment_count": 0,
        "source": "runtime-config",
    }


def test_restricted_chunk_is_not_listed_in_public_catalog(tmp_path):
    from accelerator_rag.rag.catalog import DocumentCatalog

    source = tmp_path / "restricted.pdf"
    source.write_bytes(b"%PDF-1.4")
    chunk = SimpleNamespace(
        document_id="restricted-rev",
        document_title="Restricted",
        document_version="1",
        category="control_system",
        topic="cybersecurity",
        language="zh",
        chunk_id="restricted-rev:1",
        family_id="restricted-family",
        revision_label="1",
        usage_status="pending_review",
        document_kind="subsystem_design",
        evidence_role="design_target",
        approval_status="unknown",
        access_scope="restricted",
        scope="",
        position_kind="pdf_page",
        position_label="page-1",
        effective_position_kind="pdf_page",
    )
    catalog = DocumentCatalog()
    catalog.add(chunk, source)
    catalog.finish()

    assert catalog.snapshot()["document_count"] == 0
    assert catalog.snapshot()["families"] == []


def test_new_office_formats_have_a_normalized_reader_url(tmp_path):
    from accelerator_rag.rag.catalog import DocumentCatalog

    source = tmp_path / "manual.docx"
    source.write_bytes(b"PK")
    chunk = SimpleNamespace(
        document_id="manual-rev",
        document_title="Manual",
        document_version="1",
        category="control_system",
        topic="timing",
        language="zh",
        chunk_id="manual-rev:1",
        family_id="manual-family",
        revision_label="1",
        usage_status="reference",
        document_kind="operation_manual",
        evidence_role="operating_step",
        approval_status="unknown",
        access_scope="internal",
        scope="",
        tags="series:shine-control-operation-manual-series;device:timing",
        position_kind="paragraph",
        position_label="paragraph-4",
        effective_position_kind="paragraph",
    )
    catalog = DocumentCatalog()
    catalog.add(chunk, source)
    catalog.finish()
    document = catalog.snapshot()["documents"][0]

    assert document["original_available"] is True
    assert document["reader_available"] is True
    assert document["document_url"] == "/v1/rag/documents/manual-rev"
    assert document["download_url"] == "/v1/rag/documents/manual-rev"
    assert document["reader_kind"] == "office"
    assert document["tags"] == [
        "device:timing",
        "series:shine-control-operation-manual-series",
    ]


def test_release_identity_reads_top_level_or_nested_config():
    top = release_identity_from_config({"release_id": "kb-2.0.0"})
    assert top.release_id == "kb-2.0.0"
    assert top.build_id == "unknown"
    nested = release_identity_from_config(
        {"release": {"release_id": "kb-2.0.1", "build_id": "build-7"}}
    )
    assert nested.release_id == "kb-2.0.1"
    # A build ID requires the K3 manifest, not an arbitrary config value.
    assert nested.build_id == "unknown"
    assert release_identity_from_config(None) == ReleaseIdentity()


def test_release_status_uses_explicit_catalog_snapshot_counts():
    identity = ReleaseIdentity(release_id="kb-2.0.0", build_id="build-42")
    snapshot = {
        "document_count": 3,
        "indexed_section_count": 9,
        "documents": [
            {"document_id": "a", "family_ids": ["fam"]},
            {"document_id": "b", "family_ids": ["fam"]},
            {"document_id": "c", "family_ids": ["other"]},
        ],
        "families": [{"family_id": "fam"}, {"family_id": "other"}],
    }
    assert release_status(identity, snapshot) == {
        "release_id": "kb-2.0.0",
        "build_id": "build-42",
        "document_count": 3,
        "revision_count": 3,
        "family_count": 2,
        "indexed_section_count": 9,
        "read_only_attachment_count": 0,
        "source": "runtime-config",
    }
