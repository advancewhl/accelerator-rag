"""Evidence locators use the chunk's position kind, not the file suffix."""

import json
from types import SimpleNamespace

import pytest

from accelerator_rag.domain.knowledge import RetrievalResult
from accelerator_rag.rag.context import EvidenceContextBuilder


def hit(position_kind, label, suffix):
    chunk = SimpleNamespace(
        chunk_id="chunk",
        document_id="rev",
        document_title="Doc",
        text="Evidence text.",
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/doc" + suffix,
        document_version="1",
        page_start=12,
        page_end=12,
        effective_position_kind=position_kind,
        position_label=label,
    )
    return RetrievalResult(1, 0.9, chunk, "test")


@pytest.mark.parametrize(
    ("kind", "label", "suffix", "expected"),
    [
        ("pdf_page", "page-12", ".pdf", "page"),
        ("paragraph", "paragraph-12", ".docx", "paragraph"),
        ("slide", "slide-12", ".pptx", "slide"),
        ("cell_range", "Sheet1!A2:K14", ".xlsx", "cell_range"),
        ("section", "section-12", ".md", "section"),
    ],
)
def test_context_reports_explicit_position(kind, label, suffix, expected):
    context = EvidenceContextBuilder().build([hit(kind, label, suffix)])
    record = json.loads(context.model_content)[0]

    assert record["locator_kind"] == expected
    assert record["position_label"] == label


def test_context_carries_governance_and_parse_quality():
    chunk = SimpleNamespace(
        chunk_id="chunk",
        document_id="rev",
        document_title="Doc",
        text="控制需求工作联系单第 3 页参数表。",
        source_path="data/l0_raw/incoming/2026-11-02-shine-control/资料/doc.pdf",
        document_version="1",
        page_start=3,
        page_end=3,
        effective_position_kind="pdf_page",
        position_label="page-3",
        document_kind="design_report",
        evidence_role="design_metric",
        usage_status="pending_review",
        approval_status="unknown",
        scope="SHINE 控制系统",
        section_path="3. 控制需求",
        content_role="table",
        extraction_method="ocr",
        review_status="required",
        formula_status="",
    )
    context = EvidenceContextBuilder().build(
        [RetrievalResult(1, 0.9, chunk, "test")]
    )
    record = json.loads(context.model_content)[0]

    assert record["document_kind"] == "design_report"
    assert record["evidence_role"] == "design_metric"
    assert record["usage_status"] == "pending_review"
    assert record["scope"] == "SHINE 控制系统"
    assert record["section_path"] == "3. 控制需求"
    assert record["content_role"] == "table"
    assert record["extraction_method"] == "ocr"
    assert record["review_status"] == "required"
    assert "formula_status" not in record
