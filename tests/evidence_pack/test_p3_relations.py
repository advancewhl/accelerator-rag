from accelerator_rag.evidence_pack.index import RowAtom
from accelerator_rag.evidence_pack.relations import (
    complete,
    relevant_atom_ids,
)
from accelerator_rag.evidence_pack.schema import RelationNeed

from conftest import FakeChunk


def _needs(needs_factory, *names, **kwargs):
    return needs_factory(
        route=kwargs.pop("route", "cross_source"),
        entities=kwargs.pop("entities", ()),
        relations=tuple(
            [RelationNeed("provenance", True, "定位")]
            + [RelationNeed(name, True, "测试") for name in names]
        ),
        **kwargs,
    )


def test_role_completion_adds_missing_test_result(
    fact_factory, fact_atom_factory, index_factory, needs_factory
):
    requirement = fact_factory("F" + "1" * 16, source_role="design_target")
    test = fact_factory(
        "F" + "2" * 16,
        source_role="test_result",
        revision_id="rev-b",
        chunk_id="c2",
        excerpt="指标甲 | 60s",
    )
    chunks = [
        FakeChunk("c1", "rev-a", "指标甲 | 60s"),
        FakeChunk("c2", "rev-b", "指标甲 | 60s"),
    ]
    index = index_factory(chunks, [requirement, test])
    completion = complete(
        index,
        _needs(needs_factory, "requirement", "test_result"),
        "指标甲 测试结果",
        (fact_atom_factory(requirement),),
        family_ids={"fam"},
        revisions={"rev-a", "rev-b"},
    )
    roles = {atom.source_role for atom in completion.atoms}
    assert "test_result" in roles


def test_role_conflict_is_detected_and_both_atoms_marked(
    fact_factory, fact_atom_factory, index_factory, needs_factory
):
    design = fact_factory(
        "F" + "3" * 16, source_role="design_target", raw_value="10", number=10.0,
        excerpt="指标甲 | 10s",
    )
    test = fact_factory(
        "F" + "4" * 16, source_role="test_result", revision_id="rev-b",
        chunk_id="c2", raw_value="20", number=20.0,
        excerpt="指标甲 | 20s",
    )
    chunks = [
        FakeChunk("c1", "rev-a", "指标甲 | 10s"),
        FakeChunk("c2", "rev-b", "指标甲 | 20s"),
    ]
    index = index_factory(chunks, [design, test])
    completion = complete(
        index,
        _needs(needs_factory, "requirement", "test_result"),
        "指标甲",
        (fact_atom_factory(design), fact_atom_factory(test)),
        family_ids={"fam"},
        revisions={"rev-a", "rev-b"},
    )
    assert len(completion.conflicts) == 1
    conflict = completion.conflicts[0]
    marked = {atom.atom_id for atom in completion.atoms if atom.conflict_group}
    assert set(conflict.atom_ids) <= marked


def test_enumeration_completion_pulls_all_rows(index_factory, row_atom_factory, needs_factory):
    rows = tuple(
        RowAtom(
            chunk_id="c1",
            revision_id="rev-a",
            family_id="fam",
            table_block_id="t1",
            sheet="s",
            row_number=number,
            headers=("设备", "端口", "系统"),
            cells=(("设备", "D"), ("端口", f"{number}-{number}"), ("系统", "S")),
            line=f"D | {number}-{number} | S",
            locator_label=f"t1r{number}",
        )
        for number in range(1, 4)
    )
    index = index_factory([FakeChunk("c1", "rev-a", "D | 1-1 | S")], [], rows=rows)
    atom = row_atom_factory("c1", excerpt="D | 1-1 | S", row_number=1)
    needs = needs_factory(
        route="cross_source",
        relations=(
            RelationNeed("provenance", True, "定位"),
            RelationNeed("enumeration", True, "完整"),
            RelationNeed("counterpart", True, "对端"),
        ),
    )
    completion = complete(
        index, needs, "D 全部端口", (atom,), family_ids={"fam"}, revisions={"rev-a"}
    )
    summary = completion.enumeration["t1"]
    assert summary["expected_rows"] == 3
    assert summary["complete"] is True
    assert len(summary["atom_ids"]) == 3


def test_version_alignment_pairs_similar_paragraphs(
    index_factory, needs_factory, row_atom_factory
):
    left_atom = row_atom_factory(
        "c1", revision_id="rev-a", excerpt="界面甲：系统桌面图标进入",
        row_number=1, table_block_id="t1",
    )
    right_atom = row_atom_factory(
        "c2", revision_id="rev-b", excerpt="界面甲：菜单栏 GUN 与 Timing 进入",
        row_number=1, table_block_id="t1",
    )
    index = index_factory(
        [FakeChunk("c1", "rev-a", left_atom.excerpt), FakeChunk("c2", "rev-b", right_atom.excerpt)],
        [],
        paragraphs={"rev-a": (left_atom,), "rev-b": (right_atom,)},
    )
    needs = needs_factory(
        route="document_explanation",
        relations=(
            RelationNeed("provenance", True, "定位"),
            RelationNeed("version_left", True, "左侧"),
            RelationNeed("version_right", True, "右侧"),
        ),
        version_pair=("rev-a", "rev-b"),
    )
    completion = complete(
        index,
        needs,
        "界面甲 第一版 第二版",
        (),
        family_ids={"fam"},
        revisions={"rev-a", "rev-b"},
    )
    assert completion.alignment
    assert completion.alignment[0]["left_atom_id"] == left_atom.atom_id


def test_relevant_atoms_require_object_or_terms(
    fact_factory, fact_atom_factory, index_factory, needs_factory
):
    fact = fact_factory("F" + "9" * 16, excerpt="指标甲 | 60s")
    other = fact_factory(
        "F" + "a" * 16, subject="无关对象", attribute="无关属性",
        excerpt="无关对象 | 1", row_number=2,
    )
    index = index_factory(
        [FakeChunk("c1", "rev-a", "指标甲 | 60s")], [fact, other]
    )
    atoms = (fact_atom_factory(fact), fact_atom_factory(other))
    relevant = relevant_atom_ids(
        atoms, needs_factory(route="cross_source"), "指标甲", index
    )
    assert fact_atom_factory(fact).atom_id in relevant
    assert fact_atom_factory(other).atom_id not in relevant
