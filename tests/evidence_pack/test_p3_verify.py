from accelerator_rag.evidence_pack.pack import Pack, coverage_for
from accelerator_rag.evidence_pack.schema import (
    Atom,
    Conflict,
    EntityNeed,
    RelationNeed,
    atom_id_for,
)
from accelerator_rag.evidence_pack.verify import verify
from accelerator_rag.verify.operators import run_operator


def _question(verdict="deterministic"):
    return {
        "base_id": "Q",
        "query": "CAB-A-CN01柜（DEVXSW02）的 45-48 端口系统与网络分配是什么？",
        "gold": {"verdict_class": verdict},
    }


def _row_atom(row_atom_factory):
    return row_atom_factory(
        "c1",
        excerpt="设备 | 端口 | 系统 | 网络分配\nCAB-A-CN01柜（DEVXSW02） | 45-48 | 系统甲 | VLAN9",
        row_number=1,
    )


def _pack(atom, needs, index):
    relevant = {atom.atom_id}
    coverage = coverage_for(
        (atom,), needs, index, {}, relevant, structural=set()
    )
    return Pack(
        atoms=(atom,),
        parents=({"chunk_id": atom.chunk_id, "tokens": atom.tokens},),
        tokens=atom.tokens,
        budget=1000,
        coverage=coverage,
        conflicts=(),
        unresolved=(),
    )


def test_not_evaluated_has_no_claims(row_atom_factory, index_factory, needs_factory):
    atom = _row_atom(row_atom_factory)
    index = index_factory([__import__("conftest", fromlist=["FakeChunk"]).FakeChunk("c1", "rev-a", atom.excerpt)])
    needs = needs_factory(
        route="exact_record",
        entities=(
            EntityNeed("CAB-A-CN01", "cab-a-cn01", "cabinet"),
            EntityNeed("DEVXSW02", "devxsw02", "device"),
            EntityNeed("45-48", "45-48", "port"),
        ),
        relations=(
            RelationNeed("provenance", True, "定位"),
            RelationNeed("value", True, "值"),
        ),
    )
    result = verify(index, _pack(atom, needs, index), needs, _question("rubric"))
    assert result.status == "not_evaluated"
    assert result.claims == []


def test_row_claim_and_answered(row_atom_factory, index_factory, needs_factory):
    atom = _row_atom(row_atom_factory)
    index = index_factory([__import__("conftest", fromlist=["FakeChunk"]).FakeChunk("c1", "rev-a", atom.excerpt)])
    needs = needs_factory(
        route="exact_record",
        entities=(
            EntityNeed("CAB-A-CN01", "cab-a-cn01", "cabinet"),
            EntityNeed("DEVXSW02", "devxsw02", "device"),
            EntityNeed("45-48", "45-48", "port"),
        ),
        relations=(
            RelationNeed("provenance", True, "定位"),
            RelationNeed("value", True, "值"),
            RelationNeed("scope", True, "范围"),
            RelationNeed("counterpart", True, "对端"),
        ),
    )
    result = verify(index, _pack(atom, needs, index), needs, _question())
    assert result.status == "answered"
    assert result.claims
    assert result.claims[0].anchor_hits == 3
    assert "VLAN9" in result.claims[0].text


def test_affecting_conflict_makes_partial(row_atom_factory, index_factory, needs_factory):
    atom = _row_atom(row_atom_factory)
    index = index_factory([__import__("conftest", fromlist=["FakeChunk"]).FakeChunk("c1", "rev-a", atom.excerpt)])
    needs = needs_factory(
        route="cross_source",
        relations=(
            RelationNeed("provenance", True, "定位"),
            RelationNeed("value", True, "值"),
        ),
    )
    pack = _pack(atom, needs, index)
    conflict = Conflict(
        conflict_id="C1",
        kind="value",
        subject="s",
        attribute="a",
        atom_ids=(atom.atom_id, atom.atom_id + "x"),
        resolution="affects_target",
        reason="测试",
    )
    pack = Pack(
        atoms=pack.atoms,
        parents=pack.parents,
        tokens=pack.tokens,
        budget=pack.budget,
        coverage=pack.coverage,
        conflicts=(conflict,),
    )
    result = verify(index, pack, needs, _question())
    assert result.status == "partial"
    assert any("冲突" in item for item in result.missing)


def test_version_diff_operator_replays(fact_factory, index_factory, needs_factory):
    left = Atom(
        atom_id=atom_id_for(
            chunk_id="c1", locator_kind="paragraph", locator_label="p1#s1",
            excerpt="界面甲：通过入口一进入",
        ),
        chunk_id="c1", revision_id="rev-a", locator_kind="paragraph",
        locator_label="p1#s1", excerpt="界面甲：通过入口一进入",
        source_role="", evidence_role="fact_support", route="revision",
        score=1.0, tokens=8,
    )
    right = Atom(
        atom_id=atom_id_for(
            chunk_id="c2", locator_kind="paragraph", locator_label="p1#s1",
            excerpt="界面甲：通过入口二进入",
        ),
        chunk_id="c2", revision_id="rev-b", locator_kind="paragraph",
        locator_label="p1#s1", excerpt="界面甲：通过入口二进入",
        source_role="", evidence_role="fact_support", route="revision",
        score=1.0, tokens=10,
    )
    index = index_factory(
        [
            __import__("conftest", fromlist=["FakeChunk"]).FakeChunk("c1", "rev-a", left.excerpt),
            __import__("conftest", fromlist=["FakeChunk"]).FakeChunk("c2", "rev-b", right.excerpt),
        ]
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
    coverage = coverage_for(
        (left, right), needs, index, {}, {left.atom_id, right.atom_id}, set()
    )
    pack = Pack(
        atoms=(left, right),
        parents=(),
        tokens=left.tokens + right.tokens,
        budget=1000,
        coverage=coverage,
    )
    alignment = (
        {
            "left_atom_id": left.atom_id,
            "right_atom_id": right.atom_id,
            "similarity": 0.5,
        },
    )
    question = {
        "base_id": "Q",
        "query": "界面甲在第一版与第二版中分别通过什么路径进入？",
        "gold": {"verdict_class": "deterministic"},
    }
    result = verify(index, pack, needs, question, alignment=alignment)
    assert result.status == "answered"
    assert result.claims
    assert all(claim.atom_ids or claim.fact_ids for claim in result.claims)
    assert result.operators
    record = result.operators[0]
    assert record["op"] == "version_diff"
    assert run_operator(record["op"], record["request"]) == record["response"]
