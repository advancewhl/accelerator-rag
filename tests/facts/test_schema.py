"""Contract tests for the phase-2 fact schema."""

from __future__ import annotations

import pytest

from accelerator_rag.facts.schema import (
    UNKNOWN,
    Citation,
    Condition,
    EntityRef,
    Fact,
    FactError,
    FactSet,
    IdentityKey,
    check_citations,
    excerpt_in_text,
    make_fact_id,
)


def citation(**overrides) -> Citation:
    values = {
        "chunk_id": "rev-a:1",
        "revision_id": "rev-a",
        "locator_kind": "table_row",
        "locator_label": "S!A2:D2;A3:D4",
        "excerpt": "L3-CN01柜（DEVSW001） | 45-48 | 联锁FL-net | VLAN100",
        "source_role": "background_reference",
        "table_block_id": "rev-a:b:1",
        "row_number": 3,
    }
    values.update(overrides)
    return Citation(**values)


def device(scope=UNKNOWN, scope_source=UNKNOWN) -> EntityRef:
    return EntityRef(
        kind="device",
        raw_id="L3-CN01柜（DEVSW001）",
        scope=scope,
        scope_source=scope_source,
        keys=(
            IdentityKey(name="cabinet", value="L3-CN01柜", basis="prefix"),
            IdentityKey(name="device", value="DEVSW001", basis="parenthesized"),
        ),
    )


def attribute_fact(**overrides) -> Fact:
    values = {
        "fact_id": "F0123456789abcdef",
        "layer": "parameter",
        "fact_type": "attribute",
        "subject": device(),
        "attribute": "网络分配",
        "raw_value": "VLAN100",
        "value_kind": "enum",
        "comparator": "eq",
        "revision_id": "rev-a",
        "source_role": "background_reference",
        "evidence_role": "fact_support",
        "citation": citation(),
        "unknown_fields": ("conditions", "unit"),
        "extra": (("comparator_basis", "table_cell_assignment"),),
        "extracted_by": "W1",
    }
    values.update(overrides)
    return Fact(**values)


def test_attribute_fact_roundtrip():
    fact = attribute_fact()
    payload = fact.to_dict()
    assert payload["subject"]["keys"][1]["value"] == "DEVSW001"
    assert payload["object"] is None
    assert Fact.from_dict(payload) == fact


def test_unknown_fields_must_match_observed():
    with pytest.raises(FactError) as error:
        attribute_fact(unknown_fields=("unit",))
    assert error.value.code == "UNKNOWN_FIELDS_MISMATCH"

    with pytest.raises(FactError) as error:
        attribute_fact(unknown_fields=("attribute", "conditions", "unit"))
    assert error.value.code == "UNKNOWN_FIELDS_MISMATCH"


def test_conditions_are_not_inferred():
    condition = Condition(
        kind="measurement_endpoint",
        raw="4级门电路",
        citation=citation(
            locator_kind="table_header",
            excerpt="NI 9401 | 4级门电路 | <10 μs | <1 μs | 合格",
        ),
    )
    fact = attribute_fact(
        conditions=(condition,),
        unknown_fields=("unit",),
    )
    assert fact.conditions[0].raw == "4级门电路"


def test_relation_fact_requires_object():
    relation = attribute_fact(
        fact_type="relation",
        attribute="cable_terminal",
        raw_value="UN-FEL1:VA-01",
        value_kind="text",
        comparator="eq",
        object_ref=EntityRef(kind="device", raw_id="UN-FEL1:VA-01"),
    )
    payload = relation.to_dict()
    assert payload["object"]["raw_id"] == "UN-FEL1:VA-01"
    assert Fact.from_dict(payload) == relation

    with pytest.raises(FactError) as error:
        attribute_fact(fact_type="relation")
    assert error.value.code == "RELATION_OBJECT"


def test_attribute_fact_rejects_object():
    with pytest.raises(FactError) as error:
        attribute_fact(object_ref=EntityRef(kind="device", raw_id="X"))
    assert error.value.code == "ATTRIBUTE_OBJECT"


def test_entity_scope_source_requires_scope():
    with pytest.raises(FactError) as error:
        EntityRef(
            kind="device",
            raw_id="DEVSW001",
            scope=UNKNOWN,
            scope_source="table_title",
        )
    assert error.value.code == "ENTITY_SCOPE_SOURCE"


def test_table_row_citation_requires_row_identity():
    with pytest.raises(FactError) as error:
        citation(row_number=None)
    assert error.value.code == "CITATION_ROW_NUMBER"


def test_excerpt_must_be_verbatim():
    assert excerpt_in_text("45-48 | 联锁FL-net", "a 45-48 | 联锁FL-net b")
    assert excerpt_in_text("45-48……VLAN100", "x 45-48 y VLAN100 z")
    assert not excerpt_in_text("45-48 | VLAN1010", "45-48 | VLAN100")


def test_citation_check_reports_missing_chunk():
    fact = attribute_fact()
    problems = check_citations([fact], {"rev-a:1": "irrelevant"})
    assert problems and "not verbatim" in problems[0]
    problems = check_citations([fact], {})
    assert problems and "unknown chunk" in problems[0]


def test_fact_id_is_stable():
    first = make_fact_id(
        layer="parameter",
        fact_type="attribute",
        subject_raw="S",
        attribute="A",
        object_raw="",
        raw_value="V",
        revision_id="R",
        locator_label="L",
        excerpt="E",
    )
    second = make_fact_id(
        layer="parameter",
        fact_type="attribute",
        subject_raw="S",
        attribute="A",
        object_raw="",
        raw_value="V",
        revision_id="R",
        locator_label="L",
        excerpt="E",
    )
    assert first == second
    assert len(first) == 17


def test_factset_rejects_duplicates_and_roundtrips(tmp_path):
    fact = attribute_fact()
    facts = FactSet()
    facts.add(fact)
    with pytest.raises(FactError):
        facts.add(fact)
    path = tmp_path / "facts.jsonl"
    assert facts.write_jsonl(path) == 1
    restored = FactSet.read_jsonl(path)
    assert restored.sorted() == [fact]
