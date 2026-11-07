from accelerator_rag.evidence_pack.index import (
    port_covers,
    port_intervals,
    role_from_headers,
    version_markers,
)
from accelerator_rag.evidence_pack.schema import Atom, atom_id_for


def test_port_intervals_and_containment():
    assert port_intervals("45-48") == [(45, 48)]
    assert port_intervals("48-45") == [(45, 48)]
    assert port_intervals("1-4,7,9-12") == [(1, 4), (7, 7), (9, 12)]
    assert port_covers("33-48", "33-36")
    assert port_covers("1-4,9-12", "10")
    assert not port_covers("1-4", "5")
    assert not port_covers("33-48", "32-33")


def test_role_from_headers():
    assert role_from_headers(("测试内容", "测试结果")) == "test_result"
    assert role_from_headers(("测试项", "结论")) == "acceptance_conclusion"
    assert role_from_headers(("要求", "指标")) == "design_target"
    assert role_from_headers(("测试内容", "测试方法")) == "test_plan"
    assert role_from_headers(("a", "b")) == ""


def test_version_markers_order():
    markers = version_markers("第三版与其2024归档副本是否一致？")
    assert [(item.kind, item.value) for item in markers] == [
        ("ordinal", 3),
        ("archive", "2024"),
    ]
    markers = version_markers("两版是否一致")
    assert markers[0].kind == "both"


def test_alt_text_atom_serializes():
    atom = Atom(
        atom_id=atom_id_for(
            chunk_id="c1",
            locator_kind="paragraph",
            locator_label="p1#s1",
            excerpt="测试文本",
        ),
        chunk_id="c1",
        revision_id="r1",
        locator_kind="paragraph",
        locator_label="p1#s1",
        excerpt="测试文本",
        source_role="",
        evidence_role="fact_support",
        route="bm25",
        score=1.0,
        tokens=2,
    )
    assert atom.to_dict()["excerpt"] == "测试文本"
