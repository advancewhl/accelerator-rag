from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pymupdf
import pytest

from accelerator_rag.corpus.registry import DocumentRecord
from accelerator_rag.domain.knowledge import KnowledgeChunk


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
