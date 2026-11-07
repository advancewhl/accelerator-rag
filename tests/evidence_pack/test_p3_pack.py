from accelerator_rag.evidence_pack.pack import select_pack, select_parent_baseline
from accelerator_rag.evidence_pack.relations import complete
from accelerator_rag.evidence_pack.schema import RelationNeed

from conftest import FakeChunk


def _needs(needs_factory):
    return needs_factory(
        route="cross_source",
        entities=(),
        relations=(
            RelationNeed("provenance", True, "定位"),
            RelationNeed("requirement", True, "要求"),
            RelationNeed("test_result", True, "测试"),
        ),
        revision_ids=("rev-a", "rev-b"),
    )


def test_pack_covers_roles_and_stays_within_budget(
    fact_factory, fact_atom_factory, index_factory, needs_factory, policy_factory
):
    requirement = fact_factory(
        "F" + "1" * 16, source_role="design_target", raw_value="60", number=60.0
    )
    test = fact_factory(
        "F" + "2" * 16,
        source_role="test_result",
        revision_id="rev-b",
        chunk_id="c2",
        raw_value="60",
        number=60.0,
        excerpt="指标甲 | 60s",
    )
    chunks = [
        FakeChunk("c1", "rev-a", "指标甲 | 60s"),
        FakeChunk("c2", "rev-b", "指标甲 | 60s"),
    ]
    index = index_factory(chunks, [requirement, test])
    atoms = (fact_atom_factory(requirement), fact_atom_factory(test))
    pack = select_pack(
        atoms,
        _needs(needs_factory),
        index,
        policy_factory(tokens=300),
        query="指标甲 要求 测试结果",
        candidate_order=("c1", "c2"),
        conflicts=(),
        enumeration={},
    )
    assert pack.tokens <= pack.budget
    assert all(item.satisfied for item in pack.coverage if item.required)
    assert {item["chunk_id"] for item in pack.parents} == {"c1", "c2"}


def test_conflict_pair_is_kept_both_sides(
    fact_factory, fact_atom_factory, index_factory, needs_factory, policy_factory
):
    design = fact_factory(
        "F" + "3" * 16,
        source_role="design_target",
        raw_value="10",
        number=10.0,
        excerpt="指标甲 | 10s",
    )
    test = fact_factory(
        "F" + "4" * 16,
        source_role="test_result",
        revision_id="rev-b",
        chunk_id="c2",
        raw_value="20",
        number=20.0,
        excerpt="指标甲 | 20s",
    )
    chunks = [
        FakeChunk("c1", "rev-a", "指标甲 | 10s"),
        FakeChunk("c2", "rev-b", "指标甲 | 20s"),
    ]
    index = index_factory(chunks, [design, test])
    atoms = (fact_atom_factory(design), fact_atom_factory(test))
    completion = complete(
        index,
        _needs(needs_factory),
        "指标甲 要求 测试结果",
        atoms,
        family_ids={"fam"},
        revisions={"rev-a", "rev-b"},
    )
    assert completion.conflicts
    conflict = completion.conflicts[0]
    assert conflict.kind == "role"
    pack = select_pack(
        completion.atoms,
        _needs(needs_factory),
        index,
        policy_factory(tokens=400),
        query="指标甲 要求 测试结果",
        candidate_order=("c1", "c2"),
        conflicts=completion.conflicts,
        enumeration={},
    )
    assert set(conflict.atom_ids) <= {atom.atom_id for atom in pack.atoms}
    assert pack.tokens <= pack.budget


def test_conflict_not_one_sided_when_budget_too_small(
    fact_factory, fact_atom_factory, index_factory, needs_factory, policy_factory
):
    design = fact_factory(
        "F" + "5" * 16,
        source_role="design_target",
        raw_value="10",
        number=10.0,
        excerpt="指标甲 | 10s " + "描述" * 40,
    )
    test = fact_factory(
        "F" + "6" * 16,
        source_role="test_result",
        revision_id="rev-b",
        chunk_id="c2",
        raw_value="20",
        number=20.0,
        excerpt="指标甲 | 20s " + "说明" * 40,
    )
    chunks = [
        FakeChunk("c1", "rev-a", design.citation.excerpt),
        FakeChunk("c2", "rev-b", test.citation.excerpt),
    ]
    index = index_factory(chunks, [design, test])
    atoms = (fact_atom_factory(design), fact_atom_factory(test))
    completion = complete(
        index,
        _needs(needs_factory),
        "指标甲",
        atoms,
        family_ids={"fam"},
        revisions={"rev-a", "rev-b"},
    )
    pack = select_pack(
        completion.atoms,
        _needs(needs_factory),
        index,
        policy_factory(tokens=20),
        query="指标甲",
        candidate_order=("c1", "c2"),
        conflicts=completion.conflicts,
        enumeration={},
    )
    selected = {atom.atom_id for atom in pack.atoms}
    assert not (set(completion.conflicts[0].atom_ids) & selected)
    assert pack.unresolved
    assert pack.conflicts[0].resolution == "unresolved"


def test_fill_scorer_controls_non_witness_fill(
    fact_factory, fact_atom_factory, row_atom_factory, index_factory, needs_factory, policy_factory
):
    requirement = fact_factory("F" + "7" * 16, source_role="design_target")
    chunks = [
        FakeChunk("c1", "rev-a", "指标甲 | 60s"),
        FakeChunk("c2", "rev-a", "无关段落 A"),
        FakeChunk("c3", "rev-a", "无关段落 B"),
    ]
    index = index_factory(chunks, [requirement])
    filler_a = row_atom_factory(
        "c2", excerpt="无关段落 A", row_number=1, table_block_id="t2", score=1.0
    )
    filler_b = row_atom_factory(
        "c3", excerpt="无关段落 B", row_number=1, table_block_id="t3", score=1.0
    )
    atoms = (fact_atom_factory(requirement), filler_a, filler_b)
    needs = needs_factory(
        route="cross_source",
        relations=(RelationNeed("provenance", True, "定位"),),
    )
    pack = select_pack(
        atoms,
        needs,
        index,
        policy_factory(tokens=120),
        query="指标甲",
        candidate_order=("c1", "c2", "c3"),
        conflicts=(),
        enumeration={},
        fill_scorer=lambda atom, rank, selected: 9.0 if atom.chunk_id == "c3" else 0.0,
    )
    chosen = {atom.chunk_id for atom in pack.atoms}
    assert "c3" in chosen


def test_parent_baseline_respects_parent_limit(
    fact_factory, fact_atom_factory, index_factory, needs_factory, policy_factory
):
    facts = [
        fact_factory(
            "F" + str(index) * 16,
            source_role="design_target",
            chunk_id=f"c{index}",
            revision_id="rev-a",
            excerpt=f"要求 | {index}",
        )
        for index in range(1, 8)
    ]
    chunks = [
        FakeChunk(f"c{index}", "rev-a", f"要求 | {index}") for index in range(1, 8)
    ]
    index = index_factory(chunks, facts)
    atoms = tuple(fact_atom_factory(fact) for fact in facts)
    pack = select_parent_baseline(
        atoms,
        [
            __import__(
                "accelerator_rag.evidence_pack.schema", fromlist=["Candidate"]
            ).Candidate(chunk_id=f"c{number}", score=1.0 / number)
            for number in range(1, 8)
        ],
        needs_factory(
            route="cross_source",
            relations=(RelationNeed("provenance", True, "定位"),),
        ),
        index,
        policy_factory(tokens=5000, parents=8),
        query="要求",
        conflicts=(),
        enumeration={},
    )
    assert len(pack.parents) == 5
