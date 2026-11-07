from dataclasses import asdict, dataclass
import json
import sys
from pathlib import Path

import numpy as np
import pymupdf
import pytest

from accelerator_rag.corpus.registry import DocumentRecord
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.evidence_pack.schema import (
    Atom,
    BudgetPolicy,
    Needs,
    atom_id_for,
    estimate_tokens,
)
from accelerator_rag.facts.schema import (
    Citation,
    EntityRef,
    Fact,
    FactSet,
    UNKNOWN,
)


@pytest.fixture
def record() -> DocumentRecord:
    return DocumentRecord(
        doc_id="shine-controls",
        title="SHINE controls",
        source_path="data/l0_raw/shine.pdf",
        category="control_system",
        topic="ioc",
        document_type="pdf",
        language="en",
        version="1",
        status="reference",
    )


@pytest.fixture
def chunk(record: DocumentRecord) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id="shine-controls:test",
        document_id=record.doc_id,
        document_title=record.title,
        text="EPICS IOC manages SR:BPM01:X via camonitor.",
        source_path=record.source_path,
        document_version=record.version,
        language=record.language,
        category=record.category,
        topic=record.topic,
        page_start=3,
        page_end=3,
    )


@pytest.fixture
def corpus_root(tmp_path: Path, record: DocumentRecord) -> Path:
    pdf_path = tmp_path / record.source_path
    pdf_path.parent.mkdir(parents=True)
    with pymupdf.open() as pdf:
        first = pdf.new_page()
        first.insert_text((72, 72), "SHINE uses EPICS for distributed controls.")
        first.insert_text((72, 120), "MySQL stores server and record information.")
        pdf.new_page()  # Blank physical page 2 must not renumber page 3.
        third = pdf.new_page()
        third.insert_text(
            (72, 72), "IOC startup submits installation path and IP address."
        )
        third.insert_text((72, 120), "SR:BPM01:X can be observed using camonitor.")
        pdf.save(pdf_path)
    registry = tmp_path / "data/documents/registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps([asdict(record)]), encoding="utf-8")
    return tmp_path


class FakeEmbedder:
    """Deterministic test vectors, explicitly unrelated to model quality."""

    def embed_documents(self, texts):
        return np.array(
            [[1.0, 0.0] if "startup" in text else [0.0, 1.0] for text in texts],
            dtype=np.float32,
        )

    def embed_query(self, text):
        return np.array([1.0, 0.0], dtype=np.float32)


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


# Actual local tokenizer fixture (no model files/download). Its deliberately
# small character vocabulary makes token-budget edge cases deterministic.
class PassageFixtureEmbedder(FakeEmbedder):
    max_seq_length = 512
    model_name = "fixture-tokenizer"

    def __init__(self, limit=512):
        from tokenizers import Tokenizer, models, pre_tokenizers, processors

        self.max_seq_length = limit
        self.tokenizer = Tokenizer(
            models.WordLevel({"[UNK]": 0, "[CLS]": 1, "[SEP]": 2}, unk_token="[UNK]")
        )
        self.tokenizer.pre_tokenizer = pre_tokenizers.Split("", behavior="isolated")
        self.tokenizer.post_processor = processors.TemplateProcessing(
            single="[CLS] $A [SEP]", special_tokens=[("[CLS]", 1), ("[SEP]", 2)]
        )
        self.encoded = []

    def tokenizer_contract(self):
        from hashlib import sha256

        return {
            "model": self.model_name,
            "max_seq_length": self.max_seq_length,
            "tokenizer_sha256": sha256(self.tokenizer.to_str().encode()).hexdigest(),
        }

    dimension = 2
    QUERY_TEMPLATE = "为这个句子生成表示以用于检索相关文章：{query}"

    def fingerprint(self):
        return {
            "requested_model_name": self.model_name,
            "weights_manifest_sha256": "fixture-weights",
            "model_config_sha256": "fixture-config",
            "config_files": {"pooling.json": "fixture-pooling"},
            "tokenizer_sha256": self.tokenizer_contract()["tokenizer_sha256"],
            "query_template": self.QUERY_TEMPLATE,
            "document_prefix": "",
            "dimension": self.dimension,
            "max_seq_length": self.max_seq_length,
            "resolved_local_model_path": "/nonexistent/fixture-model",
        }

    def body_tokens(self, text):
        e = self.tokenizer.encode(text, add_special_tokens=False)
        return e.ids, e.offsets

    def audit_inputs(self, texts):
        rows = []
        for text in texts:
            n = len(self.tokenizer.encode(text.strip()).ids)
            rows.append(
                {
                    "token_count": n,
                    "would_truncate": n > self.max_seq_length,
                    "truncated_token_count": max(0, n - self.max_seq_length),
                    "truncation_ratio": max(0, n - self.max_seq_length) / n,
                }
            )
        return rows

    def visible_input_prefix(self, text):
        text = text.strip()
        encoded = self.tokenizer.encode(text)
        if len(encoded.ids) <= self.max_seq_length:
            return text
        end = max(b for a, b in encoded.offsets[: self.max_seq_length - 1])
        return text[:end]

    def embed_token_safe_documents(self, texts):
        if any(r["would_truncate"] for r in self.audit_inputs(texts)):
            raise ValueError("exceeds model max_seq_length")
        self.encoded.extend(texts)
        return self.embed_documents(texts)


@pytest.fixture
def passage_embedder():
    return PassageFixtureEmbedder()


# ---------------------------------------------------------------------------
# Phase-3 evidence-pack fixtures
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


@dataclass(frozen=True)
class FakeChunk:
    chunk_id: str
    document_id: str
    text: str
    position_label: str = "p1"
    evidence_role: str = ""
    family_id: str = "fam"
    page_start: int = 1
    page_end: int = 1


def make_citation(
    *,
    chunk_id: str = "c1",
    revision_id: str = "rev-a",
    locator_kind: str = "table_row",
    locator_label: str = "t1r1",
    excerpt: str = "指标甲 | 60s",
    source_role: str = "design_target",
    table_block_id: str = "t1",
    row_number: int | None = 1,
) -> Citation:
    return Citation(
        chunk_id=chunk_id,
        revision_id=revision_id,
        locator_kind=locator_kind,
        locator_label=locator_label,
        excerpt=excerpt,
        source_role=source_role,
        table_block_id=table_block_id,
        row_number=row_number,
    )


def make_fact(
    fact_id: str = "F" + "0" * 16,
    *,
    layer: str = "parameter",
    fact_type: str = "attribute",
    subject: str = "指标甲",
    attribute: str = "指标甲",
    raw_value: str = "60",
    unit: str = "s",
    number: float | None = 60.0,
    source_role: str = "design_target",
    revision_id: str = "rev-a",
    chunk_id: str = "c1",
    excerpt: str = "指标甲 | 60s",
    value_kind: str = "quantity",
    comparator: str = "eq",
    object_ref: EntityRef | None = None,
    conditions=(),
    table_block_id: str = "t1",
    row_number: int = 1,
) -> Fact:
    citation = make_citation(
        chunk_id=chunk_id,
        revision_id=revision_id,
        excerpt=excerpt,
        source_role=source_role,
        table_block_id=table_block_id,
        row_number=row_number,
    )
    return Fact(
        fact_id=fact_id,
        layer=layer,
        fact_type=fact_type,
        subject=EntityRef(kind="module", raw_id=subject),
        attribute=attribute,
        raw_value=raw_value,
        value_kind=value_kind,
        comparator=comparator,
        revision_id=revision_id,
        source_role=source_role,
        evidence_role="fact_support",
        citation=citation,
        conditions=tuple(conditions),
        object_ref=object_ref or UNKNOWN,
        number=number if number is not None else UNKNOWN,
        unit=unit if unit else UNKNOWN,
        unknown_fields=("conditions",) if not conditions else (),
        extracted_by="test",
    )


def make_fact_atom(fact: Fact, *, score: float = 1.0) -> Atom:
    return Atom(
        atom_id=atom_id_for(
            chunk_id=fact.citation.chunk_id,
            locator_kind=fact.citation.locator_kind,
            locator_label=fact.citation.locator_label,
            excerpt=fact.citation.excerpt,
            row_number=fact.citation.row_number,
            table_block_id=fact.citation.table_block_id,
            evidence_role=fact.evidence_role,
        ),
        chunk_id=fact.citation.chunk_id,
        revision_id=fact.revision_id,
        locator_kind=fact.citation.locator_kind,
        locator_label=fact.citation.locator_label,
        excerpt=fact.citation.excerpt,
        source_role=fact.source_role,
        evidence_role=fact.evidence_role,
        route="fact",
        score=score,
        tokens=estimate_tokens(fact.citation.excerpt),
        row_number=fact.citation.row_number,
        table_block_id=fact.citation.table_block_id,
        fact_ids=(fact.fact_id,),
    )


def make_row_atom(
    chunk_id: str = "c1",
    *,
    revision_id: str = "rev-a",
    excerpt: str = "设备 | 端口 | 系统\nCAB-A-CN01柜（DEVXSW02） | 45-48 | 系统甲",
    row_number: int = 1,
    table_block_id: str = "t1",
    source_role: str = "",
    score: float = 1.0,
) -> Atom:
    return Atom(
        atom_id=atom_id_for(
            chunk_id=chunk_id,
            locator_kind="table_row",
            locator_label=f"t1r{row_number}",
            excerpt=excerpt,
            row_number=row_number,
            table_block_id=table_block_id,
        ),
        chunk_id=chunk_id,
        revision_id=revision_id,
        locator_kind="table_row",
        locator_label=f"t1r{row_number}",
        excerpt=excerpt,
        source_role=source_role,
        evidence_role="fact_support",
        route="row_exact",
        score=score,
        tokens=estimate_tokens(excerpt),
        row_number=row_number,
        table_block_id=table_block_id,
    )


@dataclass
class FakeIndex:
    chunks: dict[str, FakeChunk]
    facts: FactSet
    rows: tuple = ()
    row_atoms: dict = None
    chunk_headers: dict = None
    facts_by_revision: dict = None
    facts_by_subject: dict = None
    paragraphs: dict = None

    def __post_init__(self):
        self.row_atoms = dict(self.row_atoms or {})
        self.chunk_headers = dict(self.chunk_headers or {})
        self.facts_by_revision = dict(self.facts_by_revision or {})
        self.facts_by_subject = dict(self.facts_by_subject or {})
        self.paragraphs = dict(self.paragraphs or {})
        for fact in self.facts.sorted():
            self.facts_by_revision.setdefault(fact.revision_id, []).append(
                fact.fact_id
            )
            self.facts_by_subject.setdefault(fact.subject.raw_id.casefold(), []).append(
                fact.fact_id
            )

    def chunk(self, chunk_id: str):
        return self.chunks[chunk_id]

    def revision_of(self, chunk_id: str) -> str:
        return self.chunks[chunk_id].document_id

    def chunk_tokens(self, chunk_id: str) -> int:
        return estimate_tokens(self.chunks[chunk_id].text)

    def rows_of(self, chunk_id: str):
        return tuple(row for row in self.rows if row.chunk_id == chunk_id)

    def all_paragraphs(self, revision_id: str):
        return tuple(self.paragraphs.get(revision_id, ()))

    def fact_atom(self, fact: Fact, *, score: float, route: str = "fact") -> Atom:
        return Atom(
            atom_id=atom_id_for(
                chunk_id=fact.citation.chunk_id,
                locator_kind=fact.citation.locator_kind,
                locator_label=fact.citation.locator_label,
                excerpt=fact.citation.excerpt,
                row_number=fact.citation.row_number,
                table_block_id=fact.citation.table_block_id,
                evidence_role=fact.evidence_role,
            ),
            chunk_id=fact.citation.chunk_id,
            revision_id=fact.revision_id,
            locator_kind=fact.citation.locator_kind,
            locator_label=fact.citation.locator_label,
            excerpt=fact.citation.excerpt,
            source_role=fact.source_role,
            evidence_role=fact.evidence_role,
            route=route,
            score=score,
            tokens=estimate_tokens(fact.citation.excerpt),
            row_number=fact.citation.row_number,
            table_block_id=fact.citation.table_block_id,
            fact_ids=(fact.fact_id,),
        )


@pytest.fixture
def fact_factory():
    return make_fact


@pytest.fixture
def fact_atom_factory():
    return make_fact_atom


@pytest.fixture
def row_atom_factory():
    return make_row_atom


@pytest.fixture
def index_factory():
    def build(chunks, facts=(), rows=(), paragraphs=None):
        fact_set = FactSet()
        for fact in facts:
            fact_set.add(fact)
        return FakeIndex(
            chunks={chunk.chunk_id: chunk for chunk in chunks},
            facts=fact_set,
            rows=tuple(rows),
            paragraphs=paragraphs or {},
        )

    return build


@pytest.fixture
def needs_factory():
    def build(
        *,
        route="cross_source",
        entities=(),
        relations=(),
        revision_ids=(),
        version_pair=(),
        comparison=False,
    ):
        return Needs(
            question_id="Q",
            route=route,
            entities=tuple(entities),
            relations=tuple(relations),
            revision_ids=tuple(revision_ids),
            version_pair=tuple(version_pair),
            comparison=comparison,
        )

    return build


@pytest.fixture
def policy_factory():
    def build(tokens=600, route="cross_source", parents=8, rounds=2, relations=3):
        return BudgetPolicy(
            route=route,
            base_tokens=tokens,
            max_parents=parents,
            max_rounds=rounds,
            tokens=tokens,
            relation_count=relations,
        )

    return build
