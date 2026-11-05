"""Row records preserve sheet, physical row and exact identifier lookup."""

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    TableData,
)
from accelerator_rag.corpus.table_records import (
    TableRecordIndex,
    build_table_records,
)
from accelerator_rag.domain.knowledge import KnowledgeChunk


SOURCE = "data/l0_raw/incoming/2026-11-02-shine-control/资料/端子表.xlsx"


def table_document():
    table = TableData(
        rows=(
            ("设备", "端子号", "信号名"),
            ("BPM01", "X09", "SR:BPM01:X"),
            ("BPM02", "X09A", "SR:BPM02:X"),
        ),
        header_rows=1,
        row_numbers=(17, 18, 19),
        column_letters=("A", "B", "C"),
        merged_ranges=("A17:A18",),
    )
    block = ParsedBlock(
        block_id="terminal-rev:b:table",
        block_type="table",
        text=table.text,
        position=SourcePosition(
            kind="cell_range",
            start=17,
            end=19,
            label="主控柜!A17:C19",
            locator=(("sheet", "主控柜"), ("range", "A17:C19")),
        ),
        table=table,
    )
    return ParsedDocument(
        revision_id="terminal-rev",
        asset_id="asset-terminal",
        source_path=SOURCE,
        source_format="xlsx",
        title="端子对应表",
        blocks=(block,),
        parser_profile="openpyxl-cells-v1",
    )


def table_chunk(parsed):
    block = parsed.blocks[0]
    return KnowledgeChunk(
        chunk_id="terminal-rev:table-chunk",
        document_id=parsed.revision_id,
        document_title=parsed.title,
        text=block.text,
        source_path=SOURCE,
        document_version="3.8",
        language="zh",
        category="control_system",
        topic="wiring",
        page_start=1,
        page_end=1,
        position_kind="cell_range",
        position_label="主控柜!A17:C19",
        source_block_ids=block.block_id,
        content_role="table",
    )


def test_rows_keep_sheet_physical_row_and_chunk_pointer():
    parsed = table_document()
    chunk = table_chunk(parsed)
    records = build_table_records(parsed, [chunk])

    assert len(records) == 2
    assert records[0].sheet == "主控柜"
    assert records[0].row_number == 18
    assert records[0].headers == ("设备", "端子号", "信号名")
    assert records[0].values()["B"] == "X09"
    assert records[0].chunk_id == chunk.chunk_id
    assert records[1].row_number == 19


def test_exact_lookup_does_not_prefix_match_identifiers():
    index = TableRecordIndex(build_table_records(table_document()))

    assert [record.values()["B"] for record in index.lookup("X09")] == ["X09"]
    assert [record.values()["B"] for record in index.lookup("x09")] == ["X09"]
    assert [record.values()["B"] for record in index.lookup("X09A")] == ["X09A"]
    assert index.lookup("X0") == []


def test_lookup_in_text_and_revision_filter():
    index = TableRecordIndex(build_table_records(table_document()))

    records = index.lookup_in_text("请查询端子 X09 的接线")
    assert [record.values()["B"] for record in records] == ["X09"]
    assert [record.values()["B"] for record in index.lookup_in_text("X09.")] == [
        "X09"
    ]
    assert [record.values()["B"] for record in index.lookup_in_text("X09A。")] == [
        "X09A"
    ]
    assert index.lookup_in_text("X09", revision_ids={"other-rev"}) == []
