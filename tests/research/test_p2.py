"""Tests for the phase-2 P2 manual revision alignment prototype.

Unit tests use in-memory revision metadata and synthetic paragraph texts only.
Corpus tests read the frozen rc.3 snapshot and the built fact layer; they are
skipped when either is absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPES = ROOT / "scripts" / "research" / "prototypes"
if str(PROTOTYPES) not in sys.path:
    sys.path.insert(0, str(PROTOTYPES))

import common  # noqa: E402
import p2_manual_revision_align as p2  # noqa: E402

CORPUS = ROOT / "tmp" / "research-rc3" / "inventory" / "families.json"
CORPUS_READY = common.DEFAULT_FACTS.exists() and CORPUS.exists()


# ---------------------------------------------------------------------------
# revision mapping
# ---------------------------------------------------------------------------


def test_version_number_from_label():
    assert p2.version_number("操作手册 | SHINE定时界面操作手册") == 1
    assert p2.version_number("操作手册/第二版 | SHINE定时界面操作手册(20231206)") == 2
    assert p2.version_number("操作手册/第三版（202411） | 真空控制手册") == 3
    assert p2.version_number("归档文档（202310）/2023归档文件 | 定时系统") is None
    assert p2.version_number("归档文档（202410） | SHINE注入段真空控制操作手册") is None


def test_archive_period_from_label():
    assert (
        p2.archive_period("归档文档（202310）/2023控制系统硬线项目归档文件")
        == "202310"
    )
    assert p2.archive_period("归档文档（202410） | SHINE注入段真空控制操作手册") == "202410"
    assert p2.archive_period("操作手册/第三版（202411） | 某手册") is None


def test_revision_marker_mapping_basis():
    revisions = {
        "rev-a": {"revision_label": "操作手册 | 手册甲", "document_kind": "operation_manual"},
        "rev-b": {
            "revision_label": "操作手册/第二版 | 手册甲(20231206)",
            "document_kind": "operation_manual",
        },
        "rev-c": {
            "revision_label": "归档文档（202310）/2023归档文件 | 手册甲",
            "document_kind": "operation_manual",
        },
    }
    assert p2.revisions_for_marker("第一版", revisions) == (
        ["rev-a"],
        "only_non_archive_manual",
    )
    assert p2.revisions_for_marker("第二版", revisions) == (
        ["rev-b"],
        "label_ordinal",
    )
    assert p2.revisions_for_marker("2023归档副本", revisions) == (
        ["rev-c"],
        "archive_year",
    )


def test_first_version_requires_unique_non_archive_manual():
    revisions = {
        "rev-a": {"revision_label": "操作手册 | 手册甲", "document_kind": "operation_manual"},
        "rev-b": {"revision_label": "操作手册 | 手册甲（旧）", "document_kind": "operation_manual"},
        "rev-c": {
            "revision_label": "操作手册/第二版 | 手册甲",
            "document_kind": "operation_manual",
        },
    }
    question = {"query": "第一版与第二版是否一致？", "scope": {"mode": "global"}}
    with pytest.raises(p2.Unsupported):
        p2.resolve_pair(question, revisions)


def test_explicit_revisions_keep_given_order():
    revisions = {
        "rev-a": {"revision_label": "操作手册 | 手册甲", "document_kind": "operation_manual"},
        "rev-b": {
            "revision_label": "操作手册/第二版 | 手册甲",
            "document_kind": "operation_manual",
        },
    }
    question = {
        "query": "两版是否一致？",
        "scope": {"mode": "explicit_revisions", "revision_ids": ["rev-b", "rev-a"]},
    }
    sides, notes, mode = p2.resolve_pair(question, revisions)
    assert mode == "explicit_revisions"
    assert [side.revision_id for side in sides] == ["rev-b", "rev-a"]
    assert [side.role for side in sides] == ["第二版", "第一版"]
    assert any("scope.revision_ids" in note for note in notes)


def test_same_revision_on_both_sides_is_refused():
    revisions = {
        "rev-a": {"revision_label": "操作手册 | 手册甲", "document_kind": "operation_manual"},
    }
    question = {
        "query": "两版是否一致？",
        "scope": {"mode": "explicit_revisions", "revision_ids": ["rev-a", "rev-a"]},
    }
    with pytest.raises(p2.Unsupported):
        p2.resolve_pair(question, revisions)


def test_default_pair_is_first_two_versions():
    revisions = {
        "rev-a": {"revision_label": "操作手册 | 手册甲", "document_kind": "operation_manual"},
        "rev-b": {
            "revision_label": "操作手册/第二版 | 手册甲",
            "document_kind": "operation_manual",
        },
        "rev-c": {
            "revision_label": "归档文档（202310）/2023归档文件 | 手册甲",
            "document_kind": "operation_manual",
        },
    }
    question = {"query": "两版是否一致？", "scope": {"mode": "global"}}
    sides, _, mode = p2.resolve_pair(question, revisions)
    assert mode == "family_versions"
    assert [side.revision_id for side in sides] == ["rev-a", "rev-b"]


# ---------------------------------------------------------------------------
# anchors
# ---------------------------------------------------------------------------


def test_extract_terms_identifiers_concepts_and_probes():
    terms = p2.extract_terms(
        "第一版延时调节说明中的 APPLY 按键在第二版说明中是否仍被要求？",
        probe_identifiers=True,
    )
    assert terms.markers == ("第一版", "第二版")
    assert terms.probes == ("APPLY",)
    assert terms.identifiers == ()
    assert "延时调节" in terms.concepts
    assert "按键" in terms.concepts


def test_extract_terms_extends_segment_identifier():
    terms = p2.extract_terms(
        "InjCM 段真空控制页面需要监控哪些类型的设备？", probe_identifiers=False
    )
    assert "InjCM段" in terms.identifiers


def test_extract_terms_quoted_phrase_and_figure():
    terms = p2.extract_terms(
        "第二版在“给与各系统的信号控制”中把哪个系统新增进束测系统范围？",
        probe_identifiers=True,
    )
    assert terms.probes == ("给与各系统的信号控制",)
    terms = p2.extract_terms("图3 对恒温机柜总界面的五个标注列分别是什么？", probe_identifiers=False)
    assert "图3" in terms.identifiers


def test_quote_anchor_keeps_verbatim_phrase_when_present():
    terms = p2.QueryTerms(
        markers=(),
        quoted=("给与各系统的信号控制",),
        identifiers=(),
        concepts=(),
        probes=(),
    )
    anchors, notes = p2.build_anchors(terms, [["其中给与各系统的信号控制包含束测系统"]])
    assert [anchor.alternatives for anchor in anchors] == [("给与各系统的信号控制",)]
    assert notes == []


def test_quote_anchor_decomposes_missing_composite_phrase():
    terms = p2.QueryTerms(
        markers=(),
        quoted=("绿色（交换机第一状态灯灰色）/红色/白色",),
        identifiers=(),
        concepts=(),
        probes=(),
    )
    side_texts = [["状态灯显示为绿色表示正常，红色表示报警，白色表示预留"]]
    anchors, notes = p2.build_anchors(terms, side_texts)
    alternatives = [anchor.alternatives for anchor in anchors]
    assert ("绿色",) in alternatives
    assert ("红色",) in alternatives
    assert ("白色",) in alternatives
    assert all("交换机第一状态灯灰色" not in item for item in alternatives)
    assert any("交换机第一状态灯灰色" in note for note in notes)


def test_focal_sentence_skips_short_heading():
    text = "系统进入\n\n通过系统桌面的图标SHINE-AC进入SHINE控制的总页面。"
    anchors = [p2.Anchor("concept", "进入", ("进入",))]
    focal = p2._focal_sentence(text, anchors)
    assert "SHINE-AC" in focal


def test_action_sentences_keep_best_anchor_coverage():
    text = (
        "注入器段用户界面可以通过OPI工作站桌面图标进入。\n"
        "在菜单栏选择GUN与Timing按钮可以进入定时控制页面。"
    )
    anchors = [
        p2.Anchor("concept", "定时控制", ("定时控制",)),
        p2.Anchor("concept", "进入", ("进入",)),
    ]
    sentences = p2._action_sentences(text, anchors)
    assert sentences == ["在菜单栏选择GUN与Timing按钮可以进入定时控制页面"]


# ---------------------------------------------------------------------------
# corpus integration
# ---------------------------------------------------------------------------

corpus = pytest.mark.skipif(
    not CORPUS_READY, reason="rc.3 snapshot or data/facts/facts.jsonl is missing"
)


@pytest.fixture(scope="module")
def facts():
    return common.load_facts()


def _report(base_id: str, facts) -> dict:
    return p2.evaluate(common.get_question(base_id), facts)


@corpus
@pytest.mark.corpus
def test_tm01_path_reports_both_versions(facts):
    report = _report("S2-DEV-TM-01", facts)
    answer = report["answer"]
    assert report["status"] == "answered"
    assert "SHINE-AC" in answer or "导航栏" in answer
    assert "GUN" in answer or "Timing" in answer
    assert report["operators"], "version_diff must be recorded"


@corpus
@pytest.mark.corpus
def test_tm06_apply_removed(facts):
    report = _report("S2-DEV-TM-06", facts)
    assert report["status"] == "answered"
    assert "APPLY" in report["answer"]
    assert "未出现" in report["answer"]
    assert report["operators"]


@corpus
@pytest.mark.corpus
def test_vac12_figure_number_diff(facts):
    report = _report("S2-DEV-VAC-12", facts)
    answer = report["answer"]
    assert report["status"] == "answered"
    assert "图8" in answer and "图9" in answer
    assert "设备覆盖相同" in answer
    assert report["operators"]


@corpus
@pytest.mark.corpus
def test_dev_coverage_at_least_eight(facts):
    result = p2.evaluate_split("dev", facts)
    assert result["question_count"] == 33
    assert result["answered_or_partial"] >= 8


def test_explicit_scope_allows_more_than_two_revisions():
    revisions = {
        "rev-a": {"revision_label": "操作手册 | 手册甲", "document_kind": "operation_manual"},
        "rev-b": {
            "revision_label": "操作手册/第二版 | 手册甲",
            "document_kind": "operation_manual",
        },
        "rev-c": {
            "revision_label": "归档文档（202410） | 手册甲",
            "document_kind": "operation_manual",
        },
    }
    question = {
        "query": "2024归档副本相对前两版有什么新增说明？",
        "scope": {
            "mode": "explicit_revisions",
            "revision_ids": ["rev-a", "rev-b", "rev-c"],
        },
    }
    sides, _, mode = p2.resolve_pair(question, revisions)
    assert mode == "explicit_revisions"
    assert [side.revision_id for side in sides] == ["rev-a", "rev-b", "rev-c"]


def test_fallback_phrases_are_literal_noun_phrases():
    phrases = p2.fallback_phrases(
        "2024归档副本说明MPS输出信号在锁存与旁路两方面有什么限制？"
    )
    assert "输出信号" in phrases
    assert "锁存" in phrases
    assert "旁路" in phrases
    assert all(phrase[0] not in p2._FALLBACK_BOUNDARY for phrase in phrases)
    assert all(phrase[-1] not in p2._FALLBACK_BOUNDARY for phrase in phrases)


def test_one_sided_quote_is_kept_as_probe_anchor():
    terms = p2.QueryTerms(
        markers=(),
        quoted=("主要功能",),
        identifiers=(),
        concepts=(),
        probes=("主要功能",),
    )
    anchors, _ = p2.build_anchors(
        terms, [["第二版有主要功能章节"], ["第一版没有该章节"]], one_sided_quotes=True
    )
    assert [anchor.alternatives for anchor in anchors] == [("主要功能",)]
