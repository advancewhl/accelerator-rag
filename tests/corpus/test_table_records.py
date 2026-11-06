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


def _split_sheet():
    rows = [("设备", "端口", "系统", "网络分配")]
    rows += [(f"SW{i:02d}", f"{i}-{i + 3}", "电源", f"VLAN{i}") for i in range(1, 41, 4)]
    table = TableData(
        rows=tuple(rows),
        header_rows=1,
        row_numbers=tuple(range(5, 5 + len(rows))),
        column_letters=("A", "B", "C", "D"),
    )
    block = ParsedBlock(
        block_id="switch-rev:b:t",
        block_type="table",
        text=table.text,
        position=SourcePosition(
            kind="cell_range",
            start=5,
            end=15,
            label="L3!A5:D15",
            locator=(("sheet", "L3"),),
        ),
        table=table,
        metadata=(("group", "L3-CN01柜（DEVSW001）"),),
    )
    parsed = ParsedDocument(
        revision_id="switch-rev",
        asset_id="asset-switch",
        source_path="data/l0_raw/incoming/x/switch.xlsx",
        source_format="xlsx",
        title="交换机配置表",
        blocks=(block,),
        parser_profile="openpyxl-cells-v1",
    )

    def chunk(cid, label):
        return KnowledgeChunk(
            chunk_id=cid,
            document_id="switch-rev",
            document_title="交换机配置表",
            text=table.text,
            source_path=parsed.source_path,
            document_version="1",
            language="zh",
            category="control_system",
            topic="network",
            page_start=1,
            page_end=1,
            position_kind="cell_range",
            position_label=label,
            source_block_ids=block.block_id,
            content_role="table",
        )

    return parsed, [chunk("c1", "L3!A5:D5;A6:D10"), chunk("c2", "L3!A5:D5;A11:D15")]


def test_split_table_rows_point_at_the_chunk_holding_them():
    parsed, chunks = _split_sheet()
    records = build_table_records(parsed, chunks)
    by_row = {record.row_number: record.chunk_id for record in records}
    assert by_row[6] == "c1" and by_row[10] == "c1"
    assert by_row[11] == "c2" and by_row[15] == "c2"
    assert records[0].values()["_group"] == "L3-CN01柜（DEVSW001）"


def test_port_range_and_group_rank_the_matching_row_first():
    parsed, chunks = _split_sheet()
    index = TableRecordIndex(build_table_records(parsed, chunks))
    hits = index.search("L3-CN01柜 DEVSW001 第 14 口是什么 VLAN")
    assert hits[0].record.values()["B"] == "13-16"
    assert "端口14" in hits[0].matched
    top = index.lookup_in_text("L3-CN01柜 DEVSW001 第 14 口是什么 VLAN")
    assert [record.values()["B"] for record in top] == ["13-16"]


def test_identifier_forms_match_exactly_without_prefix_guessing():
    parsed, chunks = _split_sheet()
    index = TableRecordIndex(build_table_records(parsed, chunks))
    # Group label component, case and punctuation variants are exact keys.
    assert index.search("l3-cn01 端口 2")[0].record.values()["B"] == "1-4"
    # Components are whole separator-delimited parts, never prefixes.
    assert index.search("CN0") == []
    assert index.search("SW0") == []


def test_unknown_named_identifier_blocks_partial_row_injection():
    parsed, chunks = _split_sheet()
    index = TableRecordIndex(build_table_records(parsed, chunks))
    query = "L9-CN01柜 DEVSW001 第 14 口"
    assert index.unmatched_identifiers(query) == ["L9-CN01"]
    assert index.lookup_in_text(query) == []
    # The ranked search still shows the partial rows for a UI to flag.
    assert index.search(query)
