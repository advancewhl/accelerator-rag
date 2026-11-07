"""Tests for the W5c requirement--test claim verification prototype."""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (
    ROOT / "src",
    ROOT / "scripts" / "research" / "prototypes",
):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import p3_requirement_test_claim as p3  # noqa: E402


FACTS_PATH = ROOT / "data" / "facts" / "facts.jsonl"
CORPUS_BASE = ROOT / "tmp" / "research-rc3"


# ---------------------------------------------------------------------------
# pure unit tests
# ---------------------------------------------------------------------------


def test_verdict_to_status_mapping():
    assert p3.verdict_to_status("成立") == "answered"
    assert p3.verdict_to_status("不成立") == "answered"
    assert p3.verdict_to_status("有条件成立") == "partial"
    assert p3.verdict_to_status("当前证据无法判断") == "insufficient"
    assert p3.verdict_to_status("超出能力") == "unsupported"
    with pytest.raises(ValueError):
        p3.verdict_to_status("未知")


def test_parse_quantity_keeps_printed_comparator_and_unit():
    assert p3.parse_quantity("<10 μs") == ("lt", Decimal("10"), "μs")
    assert p3.parse_quantity("小于100 μs") == ("lt", Decimal("100"), "μs")
    assert p3.parse_quantity("2Hz") == ("eq", Decimal("2"), "Hz")
    assert p3.parse_quantity("3.1Hz，7秒22个数") == (
        "eq",
        Decimal("3.1"),
        "Hz",
    )
    assert p3.parse_quantity("没有数值") is None


def test_requirement_op_minimum_requirement_for_table_assignment():
    class Fact:
        comparator = "eq"
        raw_value = "2Hz"
        extra = (("comparator_basis", "table_cell_assignment"),)

    assert p3.requirement_op(Fact()) == ("ge", "minimum_requirement")


def test_requirement_op_reads_explicit_text():
    class Upper:
        comparator = "eq"
        raw_value = "小于10 μs"
        extra = ()

    class Lower:
        comparator = "eq"
        raw_value = "不低于2Hz"
        extra = ()

    assert p3.requirement_op(Upper()) == ("lt", "explicit_text")
    assert p3.requirement_op(Lower()) == ("ge", "explicit_text")


def test_bound_implies_strict_upper_boundary():
    records: list[dict] = []
    assert p3.bound_implies(
        Decimal("1"), "lt", "μs", Decimal("10"), "lt", "us", records
    )[0] is True
    assert p3.bound_implies(
        Decimal("1000"), "lt", "ns", Decimal("10"), "lt", "us", records
    )[0] is True
    assert p3.bound_implies(
        Decimal("10"), "le", "μs", Decimal("10"), "lt", "us", records
    )[0] is False
    assert p3.bound_implies(
        Decimal("10"), "lt", "μs", Decimal("10"), "le", "us", records
    )[0] is True
    assert records, "unit_convert and boundary_compare must be recorded"


def test_bound_implies_strict_lower_boundary():
    records: list[dict] = []
    assert p3.bound_implies(
        Decimal("2"), "gt", "Hz", Decimal("2"), "ge", "Hz", records
    )[0] is True
    assert p3.bound_implies(
        Decimal("2"), "ge", "Hz", Decimal("2"), "gt", "Hz", records
    )[0] is False
    assert p3.bound_implies(
        Decimal("3"), "eq", "Hz", Decimal("2"), "ge", "Hz", records
    )[0] is True


def test_table_gaps_detects_missing_and_empty_result_cells():
    table = p3.TableView(
        revision_id="rev",
        chunk_id="chunk",
        block_id="block",
        label_prefix="paragraph-1#t1",
        header=("测试项", "验收功能", "测试结果", "结论"),
        rows=(
            p3.RowView(1, ("隆玛", "功能", "", ""), "row-1"),
            p3.RowView(2, ("盈凡", "功能"), "row-2"),
        ),
    )
    gaps = p3.table_gaps(table)
    assert len(gaps) == 4
    assert {gap["reason"] for gap in gaps} == {
        "empty_cell",
        "missing_column",
    }


def test_normalize_rows_inherits_merged_group_column():
    table = p3.TableView(
        revision_id="rev",
        chunk_id="chunk",
        block_id="block",
        label_prefix="slide-1#t1",
        header=("测试主项", "测试子项", "测试结果"),
        rows=(
            p3.RowView(1, ("真空控制功能", "电压", "读取正常"), "row-1"),
            p3.RowView(2, ("电流", "读取正常"), "row-2"),
        ),
    )
    rows = p3.normalize_rows(table)
    assert rows[1].cells == ("真空控制功能", "电流", "读取正常")


def test_item_key_normalises_read_back_pair():
    assert p3.item_key("离子泵电压值回读") == p3.item_key("离子泵电压值读取")
    assert p3.item_key("离子泵远程/本地控制及状态读取") != p3.item_key(
        "离子泵高压开关及状态读取"
    )


def test_model_token_splits_cabinet_model_from_verb():
    assert p3.model_token("威图1kW恒温机柜监测与设置") == "威图"
    assert p3.model_token("隆玛1kW恒温机柜监测与设置") == "隆玛"
    assert p3.model_token("MOXA控制器监测") == "MOXA"


def test_unique_cell_text_removes_duplicated_merged_cell():
    assert (
        p3.unique_cell_text(
            ("主要技术指标、实测结果和符合性", "主要技术指标、实测结果和符合性")
        )
        == "主要技术指标、实测结果和符合性"
    )


def test_has_measured_content_rejects_section_title():
    assert not p3.has_measured_content("主要技术指标、实测结果和符合性")
    assert not p3.has_measured_content(
        "二．主要技术指标、实测结果和符合性 1、真空控制功能 "
        "2、真空数据刷新率 3、IOC规范性测试"
    )
    assert p3.has_measured_content("真空数据刷新率 2Hz 合格")


# ---------------------------------------------------------------------------
# corpus integration
# ---------------------------------------------------------------------------


def _load_corpus_facts():
    if not FACTS_PATH.exists():
        pytest.skip("facts not built")
    if not CORPUS_BASE.exists():
        pytest.skip("rc.3 local snapshot is absent")
    return p3.common.load_facts(FACTS_PATH)


@pytest.mark.corpus
def test_anchor_scope_mismatch_endpoint_coverage():
    facts = _load_corpus_facts()
    question = p3.common.get_question("S3-DEV-CT-002")
    report = p3.evaluate(question, facts)
    assert report["status"] == "partial"
    assert report["research_label"] == "有条件成立"
    assert "0" in report["answer"]
    assert "20" in report["answer"] and "100" in report["answer"]
    assert report["operators"], "set_enumeration response must be embedded"
    assert report["operators"][0]["op"] == "set_enumeration"
    assert report["operators"][0]["response"]["value"]["missing"] == ["0"]


@pytest.mark.corpus
def test_anchor_acceptance_gap_missing_item():
    facts = _load_corpus_facts()
    question = p3.common.get_question("S3-DEV-VAC-005")
    report = p3.evaluate(question, facts)
    assert report["status"] == "answered"
    assert "离子泵远程/本地控制及状态读取" in report["answer"]
    assert "9" in report["answer"] and "8" in report["answer"]
    assert report["operators"], "set_enumeration response must be embedded"
    response = report["operators"][0]["response"]
    assert response["op"] == "set_enumeration"
    assert "离子泵远程/本地控制及状态读取" in response["value"]["missing"]


@pytest.mark.corpus
def test_anchor_verdict_rate_recompute():
    facts = _load_corpus_facts()
    question = p3.common.get_question("S3-DEV-VAC-009")
    report = p3.evaluate(question, facts)
    assert report["status"] == "answered"
    assert "达到" in report["answer"]
    assert "2.6" in report["answer"]
    assert "3.142857" in report["answer"]
    assert len(report["operators"]) == 2
    for record in report["operators"]:
        assert record["op"] == "boundary_compare"
        assert record["response"]["op"] == "boundary_compare"
        assert record["response"]["value"]["result"] is True
        assert "op_basis" not in record["response"]


@pytest.mark.corpus
def test_anchor_requirement_test_match():
    facts = _load_corpus_facts()
    question = p3.common.get_question("S3-VAL-FI-001")
    report = p3.evaluate(question, facts)
    assert report["status"] == "answered"
    assert report["research_label"] == "成立"
    assert "满足" in report["answer"]
    assert "154.3" in report["answer"] and "111.0" in report["answer"]
    assert report["operators"]
    assert {item["op"] for item in report["operators"]} == {
        "unit_convert",
        "boundary_compare",
    }
    assert all(
        item["response"]["value"]["result"] is True
        for item in report["operators"]
        if item["op"] == "boundary_compare"
    )


@pytest.mark.corpus
def test_val_mode_lists_complete_but_not_one_to_one():
    facts = _load_corpus_facts()
    question = p3.common.get_question("S3-VAL-FI-006")
    report = p3.evaluate(question, facts)
    assert report["status"] == "answered"
    assert report["research_label"] == "不成立"
    assert "不完全对应" in report["answer"]
    assert "波荡器调试" in report["answer"]
    assert report["operators"], "set_enumeration response must be embedded"
    response = report["operators"][0]["response"]
    assert response["op"] == "set_enumeration"
    assert response["value"]["missing"]
    assert response["value"]["counts"]["expected"] == 7
    assert response["value"]["counts"]["observed"] == 7


@pytest.mark.corpus
def test_all_dev_reports_at_least_six_answered_or_partial(capsys):
    _load_corpus_facts()
    p3.main(["--all", "--split", "dev"])
    captured = capsys.readouterr()
    summary = json.loads(captured.out)
    assert summary["deterministic_count"] == 8
    assert summary["answered_or_partial"] >= 6
    statuses = {
        item["question_id"]: item["status"] for item in summary["per_question"]
    }
    assert statuses["S3-DEV-CT-002"] == "partial"
    assert statuses["S3-DEV-VAC-005"] == "answered"
    assert statuses["S3-DEV-VAC-009"] == "answered"
    assert all(
        status in {"answered", "partial"}
        for question_id, status in statuses.items()
        if question_id.startswith("S3-DEV-")
        and question_id
        in {
            "S3-DEV-CT-002",
            "S3-DEV-CT-007",
            "S3-DEV-CT-010",
            "S3-DEV-CT-011",
            "S3-DEV-VAC-005",
            "S3-DEV-VAC-009",
            "S3-DEV-VAC-012",
            "S3-DEV-VAC-015",
        }
    )
