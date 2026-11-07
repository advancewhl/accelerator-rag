"""Contract tests for the W1 parameter/condition fact layer."""

from __future__ import annotations

import pytest

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
    TableData,
)
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.facts import params
from accelerator_rag.facts.corpus import CorpusScope, load_scope
from accelerator_rag.facts.schema import UNKNOWN, check_citations

REVISION = "rev-a"


def _position(label: str = "paragraph-1", kind: str = "paragraph") -> SourcePosition:
    return SourcePosition(kind=kind, start=1, end=1, label=label)


def _paragraph(
    block_id: str,
    text: str,
    block_type: str = "paragraph",
    metadata: tuple[tuple[str, str], ...] = (),
):
    return ParsedBlock(
        block_id=block_id,
        block_type=block_type,
        text=text,
        position=_position(block_id.rsplit(":", 1)[-1]),
        heading_level=1 if block_type == "heading" else 0,
        metadata=metadata,
    )


def _table(block_id: str, rows: tuple[tuple[str, ...], ...], caption: str = ""):
    table = TableData(rows=rows, header_rows=1, caption=caption)
    return ParsedBlock(
        block_id=block_id,
        block_type="table",
        text=table.text,
        position=_position(block_id.rsplit(":", 1)[-1]),
        table=table,
    )


def _scope(
    blocks,
    *,
    source_path: str = "data/l0_raw/sample.docx",
    extraction_method: str = "native",
    review_status: str = "",
) -> CorpusScope:
    text = "\n\n".join(block.effective_text for block in blocks)
    chunk = KnowledgeChunk(
        chunk_id=f"{REVISION}:c1",
        document_id=REVISION,
        document_title="样机测试报告",
        text=text,
        source_path=source_path,
        document_version="v1",
        language="zh",
        category="acceptance",
        topic="test",
        page_start=1,
        page_end=1,
        position_kind="paragraph",
        position_label="paragraph-1",
        source_block_ids=",".join(block.block_id for block in blocks),
        extraction_method=extraction_method,
        review_status=review_status,
    )
    parsed = ParsedDocument(
        revision_id=REVISION,
        asset_id="asset-rev-a",
        source_path=source_path,
        source_format="docx",
        title="样机测试报告",
        blocks=tuple(blocks),
    )
    return CorpusScope(
        splits=("dev",),
        family_ids=("family-a",),
        families={"family-a": {}},
        revisions={REVISION: {"evidence_role": "test_result"}},
        chunks_by_revision={REVISION: (chunk,)},
        parsed_by_revision={REVISION: parsed},
        records_by_revision={REVISION: ()},
    )


def _facts(blocks, **kwargs):
    scope = _scope(blocks, **kwargs)
    facts = params.extract(scope)
    assert check_citations(facts, scope.chunk_text()) == []
    return facts


def _by_attribute(facts, attribute):
    return [fact for fact in facts if fact.attribute == attribute]


def test_units_and_comparators_are_kept_verbatim():
    facts = _facts(
        [
            _paragraph(
                f"{REVISION}:b:1",
                "样机验收指标为：单节点响应时间小于10 μs；节点间响应时间小于100 µs。",
            )
        ]
    )
    first = _by_attribute(facts, "单节点响应时间")[0]
    assert (first.value_kind, first.comparator) == ("quantity", "lt")
    assert (first.number, first.unit) == (10.0, "μs")
    assert first.raw_value == "小于10 μs"
    second = _by_attribute(facts, "节点间响应时间")[0]
    assert second.unit == "µs"  # micro sign is preserved, never normalised
    assert second.number == 100.0


def test_less_equal_is_distinct_from_less_than():
    facts = _facts(
        [
            _paragraph(f"{REVISION}:b:1", "报警阈值≤5 ℃"),
            _paragraph(f"{REVISION}:b:2", "报警阈值<5 ℃"),
        ]
    )
    comparators = sorted(fact.comparator for fact in facts)
    assert comparators == ["le", "lt"]
    assert {fact.unit for fact in facts} == {"℃"}


def test_center_tolerance_expands_only_from_printed_bounds():
    facts = _facts(
        [_paragraph(f"{REVISION}:b:1", "隧道要求环境温度25±0.5℃")]
    )
    fact = _by_attribute(facts, "隧道要求环境温度")[0]
    assert (fact.value_kind, fact.comparator) == ("range", "range")
    assert fact.number == 25.0
    assert (fact.low, fact.high, fact.unit) == (24.5, 25.5, "℃")
    assert ("derivation", "center±tolerance") in fact.extra
    assert ("tolerance", "0.5") in fact.extra


def test_heading_blocks_are_scanned():
    facts = _facts(
        [
            _paragraph(
                f"{REVISION}:b:1",
                "直线加速器隧道要求环境温度25±0.5℃",
                block_type="heading",
            )
        ]
    )
    fact = facts[0]
    assert fact.value_kind == "range"
    assert (fact.low, fact.high) == (24.5, 25.5)
    assert fact.citation.locator_kind == "paragraph"


def test_percent_range_keeps_its_unit():
    facts = _facts([_paragraph(f"{REVISION}:b:1", "风扇开度0%-100%")])
    fact = facts[0]
    assert (fact.value_kind, fact.comparator) == ("range", "range")
    assert (fact.low, fact.high, fact.unit) == (0.0, 100.0, "%")


def test_attribute_tail_does_not_eat_cue_characters():
    facts = _facts([_paragraph(f"{REVISION}:b:1", "响应小于10 μs")])
    assert facts[0].attribute == "响应"
    refreshed = _facts([_paragraph(f"{REVISION}:b:1", "刷新率不低于2Hz")])
    assert refreshed[0].attribute == "刷新率"
    assert refreshed[0].comparator == "ge"


def test_ocr_blocks_and_chunks_produce_no_facts():
    ocr_block = _paragraph(
        f"{REVISION}:b:1",
        "结果通过800m电缆传输，响应时间小于10 μs",
        metadata=(("ocr", "tesseract"), ("manual_review_required", "true")),
    )
    assert _facts([ocr_block]) == []

    scope = _scope(
        [_paragraph(f"{REVISION}:b:1", "响应时间小于10 μs")],
        extraction_method="ocr",
        review_status="required",
    )
    assert params.extract(scope) == []


def test_numbered_sentence_strips_clause_number():
    facts = _facts(
        [
            _paragraph(
                f"{REVISION}:b:1",
                "2. 真空参数监测刷新率不低于2Hz，完成。",
            )
        ]
    )
    fact = [item for item in facts if item.raw_value == "不低于2Hz"][0]
    assert fact.attribute == "真空参数监测刷新率"
    assert fact.comparator == "ge"


def test_mixed_review_required_chunk_keeps_native_blocks():
    native = _paragraph(f"{REVISION}:b:1", "响应时间小于10 μs")
    ocr = _paragraph(
        f"{REVISION}:b:2",
        "站 子 1 电压 800m",
        metadata=(("ocr", "tesseract"), ("manual_review_required", "true")),
    )
    scope = _scope(
        [native, ocr],
        extraction_method="mixed",
        review_status="required",
    )
    facts = params.extract(scope)
    assert [fact.attribute for fact in facts] == ["响应时间"]
    assert check_citations(facts, scope.chunk_text()) == []


def test_table_note_is_a_footnote_with_table_link():
    table = _table(
        f"{REVISION}:b:1",
        (("参数", "数值"), ("响应时间", "10 μs")),
    )
    note = _paragraph(
        f"{REVISION}:b:2", "注：表内数值均为实测值。", block_type="note"
    )
    facts = _facts([table, note])
    note_facts = [
        fact for fact in facts if fact.citation.locator_kind == "footnote"
    ]
    assert len(note_facts) == 1
    assert note_facts[0].attribute == "footnote"
    assert dict(note_facts[0].extra)["table_note_of"] == f"{REVISION}:b:1"


def test_table_block_prose_is_scanned_when_the_table_is_not_structured():
    table = _table(
        f"{REVISION}:b:1",
        (
            ("一、申请验收内容（按有关要求填写）",) * 3,
            ("样机验收指标：单节点响应时间小于10 μs",) * 3,
        ),
    )
    facts = _facts([table])
    fact = [item for item in facts if item.raw_value == "小于10 μs"][0]
    assert fact.attribute == "单节点响应时间"
    assert fact.citation.locator_kind == "paragraph"


def test_version_is_not_parsed_as_a_number():
    facts = _facts(
        [_paragraph(f"{REVISION}:b:1", "EPICS版本7.0.5及以上")]
    )
    fact = _by_attribute(facts, "EPICS版本")[0]
    assert fact.value_kind == "version"
    assert fact.comparator == "ge"
    assert fact.number is UNKNOWN
    assert fact.unit is UNKNOWN
    assert fact.unknown_fields == ("conditions", "unit")


def test_table_row_attribute_comes_from_the_column_header():
    table = _table(
        f"{REVISION}:b:1",
        (
            ("设备名称", "指标", "单位", "数量"),
            ("PXI机箱", "10Hz", "台", "2"),
        ),
    )
    facts = _facts([table])
    value = [fact for fact in facts if fact.raw_value == "10Hz"][0]
    assert value.attribute == "指标"
    assert value.comparator == "eq"
    assert ("comparator_basis", "table_cell_assignment") in value.extra
    assert ("attribute_source", "table_header") in value.extra
    assert ("document_context", "样机测试报告") in value.extra
    assert value.citation.locator_kind == "table_row"
    assert value.subject.raw_id == "PXI机箱"
    assert value.subject.kind == "device"

    header = [
        fact
        for fact in facts
        if fact.evidence_role == "header" and fact.attribute == "指标"
    ][0]
    assert header.citation.locator_kind == "table_header"
    assert header.citation.row_number == 0


def test_table_cell_assignment_is_an_equality_with_basis():
    table = _table(
        f"{REVISION}:b:1",
        (
            ("设备名称", "数量", "单位"),
            ("PXI机箱", "2", "台"),
        ),
    )
    facts = _facts([table])
    fact = [item for item in facts if item.raw_value == "2"][0]
    assert fact.comparator == "eq"
    assert ("comparator_basis", "table_cell_assignment") in fact.extra
    assert fact.unit == "台"
    assert ("unit_source", "row_column") in fact.extra


def test_stated_test_condition_and_its_own_citation():
    table = _table(
        f"{REVISION}:b:1",
        (
            ("项", "测试条件", "验收指标"),
            ("NI 9401", "4级门电路", "<10 μs"),
        ),
    )
    facts = _facts([table])
    fact = [item for item in facts if item.raw_value == "<10 μs"][0]
    assert fact.subject.raw_id == "NI 9401"
    assert fact.subject.kind == "test_item"
    assert len(fact.conditions) == 1
    condition = fact.conditions[0]
    assert (condition.kind, condition.raw) == ("test_condition", "4级门电路")
    assert condition.citation.locator_kind == "table_row"
    assert condition.citation.row_number == fact.citation.row_number
    assert "conditions" not in fact.unknown_fields


def test_absent_condition_stays_unknown():
    facts = _facts([_paragraph(f"{REVISION}:b:1", "响应时间小于10 μs")])
    fact = facts[0]
    assert fact.conditions == ()
    assert "conditions" in fact.unknown_fields


def test_unsupported_facets_are_not_filled():
    facts = _facts([_paragraph(f"{REVISION}:b:1", "模拟带宽500MHz")])
    fact = facts[0]
    assert fact.attribute == "模拟带宽"
    assert fact.comparator == "unknown"  # no explicit relation is invented
    assert fact.number == 500.0
    assert fact.unit == "MHz"
    assert fact.conditions == ()
    assert fact.unknown_fields == ("conditions",)


def test_empty_cells_produce_no_value():
    table = _table(
        f"{REVISION}:b:1",
        (
            ("设备名称", "指标"),
            ("A", ""),
            ("B", "10 μs"),
        ),
    )
    facts = _facts([table])
    values = [fact for fact in facts if fact.value_kind == "quantity"]
    assert len(values) == 1
    assert values[0].subject.raw_id == "B"
    assert all(fact.subject.raw_id != "A" for fact in facts)


def test_caption_and_note_keep_their_locator_kinds():
    facts = _facts(
        [
            _paragraph(
                f"{REVISION}:b:1", "表1 快联锁系统主要性能参数表", block_type="caption"
            ),
            _table(
                f"{REVISION}:b:2",
                (("项目", "指标"), ("A", "<10 μs")),
            ),
            _paragraph(f"{REVISION}:b:3", "图1 SHINE控制界面图标", block_type="caption"),
            _paragraph(f"{REVISION}:b:4", "注：测试室温为25 ℃。", block_type="note"),
        ]
    )
    context = [fact for fact in facts if fact.evidence_role == "provenance"]
    assert [fact.attribute for fact in context] == ["caption", "caption", "footnote"]
    assert [fact.citation.locator_kind for fact in context] == [
        "table_title",
        "figure_caption",
        "footnote",
    ]
    assert context[0].extra == (("caption_role", "table_title"),)
    assert context[0].citation.table_block_id == f"{REVISION}:b:2"
    assert context[0].citation.row_number == 1
    assert context[1].extra == (("caption_role", "figure_caption"),)
    assert all(fact.subject.kind == "document" for fact in context)
    assert all(fact.raw_value == fact.citation.excerpt for fact in context)


def test_facts_roundtrip_and_keep_layer():
    facts = _facts([_paragraph(f"{REVISION}:b:1", "响应时间小于10 μs")])
    assert facts
    assert all(fact.layer == params.LAYER == "parameter" for fact in facts)
    for fact in facts:
        assert fact.fact_type == "attribute"
        assert fact.extracted_by == "W1"


@pytest.mark.corpus
def test_corpus_dev_val_subset():
    from accelerator_rag.facts.corpus import BASE

    if not BASE.exists():
        pytest.skip("rc.3 snapshot is not present")
    scope = load_scope(
        ("dev", "val"),
        revision_ids=["shine-prototype-fast-interlock-acceptance-rev-dc14f6ea"],
    )
    facts = params.extract(scope)
    assert facts
    assert check_citations(facts, scope.chunk_text()) == []
    qualified = [
        fact
        for fact in facts
        if fact.attribute == "验收指标" and fact.raw_value == "<10 μs"
    ]
    assert qualified
    assert any(
        fact.subject.raw_id == "NI 9401"
        and fact.comparator == "lt"
        and any(
            condition.kind == "test_condition" and condition.raw == "4级门电路"
            for condition in fact.conditions
        )
        for fact in qualified
    )
