import pytest

from accelerator_rag.evidence_pack.schema import (
    Atom,
    PackError,
    cabinet_key,
    dedupe_atoms,
    entity_in_text,
    estimate_tokens,
    normalize_key,
)


def test_token_estimate_is_deterministic():
    assert estimate_tokens("测试 DEVXSW02 <1μs。") == 8
    assert estimate_tokens("") == 0


def test_cabinet_key_distinguishes_prefixes():
    assert cabinet_key("CAB-A-CN01") == cabinet_key("LA-CAB-A:CN-01")
    assert cabinet_key("CAB-A-CN01") == cabinet_key("CAB-A:CN-01")
    assert cabinet_key("CAB-A-CN01") != cabinet_key("EXT-CAB-A-CN01")
    assert cabinet_key("DCP-CN-01") == cabinet_key("LA-DCP:CN-01")


def test_entity_matching_kinds():
    assert entity_in_text("l3-cn01", "la-l3:cn-01", "cabinet")
    assert not entity_in_text("l3-cn01", "ext-l3-cn01", "cabinet")
    assert entity_in_text("devsw002", "la-ext-l3-cn:devsw002", "device")
    assert entity_in_text("devsw002", "devsw002", "device")
    assert not entity_in_text("45-48", "145-480", "port")
    assert entity_in_text("45-48", "port 45-48", "port")


def test_atom_validation_and_serialization(row_atom_factory):
    atom = row_atom_factory()
    payload = atom.to_dict()
    assert payload["locator_kind"] == "table_row"
    assert payload["row_number"] == 1
    assert payload["table_block_id"] == "t1"


def test_atom_rejects_table_row_without_block(row_atom_factory):
    atom = row_atom_factory()
    with pytest.raises(PackError):
        Atom(
            atom_id=atom.atom_id,
            chunk_id=atom.chunk_id,
            revision_id=atom.revision_id,
            locator_kind="table_row",
            locator_label=atom.locator_label,
            excerpt=atom.excerpt,
            source_role="",
            evidence_role="fact_support",
            route="row_exact",
            score=1.0,
            tokens=1,
            row_number=1,
        )


def test_dedupe_merges_fact_ids(fact_factory, fact_atom_factory):
    first = fact_factory("F" + "1" * 16)
    second = fact_factory(
        "F" + "2" * 16,
        attribute="指标乙",
        raw_value="3",
        excerpt="指标乙 | 3s",
        row_number=2,
    )
    atom_a = fact_atom_factory(first)
    atom_b = fact_atom_factory(second)
    merged = dedupe_atoms((atom_a, atom_b))
    assert len(merged) == 2
    assert merged[0].fact_ids


def test_normalize_key_keeps_case_out_of_comparison():
    assert normalize_key("DEVXSW02") == "devxsw02"
    assert normalize_key("ＡＢＣ") == "abc"
