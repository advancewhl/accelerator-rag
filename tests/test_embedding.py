import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from accelerator_rag.embedding import EmbeddingModel


@pytest.fixture
def model(monkeypatch):
    model = Mock()
    model.encode.return_value = np.array([1.0, 0.0])
    constructor = Mock(return_value=model)
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(
            SentenceTransformer=constructor,
        ),
    )
    embedder = EmbeddingModel()
    constructor.assert_called_once_with(
        "BAAI/bge-small-zh-v1.5",
        device="cpu",
        local_files_only=True,
        model_kwargs=None,
    )
    return embedder, model


@pytest.mark.parametrize("query", ["IOC startup", "SHINE 中 IOC 启动后提交哪些信息？"])
def test_exact_query_template_sent_to_model(model, query):
    embedder, encoder = model
    embedder.embed_query(f"  {query}  ")
    expected = f"为这个句子生成表示以用于检索相关文章：{query}"
    assert embedder.QUERY_TEMPLATE.format(query=query) == expected
    encoder.encode.assert_called_once_with(
        expected,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )


def test_documents_do_not_receive_query_instruction(model):
    embedder, encoder = model
    embedder.embed_documents(["IOC evidence"])
    assert encoder.encode.call_args.args == (["IOC evidence"],)


def test_empty_query_fails_before_encoding(model):
    embedder, encoder = model
    with pytest.raises(ValueError):
        embedder.embed_query(" \n ")
    encoder.encode.assert_not_called()


def test_tokenizer_audit_counts_special_tokens_and_truncation():
    from types import SimpleNamespace
    from accelerator_rag.embedding import EmbeddingModel

    calls = []

    class Model:
        max_seq_length = 5

        def __getitem__(self, index):
            return SimpleNamespace(do_lower_case=True)

        def tokenizer(self, texts, **kwargs):
            calls.append((texts, kwargs))
            return {"input_ids": [[101, *range(len(t.split())), 102] for t in texts]}

    embedder = object.__new__(EmbeddingModel)
    embedder._model = Model()
    rows = embedder.audit_inputs([" A B C D ", "word"])
    assert rows[0] == {
        "token_count": 6,
        "would_truncate": True,
        "truncated_token_count": 1,
        "truncation_ratio": 1 / 6,
    }
    assert not rows[1]["would_truncate"]
    assert calls[0][0][0] == "a b c d"
    assert (
        calls[0][1]["add_special_tokens"] is True and calls[0][1]["truncation"] is False
    )


def test_input_audit_document_language_attribution(chunk):
    from dataclasses import replace
    from accelerator_rag.embedding import (
        audit_embedding_inputs,
        document_embedding_text,
    )

    class Fixture:
        max_seq_length = 4

        def audit_inputs(self, texts):
            return [
                {
                    "token_count": len(t),
                    "would_truncate": len(t) > 4,
                    "truncated_token_count": max(0, len(t) - 4),
                    "truncation_ratio": max(0, len(t) - 4) / len(t),
                }
                for t in texts
            ]

    chunks = [
        chunk,
        replace(chunk, document_id="other", language="zh", chunk_id="other"),
    ]
    report = audit_embedding_inputs(Fixture(), chunks)
    assert report["total_chunks"] == report["chunks_exceeding_limit"] == 2
    assert report["by_language"]["zh"]["total_chunks"] == 1
    assert report["by_document"]["other"]["total_chunks"] == 1
    assert document_embedding_text(chunk) == chunk.document_title + "\n" + chunk.text


def test_token_count_at_limit_does_not_truncate():
    from types import SimpleNamespace
    from accelerator_rag.embedding import EmbeddingModel

    class Model:
        max_seq_length = 5

        def __getitem__(self, index):
            return SimpleNamespace(do_lower_case=False)

        def tokenizer(self, texts, **kwargs):
            return {"input_ids": [[101, 1, 2, 3, 102]]}

    e = object.__new__(EmbeddingModel)
    e._model = Model()
    assert e.audit_inputs(["example"])[0]["truncated_token_count"] == 0
    assert not e.audit_inputs(["example"])[0]["would_truncate"]


def test_safe_embedding_rejects_before_encode(model):
    embedder, encoder = model
    embedder.audit_inputs = lambda texts: [{"would_truncate": True} for _ in texts]
    with pytest.raises(ValueError, match="exceeds"):
        embedder.embed_token_safe_documents(["oversized"])
    encoder.encode.assert_not_called()


def test_real_fixture_tokenizer_contract_offsets_and_visibility(passage_embedder):
    from transformers import PreTrainedTokenizerFast

    class Model:
        max_seq_length = 16
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=passage_embedder.tokenizer)

        def __getitem__(self, index):
            return SimpleNamespace(do_lower_case=True)

    embedder = object.__new__(EmbeddingModel)
    embedder._model = Model()
    embedder.model_name = "fixture"
    contract = embedder.tokenizer_contract()
    text = "ABİ中文" + "x" * 30
    ids, offsets = embedder.body_tokens(text)
    assert (
        ids
        and len(ids) == len(offsets)
        and all(0 <= a < b <= len(text) for a, b in offsets)
    )
    prefix = embedder.visible_input_prefix(text)
    assert text.startswith(prefix) and len(prefix) < len(text)
    assert embedder.tokenizer_contract() == contract


def test_e5_encoding_and_local_only(model):
    _, encoder = model
    e = EmbeddingModel("intfloat/multilingual-e5-base")
    e.embed_query("测试")
    assert encoder.encode.call_args.args == ("query: 测试",)
    e.embed_documents(["evidence"])
    assert encoder.encode.call_args.args == (["passage: evidence"],)
    with pytest.raises(ValueError, match="local-only"):
        EmbeddingModel(local_files_only=False)
    with pytest.raises(ValueError, match="unverified"):
        EmbeddingModel("unknown-model")


def test_fingerprint_deterministic_and_sensitive_to_weights(model, tmp_path):
    e, encoder = model
    encoder.get_sentence_embedding_dimension.return_value = 2
    encoder.max_seq_length = 512
    (tmp_path / "config.json").write_text('{"model_type":"fixture"}')
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    e.model_path = str(tmp_path)
    e.tokenizer_contract = lambda: {"tokenizer_sha256": "fixture"}
    first = e.fingerprint()
    assert first == e.fingerprint()
    assert first["local_snapshot_id"] is None
    assert first["dimension"] == 2 and first["max_seq_length"] == 512
    (tmp_path / "model.safetensors").write_bytes(b"changed")
    assert e.fingerprint() == first  # The already loaded model identity is cached.
    first["dimension"] = 999
    assert e.fingerprint()["dimension"] == 2
    reloaded = EmbeddingModel()
    reloaded.model_path = str(tmp_path)
    reloaded.tokenizer_contract = e.tokenizer_contract
    assert (
        first["weights_manifest_sha256"]
        != reloaded.fingerprint()["weights_manifest_sha256"]
    )


def test_document_prefix_participates_in_token_budget():
    class Model:
        max_seq_length = 5

        def __getitem__(self, index):
            return SimpleNamespace(do_lower_case=False)

        def tokenizer(self, texts, **kwargs):
            return {"input_ids": [[101, *range(len(t.split())), 102] for t in texts]}

    e = object.__new__(EmbeddingModel)
    e._model = Model()
    e.document_prefix = "passage: "
    assert not e.audit_inputs(["one two"])[0]["would_truncate"]
    assert e.audit_inputs(["one two three"])[0]["would_truncate"]
    with pytest.raises(ValueError, match="exceeds"):
        e.embed_token_safe_documents(["one two three"])
