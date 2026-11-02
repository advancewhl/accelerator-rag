"""Source-bound development pilot; evidence checks are not semantic grading."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from accelerator_rag.corpus.eligibility import eligibility_audit
from accelerator_rag.ingestion import IngestionService
from accelerator_rag.evaluation.retrieval import normalize_evidence


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Evidence(Contract):
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    locator_kind: Literal["page", "section"]
    page: int = Field(ge=1)
    excerpt: str = Field(min_length=1)
    chunk_ids: list[str] = Field(min_length=1)


class EvidenceGroup(Contract):
    alternatives: list[Evidence] = Field(min_length=1)


class PilotItem(Contract):
    id: str = Field(min_length=1)
    category: Literal["pdf_control", "conditions", "versions", "diagnosis", "limits"]
    query: str = Field(min_length=10)
    expected_status: Literal["answered", "partial", "insufficient"]
    gold_answer: str = Field(min_length=1)
    must_cover: list[str] = Field(min_length=1)
    forbidden_claims: list[str] = Field(min_length=1)
    evidence_groups: list[EvidenceGroup] = Field(min_length=1)
    cluster: str = Field(min_length=1)
    overlaps_legacy: str | None
    human_review: Literal["pending"]


class Pilot(Contract):
    schema_version: Literal["validity-pilot-v2"]
    dataset_revision: str
    purpose: Literal["development_only"]
    independent_test_allowed: Literal[False]
    items: list[PilotItem] = Field(min_length=50, max_length=50)


def load_corpus(root: Path, pdf_root: Path):
    pdfs = IngestionService(
        pdf_root, registry_path=root / "data/documents/registry.json"
    ).ingest_all_registered_pdfs()
    markdown = IngestionService(
        root, registry_path="data/documents/registry-md.json"
    ).ingest_all_registered()
    documents = pdfs + markdown
    chunks, _ = eligibility_audit([c for d in documents for c in d.chunks])
    return documents, chunks


def matching_chunks(target: Evidence, chunks):
    excerpt = normalize_evidence(target.excerpt)
    return [
        c
        for c in chunks
        if (
            c.document_id == target.document_id
            and c.document_version == target.document_version
            and c.page_start <= target.page <= c.page_end
            and excerpt in normalize_evidence(c.text)
        )
    ]


def validate_pilot(pilot: Pilot, documents, chunks):
    """Fail on stale versions, wrong locators, invented excerpts or stale IDs."""
    if len({item.id for item in pilot.items}) != len(pilot.items):
        raise ValueError("duplicate item id")
    corpus = {d.record.doc_id: d for d in documents}
    for item in pilot.items:
        for group in item.evidence_groups:
            for target in group.alternatives:
                document = corpus[target.document_id]
                expected_kind = (
                    "section" if document.record.document_type == "md" else "page"
                )
                if target.locator_kind != expected_kind:
                    raise ValueError(f"{item.id}: wrong locator kind")
                if target.document_version != document.record.version:
                    raise ValueError(f"{item.id}: stale document version")
                pages = {p.page_number: p.text for p in document.parsed.pages}
                if target.page not in pages or normalize_evidence(
                    target.excerpt
                ) not in normalize_evidence(pages[target.page]):
                    raise ValueError(f"{item.id}: excerpt absent from source locator")
                actual = {c.chunk_id for c in matching_chunks(target, chunks)}
                if not actual or actual != set(target.chunk_ids):
                    raise ValueError(
                        f"{item.id}: stale or unsearchable evidence chunks"
                    )


def evidence_coverage(item: PilotItem, chunks):
    return [
        any(matching_chunks(target, chunks) for target in group.alternatives)
        for group in item.evidence_groups
    ]
