"""W5a 原型测试：S1 线缆跨表关联（``p1_cable_cross_table``）。

分两层：

* 查询解析的单元测试——纯字符串，不读语料、不读事实；
* 语料集成测试——``@pytest.mark.corpus``，``data/facts/facts.jsonl`` 不存在时
  跳过。只读 dev/val 题目与事实文件，绝不触碰 sealed-test。
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPES = ROOT / "scripts" / "research" / "prototypes"
if str(PROTOTYPES) not in sys.path:
    sys.path.insert(0, str(PROTOTYPES))

import common  # noqa: E402
import p1_cable_cross_table as p1  # noqa: E402

FACTS = common.DEFAULT_FACTS
CORPUS_SKIP = pytest.mark.skipif(
    not Path(FACTS).exists(),
    reason="data/facts/facts.jsonl 未构建，跳过语料集成测试",
)

ANCHOR_QUESTIONS = ("S1-DEV-001", "S1-DEV-007", "S1-DEV-009", "S1-DEV-012")


# ---------------------------------------------------------------------------
# query parsing (pure strings)
# ---------------------------------------------------------------------------


def test_parse_cabinet_device_and_port_range():
    anchors = p1.parse_query(
        "L3-CN01柜（DEVSW002）交换机的 45-48 端口在配置表中分配给哪个系统？"
    )
    assert anchors.pairs == (("L3-CN01柜", "DEVSW002"),)
    assert anchors.ports == ("45-48",)
    assert anchors.cable_ids == ()
    assert anchors.e_numbers == ()


def test_parse_cabinet_with_colon_and_full_device():
    anchors = p1.parse_query(
        "L4:CN-17柜（LA-EXT-L4-CN:DEVSW005）的端口分配是否存在区间重叠？"
    )
    assert anchors.pairs == (
        ("L4:CN-17柜", "LA-EXT-L4-CN:DEVSW005"),
    )
    assert anchors.ports == ()


def test_parse_bare_cabinet_spelling():
    anchors = p1.parse_query(
        "L4-CN-07 柜 DEVSW002 段首的 SSA49 电缆，终端是哪台设备？"
    )
    assert anchors.pairs == (("L4-CN-07", "DEVSW002"),)
    assert "SSA49" in anchors.hints


def test_parse_full_cable_id():
    anchors = p1.parse_query(
        "线缆表中电缆编号 EXT-L3-CN01/VA02:DEVSW001-E007 这一行的完整记录？"
    )
    assert anchors.cable_ids == ("EXT-L3-CN01/VA02:DEVSW001-E007",)
    assert anchors.pairs == ()
    assert anchors.e_numbers == ()


def test_parse_e_range_and_single_numbers():
    anchors = p1.parse_query(
        "L3-CN03柜（DEVSW004）线缆表中 E028 之后是否列出了 E029–E036？"
        "表里如何过渡到 E037？"
    )
    assert anchors.pairs == (("L3-CN03柜", "DEVSW004"),)
    assert anchors.e_ranges == ((29, 36),)
    assert anchors.e_numbers == (28, 37)
    assert anchors.target_e_numbers()[:8] == tuple(range(29, 37))


def test_parse_device_only():
    anchors = p1.parse_query(
        "同一台交换机 LA-BRK-CN:DEVSW002 在两张线缆表中都有记录。"
    )
    assert anchors.pairs == ()
    assert anchors.devices == ("LA-BRK-CN:DEVSW002",)


def test_parse_ignores_en_passant_tokens():
    """VLAN ids, E numbers and cabinet codes are not port ranges or devices."""

    anchors = p1.parse_query(
        "EXT-L3-CN06柜（DEVSW003）的 1-8 端口分配 VLAN1020，E001 与 E002 另计。"
    )
    assert anchors.ports == ("1-8",)
    assert anchors.devices == ()
    assert anchors.cable_ids == ()
    assert anchors.e_numbers == (1, 2)


def test_expand_spec():
    assert p1._expand_spec("9-16") == tuple(range(9, 17))
    assert p1._expand_spec("45") == (45,)
    assert p1._expand_spec("21～24") == (21, 22, 23, 24)
    assert p1._expand_spec("预留") == ()
    assert p1._expand_spec(None) == ()


def test_device_alias_requires_cabinet():
    # A question may print the qualified id while the row prints the short one.
    assert p1._device_matches("LA-EXT-L4-CN:DEVSW005", "DEVSW005")
    assert p1._device_matches("DEVSW005", "LA-EXT-L4-CN:DEVSW005")
    assert not p1._device_matches(
        "LA-A:DEVSW005", "LA-B:DEVSW007", allow_short=False
    )
    assert not p1._device_matches("DEVSW005", "DEVSW007")


def test_parse_without_anchors():
    anchors = p1.parse_query("这段端口的系统与网络分配是什么？")
    assert anchors.pairs == ()
    assert anchors.devices == ()
    assert anchors.ports == ()
    assert anchors.cable_ids == ()
    assert anchors.e_numbers == ()


# ---------------------------------------------------------------------------
# corpus integration
# ---------------------------------------------------------------------------


def _evaluate(base_id: str) -> dict:
    facts = common.load_facts(FACTS)
    question = common.get_question(base_id)
    return p1.evaluate(question, facts, FACTS)


def _assert_report(report: dict) -> None:
    assert report["operators"], "报告必须带算子请求/响应"
    assert report["evidence"], "报告必须带证据"
    assert report["recompute"]["facts_sha256"]
    for operator in report["operators"]:
        assert operator["op"]
        assert "request" in operator and "response" in operator
        assert operator["response"]["op"] == operator["op"]


@pytest.mark.corpus
@CORPUS_SKIP
def test_s1_dev_001_port_assignment():
    report = _evaluate("S1-DEV-001")
    assert report["status"] == "answered"
    assert "联锁FL-net" in report["answer"]
    assert "VLAN100" in report["answer"]
    _assert_report(report)


@pytest.mark.corpus
@CORPUS_SKIP
def test_s1_dev_007_balance_12_plus_4():
    report = _evaluate("S1-DEV-007")
    assert report["status"] == "answered"
    assert "12" in report["answer"] and "16" in report["answer"]
    assert "束测预留4" in report["answer"]
    assert any(
        operator["op"] == "set_enumeration"
        and operator["response"]["value"]["exact"] is True
        for operator in report["operators"]
    )
    _assert_report(report)


@pytest.mark.corpus
@CORPUS_SKIP
def test_s1_dev_009_exact_cable_row():
    report = _evaluate("S1-DEV-009")
    assert report["status"] == "answered"
    for value in (
        "E007",
        "LA-EXT-L3:CN-01",
        "LA-EXT-L3:VA-02",
        "LA-EXT-L3-CN:DEVSW001",
        "真空 VA02 串口服务器",
        "设备网",
    ):
        assert value in report["answer"]
    _assert_report(report)


@pytest.mark.corpus
@CORPUS_SKIP
def test_s1_dev_012_missing_numbers_and_reserved_row():
    report = _evaluate("S1-DEV-012")
    assert report["status"] == "answered"
    assert "E029–E036" in report["answer"]
    assert "工艺/PDU预留8" in report["answer"]
    assert any(
        operator["op"] == "set_enumeration"
        and "E029" in operator["response"]["value"]["missing"]
        and "E036" in operator["response"]["value"]["missing"]
        for operator in report["operators"]
    )
    _assert_report(report)


@pytest.mark.corpus
@CORPUS_SKIP
def test_s1_dev_004_switch_usage_without_vlan():
    """negative_boundary 必须是"用途/VLAN"口径，不是区间重叠口径。"""

    report = _evaluate("S1-DEV-004")
    assert report["status"] == "answered"
    assert "预留" in report["answer"]
    assert "网络分配列为空" in report["answer"]
    assert "重叠" not in report["answer"]
    assert any(
        operator["op"] == "port_range_membership"
        for operator in report["operators"]
    )
    _assert_report(report)


@pytest.mark.corpus
@CORPUS_SKIP
def test_s1_dev_034_duplicate_cable_number():
    report = _evaluate("S1-DEV-034")
    assert report["status"] == "answered"
    assert "E001" in report["answer"]
    assert "2 次" in report["answer"]
    assert "电源交换机" in report["answer"]
    assert "电源机柜智能PDU" in report["answer"]
    assert any(
        operator["op"] == "set_enumeration"
        and operator["response"]["value"]["duplicates"]
        for operator in report["operators"]
    )
    _assert_report(report)


@pytest.mark.corpus
@CORPUS_SKIP
def test_rubric_question_is_not_evaluated():
    report = _evaluate("S1-DEV-021")
    assert report["status"] == "not_evaluated"


@pytest.mark.corpus
@CORPUS_SKIP
def test_dev_split_coverage():
    facts = common.load_facts(FACTS)
    result = p1._all("dev", facts, FACTS)
    counts = result["status_counts"]
    claimable = counts.get("answered", 0) + counts.get("partial", 0)
    assert claimable >= 12, counts
    assert result["question_count"] == len(result["questions"])
    # Every reported question must be a deterministic S1 item.
    assert all(
        item["status"] != "not_evaluated" for item in result["questions"]
    )
