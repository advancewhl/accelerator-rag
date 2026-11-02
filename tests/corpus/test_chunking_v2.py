"""Schema v2 chunking keeps revision identity and explicit positions."""

from hashlib import sha256
import json

import pytest

from accelerator_rag.corpus.chunking_v2 import (
    ChunkingV2Error,
    V2ChunkingConfig,
    chunk_parsed_document,
    chunking_v2_statistics,
)
from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    TableData,
)
from accelerator_rag.corpus.schema_v2 import RevisionRecord


SOURCE = (
    "data/l0_raw/incoming/2026-11-02-shine-control/资料/定时操作手册.docx"
)


def revision(**overrides):
    data = {
        "family_id": "shine-timing-manual",
        "revision_id": "shine-timing-manual-r3-202411",
        "title": "SHINE 定时操作手册（第三版）",
        "revision_label": "第三版-2024-11",
        "batch_id": "2026-11-02-shine-control",
        "original_asset_id": "asset-shine-timing-r3-original",
        "source_path": SOURCE,
        "source_format": "docx",
        "language": "zh",
        "document_kind": "operation_manual",
        "category": "control_system",
        "topic": "timing",
        "evidence_role": "operating_step",
        "usage_status": "reference",
        "approval_status": "unknown",
        "disposition": "text_index",
        "reason": "第三版操作手册，待确认现行状态。",
        "received_at": "2026-11-02",
        "parser_profile": "docx-blocks-v1",
        "scope": ["SHINE 定时系统"],
    }
    data.update(overrides)
    return RevisionRecord.from_dict(data)


def block(
    ordinal,
    block_type,
    text,
    start,
    end,
    *,
    level=0,
    table=None,
    label="",
    kind="section",
):
    position = SourcePosition(
        kind=kind,
        start=start,
        end=end,
        label=label or f"section-{start}",
    )
    return ParsedBlock(
        block_id=f"shine-timing-manual-r3-202411:b:{ordinal:04d}",
        block_type=block_type,
        text=text,
        position=position,
        heading_level=level,
        table=table,
    )


def document(blocks):
    return ParsedDocument(
        revision_id="shine-timing-manual-r3-202411",
        asset_id="asset-shine-timing-r3-original",
        source_path=SOURCE,
        source_format="docx",
        title="SHINE 定时操作手册（第三版）",
        blocks=tuple(blocks),
        parser_profile="docx-blocks-v1",
    )


def test_chunks_carry_revision_metadata_and_explicit_position():
    parsed = document(
        [
            block(0, "heading", "1. 查看状态", 1, 1, level=1),
            block(1, "paragraph", "打开界面后先确认状态。" * 5, 1, 1),
        ]
    )
    chunks = chunk_parsed_document(parsed, revision())

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.document_id == "shine-timing-manual-r3-202411"
    assert chunk.family_id == "shine-timing-manual"
    assert chunk.revision_label == "第三版-2024-11"
    assert chunk.asset_id == "asset-shine-timing-r3-original"
    assert chunk.document_kind == "operation_manual"
    assert chunk.usage_status == "reference"
    assert chunk.position_kind == "section"
    assert chunk.effective_position_kind == "section"
    assert chunk.position_label == "section-1"
    assert chunk.chunk_id.startswith("shine-timing-manual-r3-202411:")


def test_chunking_is_deterministic_and_ids_are_unique():
    parsed = document(
        [
            block(0, "heading", "1. 查看状态", 1, 1, level=1),
            block(1, "paragraph", "第一段。" * 10, 1, 1),
            block(2, "heading", "2. 检查抖动", 2, 2, level=1),
            block(3, "paragraph", "第二段。" * 10, 2, 2),
        ]
    )
    first = chunk_parsed_document(parsed, revision())
    second = chunk_parsed_document(parsed, revision())

    assert [chunk.chunk_id for chunk in first] == [
        chunk.chunk_id for chunk in second
    ]
    assert len({chunk.chunk_id for chunk in first}) == len(first)
    assert [chunk.page_start for chunk in first] == [1, 2]


def test_table_chunks_keep_header_and_spreadsheet_range():
    table = TableData(
        rows=(
            ("设备", "通道", "阈值"),
            ("BPM01", "A", "100 µs"),
            ("BPM02", "B", "120 µs"),
        ),
        header_rows=1,
        caption="表 1 通道阈值",
    )
    parsed = document(
        [
            block(0, "heading", "3. 阈值表", 3, 3, level=1),
            block(
                1,
                "table",
                table.text,
                3,
                3,
                table=table,
                label="Sheet1!A1:K3",
                kind="cell_range",
            ),
        ]
    )
    chunks = chunk_parsed_document(parsed, revision())

    table_chunks = [chunk for chunk in chunks if chunk.position_kind == "cell_range"]
    assert len(table_chunks) == 1
    chunk = table_chunks[0]
    assert "设备 | 通道 | 阈值" in chunk.text
    assert "BPM01 | A | 100 µs" in chunk.text
    assert chunk.position_label == "Sheet1!A1:K1;A2:K3"


def test_long_paragraph_is_bounded_without_crossing_revision():
    paragraph = "联锁响应时间应小于 100 µs。" * 120
    parsed = document([block(0, "paragraph", paragraph, 1, 1)])
    chunks = chunk_parsed_document(
        parsed,
        revision(),
        V2ChunkingConfig(max_chars=400, min_chars=100),
    )

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 400 for chunk in chunks)
    assert all(chunk.document_id == "shine-timing-manual-r3-202411" for chunk in chunks)
    assert all(chunk.page_start == chunk.page_end == 1 for chunk in chunks)


def test_mixed_position_kinds_in_one_group_are_rejected():
    parsed = document(
        [
            block(0, "paragraph", "第一段。", 1, 1),
            block(1, "paragraph", "第二段。", 2, 2, kind="slide"),
        ]
    )
    with pytest.raises(ChunkingV2Error, match="mix position kinds"):
        chunk_parsed_document(parsed, revision())


def test_revision_mismatch_is_rejected():
    parsed = document([block(0, "paragraph", "正文。", 1, 1)])
    with pytest.raises(ChunkingV2Error, match="revision_id"):
        chunk_parsed_document(
            parsed,
            revision(revision_id="other-revision"),
        )
    with pytest.raises(ChunkingV2Error, match="source_path"):
        chunk_parsed_document(
            parsed,
            revision(source_path=SOURCE.replace(".docx", ".pdf"), source_format="pdf"),
        )


def test_statistics_report_position_kinds():
    parsed = document(
        [
            block(0, "heading", "1. 查看状态", 1, 1, level=1),
            block(1, "paragraph", "第一段。" * 20, 1, 1),
        ]
    )
    stats = chunking_v2_statistics(chunk_parsed_document(parsed, revision()))

    assert stats["algorithm"] == "kb2-chunks-v1"
    assert stats["chunk_count"] == 1
    assert stats["by_position_kind"] == {"section": 1}
    assert stats["by_usage_status"] == {"reference": 1}


def test_table_cell_labels_use_physical_sheet_rows():
    from accelerator_rag.corpus.chunking_v2 import _table_chunk_label

    assert (
        _table_chunk_label("主控柜 (调整)!A2:K319", 1, 2, 15)
        == "主控柜 (调整)!A2:K2;A3:K16"
    )
    assert (
        _table_chunk_label("Sheet1!A1:K100", 1, 2, 15)
        == "Sheet1!A1:K1;A2:K15"
    )
    assert _table_chunk_label("表 1 通道阈值", 1, 2, 15) == "表 1 通道阈值"


def test_chunk_ids_do_not_reuse_legacy_hash_shape():
    parsed = document([block(0, "paragraph", "正文。", 1, 1)])
    chunk = chunk_parsed_document(parsed, revision())[0]
    identity = json.dumps(
        [
            "kb2-chunks-v1",
            {"max_chars": 1200, "min_chars": 300, "max_heading_level": 2},
            chunk.document_id,
            chunk.asset_id,
            chunk.position_kind,
            chunk.page_start,
            chunk.page_end,
            0,
            chunk.text,
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected = f"{chunk.document_id}:{sha256(identity.encode()).hexdigest()}"
    assert chunk.chunk_id == expected
