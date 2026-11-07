"""Contract tests for the W3 process/dependency fact layer."""

from __future__ import annotations

import pytest

from accelerator_rag.corpus.parsed_document import (
    ParsedBlock,
    ParsedDocument,
    SourcePosition,
)
from accelerator_rag.domain.knowledge import KnowledgeChunk

from accelerator_rag.facts import process
from accelerator_rag.facts.corpus import BASE, CorpusScope, load_scope
from accelerator_rag.facts.process import LAYER, extract
from accelerator_rag.facts.schema import UNKNOWN, check_citations


def block(
    revision_id: str,
    index: int,
    block_type: str,
    text: str,
    metadata: tuple[tuple[str, str], ...] = (),
):
    return ParsedBlock(
        block_id=f"{revision_id}:b:{index}",
        block_type=block_type,
        text=text,
        position=SourcePosition(
            kind="paragraph",
            start=index + 1,
            end=index + 1,
            label=f"paragraph-{index + 1}",
        ),
        heading_level=3 if block_type == "heading" else 0,
        metadata=metadata,
    )


def scope_for(
    revision_id: str,
    blocks: list[ParsedBlock],
    *,
    document_kind: str,
    evidence_role: str,
    title: str,
    chunk_text: str | None = None,
) -> CorpusScope:
    parsed = ParsedDocument(
        revision_id=revision_id,
        asset_id="asset-test",
        source_path=f"data/l0_raw/test/{revision_id}.docx",
        source_format="docx",
        title=title,
        blocks=tuple(blocks),
        parser_profile="test",
    )
    text = (
        chunk_text
        if chunk_text is not None
        else "\n\n".join(item.effective_text for item in blocks)
    )
    chunk = KnowledgeChunk(
        chunk_id=f"{revision_id}:c1",
        document_id=revision_id,
        document_title=title,
        text=text,
        source_path=parsed.source_path,
        document_version="v-test",
        language="zh",
        category="test",
        topic="test",
        page_start=1,
        page_end=1,
        document_kind=document_kind,
        evidence_role=evidence_role,
        position_kind="paragraph",
        position_label="paragraph-1",
        source_block_ids=",".join(item.block_id for item in blocks),
    )
    return CorpusScope(
        splits=("dev",),
        family_ids=("test-family",),
        families={"test-family": {"revision_ids": [revision_id]}},
        revisions={
            revision_id: {
                "document_kind": document_kind,
                "evidence_role": evidence_role,
                "title": title,
            }
        },
        chunks_by_revision={revision_id: (chunk,)},
        parsed_by_revision={revision_id: parsed},
        records_by_revision={revision_id: ()},
    )


def manual_scope(*texts: str, block_type: str = "paragraph") -> CorpusScope:
    revision_id = "manual-rev"
    blocks = [
        block(revision_id, index, block_type, text)
        for index, text in enumerate(texts)
    ]
    return scope_for(
        revision_id,
        blocks,
        document_kind="operation_manual",
        evidence_role="operating_step",
        title="测试操作手册",
    )


def table_scope(header: str, rows: list[str], *, kind: str = "test_report"):
    revision_id = "table-rev"
    table = "\n".join([header, " | ".join("---" for _ in header.split("|")), *rows])
    blocks = [block(revision_id, 0, "paragraph", table)]
    return scope_for(
        revision_id,
        blocks,
        document_kind=kind,
        evidence_role="test_result",
        title="测试报告",
        chunk_text=table,
    )


# ---------------------------------------------------------------------------
# Steps and sequence numbers
# ---------------------------------------------------------------------------


def test_layer_is_process():
    assert LAYER == "process"
    assert process.LAYER == "process"


def test_step_sequence_explicit_and_unknown():
    scope = manual_scope(
        "1、在中控OPI界面上双击archiver图标，打开archiverDesktop软件。",
        "通过右侧的导航栏选择CPC进入工艺系统的控制总页面。",
    )
    facts = extract(scope)
    steps = [fact for fact in facts if fact.fact_type == "step"]
    assert len(steps) == 2
    assert [dict(fact.extra)["sequence"] for fact in steps] == ["1", "UNKNOWN"]
    assert steps[0].raw_value == "在中控OPI界面上双击archiver图标，打开archiverDesktop软件"
    assert steps[1].raw_value.startswith("通过右侧的导航栏")
    assert all(fact.value_kind == "text" for fact in steps)
    assert all(fact.evidence_role == "fact_support" for fact in steps)


def test_step_label_is_not_a_step():
    scope = manual_scope("系统进入", block_type="list_item")
    assert [fact for fact in extract(scope) if fact.fact_type == "step"] == []


def test_step_text_is_verbatim_and_cited():
    text = "通过系统桌面的图标SHINE-AC（图一）进入SHINE控制的总页面。"
    scope = manual_scope(text)
    facts = extract(scope)
    assert len(facts) == 1
    fact = facts[0]
    assert fact.raw_value == text.rstrip("。")
    assert fact.citation.locator_kind == "paragraph"
    assert fact.citation.excerpt in scope.chunk_text()[fact.citation.chunk_id]
    assert check_citations(facts, scope.chunk_text()) == []


# ---------------------------------------------------------------------------
# Prerequisites only when written explicitly
# ---------------------------------------------------------------------------


def test_prerequisite_only_from_explicit_text():
    scope = manual_scope(
        "由于旁路设置的特殊性，对于旁路的操作需要获取相应的密码权限。",
        "联锁系统是加速器控制系统中的机器保护系统。",
    )
    facts = extract(scope)
    prerequisites = [fact for fact in facts if fact.fact_type == "prerequisite"]
    assert len(prerequisites) == 1
    fact = prerequisites[0]
    assert fact.raw_value == "需要获取相应的密码权限"
    assert fact.subject.kind == "procedure"
    assert fact.subject.raw_id == "旁路的操作"
    assert dict(fact.extra)["basis"] == "require"
    assert dict(fact.extra)["target_status"] == "unlocated"
    assert fact.object_ref is UNKNOWN
    assert fact.evidence_role == "condition"


def test_prerequisite_from_explicit_first_then_wording():
    scope = manual_scope("先确认设备已上电，再启动IOC程序。")
    prerequisites = [
        fact for fact in extract(scope) if fact.fact_type == "prerequisite"
    ]
    assert len(prerequisites) == 1
    assert dict(prerequisites[0].extra)["basis"] == "first"
    assert prerequisites[0].raw_value == "先确认设备已上电，再启动IOC程序"


def test_prerequisite_points_at_a_located_step():
    scope = manual_scope(
        "点击BYPASS按钮完成旁路的操作。",
        "对于旁路的操作需要获取相应的密码权限。",
    )
    prerequisites = [
        fact for fact in extract(scope) if fact.fact_type == "prerequisite"
    ]
    assert len(prerequisites) == 1
    fact = prerequisites[0]
    assert dict(fact.extra)["target_status"] == "located"
    assert fact.object_ref.raw_id == "点击BYPASS按钮完成旁路的操作"


def test_prerequisite_does_not_infer_from_descriptive_text():
    scope = manual_scope(
        "系统在各种不同的联锁控制模式下确保机器设备的安全运行。",
        "因此联锁保护逻辑不依赖于后台软件。",
    )
    facts = extract(scope)
    assert [fact for fact in facts if fact.fact_type == "prerequisite"] == []
    assert facts == []


# ---------------------------------------------------------------------------
# Test scope rows
# ---------------------------------------------------------------------------


def test_test_scope_row_records_condition_and_result():
    scope = table_scope(
        "项 | 测试条件 | 验收指标 | 测试结果 | 结论",
        ["NI 9401 | 4级门电路 | <10 μs | <1 μs | 合格"],
    )
    facts = [fact for fact in extract(scope) if fact.fact_type == "test_scope"]
    assert len(facts) == 1
    fact = facts[0]
    assert fact.subject.raw_id == "NI 9401"
    assert fact.attribute == "项"
    assert fact.raw_value == "<1 μs"
    assert fact.value_kind == "quantity"
    assert fact.comparator == "lt"
    assert fact.number == 1.0
    assert fact.unit == "μs"
    assert [(item.kind, item.raw) for item in fact.conditions] == [
        ("test_condition", "4级门电路")
    ]
    condition = fact.conditions[0]
    assert condition.citation.source_role == fact.source_role == "test_result"
    assert fact.citation.excerpt == "NI 9401 | 4级门电路 | <10 μs | <1 μs | 合格"
    assert fact.unknown_fields == ()
    assert dict(fact.extra)["acceptance_criterion"] == "<10 μs"
    assert dict(fact.extra)["conclusion"] == "合格"
    assert fact.citation.locator_kind == "table_row"
    assert fact.citation.table_block_id
    assert fact.citation.row_number == 1


def test_test_scope_outline_keeps_criterion_not_invented_result():
    scope = table_scope(
        "项 | 测试条件 | 验收指标 | 测试结果 | 结论",
        ["NI 9401 | 4级门电路 | <10 μs |  | "],
        kind="test_plan",
    )
    facts = [fact for fact in extract(scope) if fact.fact_type == "test_scope"]
    assert len(facts) == 1
    fact = facts[0]
    assert fact.raw_value == "<10 μs"
    assert dict(fact.extra)["raw_value_role"] == "acceptance_criterion"
    assert "test_result" not in dict(fact.extra)


def test_test_scope_without_result_or_criterion_is_not_emitted():
    scope = table_scope(
        "测试内容 | 测试结果",
        ["离子泵电压值读取 | "],
        kind="test_plan",
    )
    assert [fact for fact in extract(scope) if fact.fact_type == "test_scope"] == []


# ---------------------------------------------------------------------------
# Requirement links never guessed
# ---------------------------------------------------------------------------


def test_ocr_table_block_produces_no_facts():
    revision_id = "ocr-rev"
    table = (
        "项 | 测试条件 | 验收指标 | 测试结果 | 结论\n"
        "--- | --- | --- | --- | ---\n"
        "NI 9401 | 4级门电路 | <10 μs | <1 μs | 合格"
    )
    blocks = [
        block(
            revision_id,
            0,
            "table",
            table,
            metadata=(
                ("ocr", "tesseract"),
                ("ocr_table", "true"),
                ("manual_review_required", "true"),
            ),
        )
    ]
    scope = scope_for(
        revision_id,
        blocks,
        document_kind="test_report",
        evidence_role="test_result",
        title="OCR 测试报告",
        chunk_text=table,
    )
    assert extract(scope) == []


def test_garbled_ocr_text_produces_no_step():
    scope = manual_scope(
        "通 过 系 统 桌 面 的 图 标 点 击 进 入 控 制 总 页 面。"
    )
    assert extract(scope) == []


def test_source_role_distinguishes_plan_report_and_acceptance():
    plan = table_scope(
        "项 | 测试条件 | 验收指标 | 测试结果 | 结论",
        ["NI 9401 | 4级门电路 | <10 μs |  | "],
        kind="test_plan",
    )
    plan_fact = extract(plan)[0]
    assert plan_fact.source_role == "test_plan"
    assert dict(plan_fact.extra)["raw_value_role"] == "acceptance_criterion"

    report = table_scope(
        "项 | 测试条件 | 验收指标 | 测试结果 | 结论",
        ["NI 9401 | 4级门电路 | <10 μs | <1 μs | 合格"],
        kind="test_report",
    )
    report_fact = extract(report)[0]
    assert report_fact.source_role == "test_result"
    assert dict(report_fact.extra)["raw_value_role"] == "test_result"

    review = table_scope(
        "测试主项 | 测试子项 | 测试结果",
        ["真空控制功能 | 离子泵电压值读取 | 读取正常"],
        kind="review_opinion",
    )
    review_fact = extract(review)[0]
    assert review_fact.source_role == "acceptance_conclusion"
    assert dict(review_fact.extra)["raw_value_role"] == "acceptance_result"


def test_document_role_mapping_is_shared_by_every_layer():
    from accelerator_rag.facts.corpus import revision_source_role

    scope = table_scope("项 | 验收指标", ["NI 9401 | <10 μs"], kind="test_plan")
    revision_id = next(iter(scope.revisions))
    # The revision metadata still says ``test_result``; the shared resolver
    # must turn it into the document's own role for all three fact layers.
    assert scope.revisions[revision_id]["evidence_role"] == "test_result"
    assert revision_source_role(scope, revision_id) == "test_plan"

    review = table_scope("测试主项 | 测试结果", ["真空控制 | 正常"], kind="review_opinion")
    assert revision_source_role(review, next(iter(review.revisions))) == (
        "acceptance_conclusion"
    )


def test_requirement_link_skips_table_without_named_requirement():
    scope = table_scope(
        "测试pv | 验收指标 | 测试结果",
        ["HW-IMG2:RdPrs | 2Hz | >2Hz"],
    )
    facts = extract(scope)
    assert [fact for fact in facts if fact.fact_type == "test_scope"]
    assert [fact for fact in facts if fact.fact_type == "requirement_link"] == []


def test_requirement_link_from_acceptance_function_column():
    scope = table_scope(
        "测试项 | 验收功能 | 测试结果 | 结论",
        ["隆玛1kW恒温机柜监测与设置 | 能回读温度采集值 | 实现功能 | 完成"],
    )
    links = [
        fact for fact in extract(scope) if fact.fact_type == "requirement_link"
    ]
    assert len(links) == 1
    fact = links[0]
    assert fact.subject.raw_id == "隆玛1kW恒温机柜监测与设置"
    assert fact.object_ref.raw_id == "能回读温度采集值"
    assert fact.raw_value == "能回读温度采集值"
    assert dict(fact.extra)["link_basis"] == "same_table_row"
    assert dict(fact.extra)["test_result"] == "实现功能"


def test_requirement_link_from_named_metric_row():
    scope = table_scope(
        "快联锁样机 | 设计指标 | 验收指标 | 实测指标",
        ["单节点时间响应 | <10 μs | <10 μs | <1 μs"],
    )
    facts = extract(scope)
    assert [fact for fact in facts if fact.fact_type == "test_scope"] == []
    links = [fact for fact in facts if fact.fact_type == "requirement_link"]
    assert len(links) == 1
    fact = links[0]
    assert fact.subject.raw_id == "单节点时间响应"
    assert fact.object_ref.raw_id == "单节点时间响应"
    assert fact.raw_value == "<10 μs"
    assert fact.value_kind == "quantity"
    assert fact.comparator == "lt"
    assert dict(fact.extra)["test_result"] == "<1 μs"


def test_requirement_link_is_never_created_from_similar_values():
    scope = table_scope(
        "测试内容 | 验收指标 | 测试结果",
        ["离子泵电压值读取 | <10 μs | <1 μs"],
    )
    assert [
        fact
        for fact in extract(scope)
        if fact.fact_type == "requirement_link"
    ] == []


# ---------------------------------------------------------------------------
# Locator kinds stay faithful to §4.3
# ---------------------------------------------------------------------------


def test_table_rows_use_table_row_locator():
    scope = table_scope(
        "测试项 | 验收功能 | 测试结果 | 结论",
        ["隆玛1kW恒温机柜监测与设置 | 能回读温度采集值 | 实现功能 | 完成"],
    )
    facts = extract(scope)
    for fact in facts:
        assert fact.citation.locator_kind == "table_row"
        assert fact.citation.row_number == 1
        assert fact.citation.table_block_id == "table-rev:b:0"


def test_unknown_fields_are_exact():
    step_scope = manual_scope("通过系统桌面的图标SHINE-AC（图一）进入控制总页面。")
    step = extract(step_scope)[0]
    assert step.unknown_fields == ("conditions", "unit")
    table = table_scope(
        "项 | 测试条件 | 验收指标 | 测试结果 | 结论",
        ["NI 9401 | 4级门电路 | <10 μs | <1 μs | 合格"],
    )
    fact = extract(table)[0]
    assert fact.unknown_fields == ()


# ---------------------------------------------------------------------------
# Corpus integration (skipped when the frozen snapshot is absent)
# ---------------------------------------------------------------------------


@pytest.mark.corpus
def test_corpus_manual_and_self_test_report():
    if not BASE.exists():
        pytest.skip("rc.3 local snapshot is absent")
    revision_ids = [
        "shine-control-operation-manual-series-rev-0e94a5e4",
        "shine-prototype-constant-temperature-cabinet-acceptance-rev-11066a8f",
    ]
    scope = load_scope(
        ("dev", "val"),
        family_ids=[
            "shine-control-operation-manual-constant-temperature-cabinet",
            "shine-prototype-constant-temperature-cabinet-acceptance",
        ],
        revision_ids=revision_ids,
    )
    facts = extract(scope)
    steps = [fact for fact in facts if fact.fact_type == "step"]
    scopes = [fact for fact in facts if fact.fact_type == "test_scope"]
    links = [fact for fact in facts if fact.fact_type == "requirement_link"]
    assert steps, "the constant-temperature manual contributes steps"
    assert len(scopes) == 4
    assert len(links) == 4
    assert check_citations(facts, scope.chunk_text()) == []
