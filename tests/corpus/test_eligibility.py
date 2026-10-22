from dataclasses import replace
import pytest
from accelerator_rag.corpus.eligibility import (
    assess_retrieval_eligibility,
    eligibility_audit,
    EligibilityConfig,
)


@pytest.mark.parametrize(
    "text,eligible",
    [
        ("谢 谢", False),
        ("THANK YOU", False),
        ("123", False),
        ("FRO21", False),
        ("8 GeV", True),
        ("10 µs", True),
        ("Spartan6 XC6SLX25", True),
        ("Normal EPICS IOC body text.", True),
        ("�" * 40 + " RF ", False),
        ("Formula � with plenty of normal explanation.", True),
    ],
)
def test_conservative_policy(chunk, text, eligible):
    assert assess_retrieval_eligibility(replace(chunk, text=text)).eligible is eligible


def test_attribution_and_config(chunk):
    good = replace(chunk, text="8 GeV")
    bad = replace(chunk, text="谢 谢", chunk_id="bad")
    eligible, audit = eligibility_audit([good, bad])
    assert eligible == [good] and audit["ineligible_chunks"] == 1
    assert audit["per_document_ineligible"] == {chunk.document_id: 1}
    assert audit["ineligible_by_reason"] == {"boilerplate_only": 1}
    with pytest.raises(ValueError):
        EligibilityConfig(replacement_ratio=2)


@pytest.mark.parametrize("ratio,expected", [(0.19, True), (0.20, False), (0.21, False)])
def test_replacement_ratio_boundary(chunk, ratio, expected):
    damaged = int(ratio * 100)
    text = "�" * damaged + "a" * (100 - damaged)
    assert assess_retrieval_eligibility(replace(chunk, text=text)).eligible is expected


def test_few_replacement_chars_do_not_remove_short_evidence(chunk):
    assert assess_retrieval_eligibility(replace(chunk, text="�" * 7 + "8 GeV")).eligible


def test_document_title_only_policy_preserves_short_technical_titles(chunk):
    title = "Guide to accelerator controls"
    assert not assess_retrieval_eligibility(
        replace(chunk, text=title, document_title=title)
    ).eligible
    assert assess_retrieval_eligibility(
        replace(chunk, text="8 GeV", document_title="8 GeV")
    ).eligible
    assert assess_retrieval_eligibility(
        replace(chunk, text="Spartan6 XC6SLX25", document_title="Spartan6 XC6SLX25")
    ).eligible
    assert assess_retrieval_eligibility(
        replace(
            chunk, text=title + " describes real control logic.", document_title=title
        )
    ).eligible
