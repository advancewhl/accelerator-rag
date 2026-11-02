"""Unified intermediate representation and format adapters."""

import pytest

from accelerator_rag.corpus.markdown_parser import parse_markdown
from accelerator_rag.corpus.parsed_document import (
    ParsedDocument,
    SourcePosition,
    TableData,
    from_markdown_parsed,
    from_parsed_pdf,
)
from accelerator_rag.corpus.pdf_parser import (
    ParsedPdfDocument,
    PdfPage,
    PdfTextBlock,
)


def parsed_pdf():
    page = PdfPage(
        page_number=3,
        width=595.0,
        height=842.0,
        text="联锁响应时间应小于 100 µs。",
        char_count=18,
        blocks=[
            PdfTextBlock(
                block_number=0,
                block_type=0,
                bbox=(72.0, 72.0, 523.0, 120.0),
                text="联锁响应时间应小于 100 µs。",
            )
        ],
        image_count=0,
        warnings=[],
    )
    return ParsedPdfDocument(
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/联锁.pdf",
        file_name="联锁.pdf",
        page_count=3,
        metadata={"title": "联锁系统设计报告", "author": "SHINE"},
        pages=[page],
        warnings=[],
    )


def test_pdf_adapter_keeps_physical_page_and_is_deterministic():
    first = from_parsed_pdf(
        parsed_pdf(), revision_id="shine-interlock-design-r1-2018"
    )
    second = from_parsed_pdf(
        parsed_pdf(), revision_id="shine-interlock-design-r1-2018"
    )

    assert first.blocks == second.blocks
    assert first.blocks[0].position.kind == "pdf_page"
    assert first.blocks[0].position.start == 3
    assert first.title == "联锁系统设计报告"
    assert first.position_kinds == ("pdf_page",)
    assert first.blocks[0].block_id.startswith("shine-interlock-design-r1-2018:b:")


def test_document_round_trip():
    document = from_parsed_pdf(
        parsed_pdf(), revision_id="shine-interlock-design-r1-2018"
    )
    assert ParsedDocument.from_dict(document.to_dict()) == document


def test_empty_document_requires_a_warning():
    with pytest.raises(ValueError, match="空文档必须带有 warnings"):
        ParsedDocument(
            revision_id="empty-document",
            asset_id="asset-empty",
            source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/空.pdf",
            source_format="pdf",
            title="空文档",
            blocks=(),
        )
    document = ParsedDocument(
        revision_id="empty-document",
        asset_id="asset-empty",
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/空.pdf",
        source_format="pdf",
        title="空文档",
        blocks=(),
        warnings=("empty_document",),
    )
    assert document.text == ""


def test_markdown_adapter_emits_headings_paragraphs_tables_and_code(tmp_path):
    path = tmp_path / "manual.md"
    path.write_text(
        """# 定时操作手册

## 1. 查看状态

打开界面后先确认状态。

| 设备 | 通道 |
| --- | --- |
| BPM | A |

```bash
camonitor SR:BPM01:X
```
""",
        encoding="utf-8",
    )
    parsed = parse_markdown(
        path,
        source_path=(
            "data/l0_raw/incoming/2026-11-02-shine-control/资料/manual.md"
        ),
    )
    document = from_markdown_parsed(
        parsed, revision_id="shine-timing-manual-r1-2024"
    )

    types = [block.block_type for block in document.blocks]
    assert "heading" in types
    assert "paragraph" in types
    assert "table" in types
    assert "code" in types
    assert all(block.position.kind == "section" for block in document.blocks)
    table = next(block for block in document.blocks if block.block_type == "table")
    assert table.table.rows[0] == ("设备", "通道")
    assert table.table.rows[1] == ("BPM", "A")
    assert document.title == "定时操作手册"


def test_table_text_repeats_header_and_units():
    table = TableData(
        rows=(("通道", "阈值"), ("BPM01", "100 µs")),
        header_rows=1,
        caption="表 1 联锁阈值",
        units=("—", "µs"),
    )
    assert "表 1 联锁阈值" in table.text
    assert "通道 | 阈值" in table.text
    assert "BPM01 | 100 µs" in table.text
    assert table.data_rows() == (("BPM01", "100 µs"),)


def test_source_position_rejects_bad_ranges():
    with pytest.raises(ValueError, match="1 <= start <= end"):
        SourcePosition(kind="pdf_page", start=4, end=3)
    with pytest.raises(ValueError, match="position.kind"):
        SourcePosition(kind="page", start=1, end=1)
