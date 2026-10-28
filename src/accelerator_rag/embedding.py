from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from typing import Protocol

FloatArray = NDArray[np.float32]


class TextEmbedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> FloatArray: ...

    def embed_query(self, text: str) -> FloatArray: ...


class EmbeddingModel:
    """Local SentenceTransformer retrieval adapter with explicit input contracts."""

    # Cached BAAI model card: bge-small-zh-v1.5 model table and s2p example.
    # The full-width colon is the recommended separator; passages have no prefix.
    QUERY_TEMPLATE = "为这个句子生成表示以用于检索相关文章：{query}"

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        device: str = "cpu",
        *,
        local_files_only: bool = True,
        batch_size: int = 32,
        model_path: str | None = None,
        dtype: str | None = None,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        if not local_files_only:
            raise ValueError("download models separately; encoding is local-only")
        contracts = {
            "BAAI/bge-small-zh-v1.5": (self.QUERY_TEMPLATE, ""),
            "BAAI/bge-base-zh-v1.5": (self.QUERY_TEMPLATE, ""),
            "intfloat/multilingual-e5-base": ("query: {query}", "passage: "),
            # M3 dense: normalized CLS, symmetric encoding without instruction.
            "BAAI/bge-m3": ("{query}", ""),
            # Qwen3: local official last-token pooling; instruction on queries only.
            "Qwen/Qwen3-Embedding-0.6B": (
                "Instruct: Retrieve technical passages that answer the user's "
                "question about accelerator, control system, EPICS, XFEL, "
                "cryogenics, timing, interlock, or related engineering topics."
                "\nQuery:{query}", ""
            ),
        }
        if model_name not in contracts:
            raise ValueError(f"unverified retrieval encoding contract: {model_name}")
        self.QUERY_TEMPLATE, self.document_prefix = contracts[model_name]
        self.model_path = model_path
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
        self.model_name = model_name
        self.device = device

        if dtype not in {None, "float32", "float16", "bfloat16"}:
            raise ValueError("unsupported embedding dtype")
        self._model = SentenceTransformer(
            model_path or model_name,
            device=device,
            local_files_only=local_files_only,
            model_kwargs={"dtype": dtype or "float32"}
            if dtype or (model_name == "Qwen/Qwen3-Embedding-0.6B" and device == "cpu")
            else None,
        )
        if model_name == "Qwen/Qwen3-Embedding-0.6B":
            self._model.tokenizer.padding_side = "left"

    @property
    def dimension(self) -> int:
        dimension = self._model.get_sentence_embedding_dimension()
        if not isinstance(dimension, int) or dimension <= 0:
            raise ValueError("embedding model does not expose a valid dimension")
        return dimension

    def embed_documents(
        self,
        texts: Sequence[str],
    ) -> FloatArray:
        """将多个文档文本转换为二维向量矩阵"""

        if not texts:
            raise ValueError("文档文本列表不能为空")

        embeddings = self._model.encode(
            [self.document_prefix + t for t in texts],
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embeddings,
            dtype=np.float32,
        )

    def embed_query(
        self,
        text: str,
    ) -> FloatArray:
        """将单个查询转换为一维向量"""

        query = text.strip()

        if not query:
            raise ValueError("查询文本不能为空")

        query_with_instruction = self.QUERY_TEMPLATE.format(query=query)
        if self.model_name in {"BAAI/bge-m3", "Qwen/Qwen3-Embedding-0.6B"}:
            ids = self._model.tokenizer(
                query_with_instruction, truncation=False, add_special_tokens=True
            )["input_ids"]
            if len(ids) > self.max_seq_length:
                raise ValueError("query exceeds model max_seq_length")

        embedding = self._model.encode(
            query_with_instruction,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return np.asarray(
            embedding,
            dtype=np.float32,
        )

    @property
    def max_seq_length(self) -> int:
        limit = self._model.max_seq_length
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("model does not expose valid max_seq_length")
        return limit

    def audit_inputs(self, texts: Sequence[str]) -> list[dict]:
        """Mirror Transformer.tokenize string preparation, retaining specials.

        Audit before truncation. The actual SentenceTransformer still controls
        truncation at encode time; this method does not change model inputs.
        """
        transformer = self._model[0]
        prefix = getattr(self, "document_prefix", "")
        prepared = [(prefix + text).strip() for text in texts]
        if transformer.do_lower_case:
            prepared = [text.lower() for text in prepared]
        encoded = self._model.tokenizer(
            prepared,
            add_special_tokens=True,
            truncation=False,
            padding=False,
            return_attention_mask=False,
        )
        return [
            {
                "token_count": len(ids),
                "would_truncate": len(ids) > self.max_seq_length,
                "truncated_token_count": max(0, len(ids) - self.max_seq_length),
                "truncation_ratio": max(0, len(ids) - self.max_seq_length)
                / max(1, len(ids)),
            }
            for ids in encoded["input_ids"]
        ]

    def tokenizer_contract(self) -> dict:
        """Stable tokenizer semantics, excluding mutable padding/truncation state."""
        import json
        from hashlib import sha256

        tokenizer = self._model.tokenizer
        if not tokenizer.is_fast:
            raise ValueError("passage building requires a fast tokenizer with offsets")
        config = json.loads(tokenizer.backend_tokenizer.to_str())
        config.pop("truncation", None)
        config.pop("padding", None)
        contract = {
            "model": self.model_name,
            "max_seq_length": self.max_seq_length,
            "tokenizer_sha256": sha256(
                json.dumps(config, sort_keys=True).encode()
            ).hexdigest(),
            "do_lower_case": self._model[0].do_lower_case,
            "template": 'document_title + "\\n" + passage.text',
        }
        if getattr(self, "document_prefix", ""):
            contract["document_prefix"] = self.document_prefix
        return contract

    def fingerprint(self) -> dict:
        """Hash actual local artifacts in bounded blocks; never infer a revision."""
        import json
        from copy import deepcopy
        from hashlib import sha256
        from pathlib import Path
        from huggingface_hub import try_to_load_from_cache

        if hasattr(self, "_fingerprint_cache"):
            return deepcopy(self._fingerprint_cache)

        if self.model_path:
            path = Path(self.model_path).absolute()
        else:
            config = try_to_load_from_cache(self.model_name, "config.json")
            if not isinstance(config, str):
                raise ValueError("local model config not resolved")
            path = Path(config).parent

        def digest(file):
            h = sha256()
            with file.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            return h.hexdigest()

        weights = {
            p.relative_to(path).as_posix(): digest(p)
            for p in sorted(path.rglob("*"))
            if p.is_file()
            and p.suffix in {".safetensors", ".bin"}
            and not {"onnx", "openvino", ".cache"}.intersection(
                p.relative_to(path).parts
            )
        }
        if not weights:
            raise ValueError("no local model weights found")
        configs = {
            p.relative_to(path).as_posix(): digest(p)
            for p in sorted(path.rglob("*.json"))
            if ".cache" not in p.relative_to(path).parts
        }
        identity = {
            "requested_model_name": self.model_name,
            "resolved_local_model_path": str(path),
            "local_snapshot_id": path.name if path.parent.name == "snapshots" else None,
            "snapshot_identity_source": "local cache path"
            if path.parent.name == "snapshots"
            else "downloaded local directory; no inferred revision",
            "model_config_sha256": digest(path / "config.json"),
            "config_files": configs,
            "tokenizer_sha256": self.tokenizer_contract()["tokenizer_sha256"],
            "weights_files": weights,
            "weights_manifest_sha256": sha256(
                json.dumps(weights, sort_keys=True).encode()
            ).hexdigest(),
            "max_seq_length": self.max_seq_length,
            "dimension": self.dimension,
            "query_template": self.QUERY_TEMPLATE,
            "document_prefix": self.document_prefix,
            "local_model_bytes": sum(
                p.stat().st_size
                for p in path.rglob("*")
                if p.is_file() and ".cache" not in p.relative_to(path).parts
            ),
        }
        self._fingerprint_cache = identity
        return deepcopy(identity)

    def body_tokens(self, text: str) -> tuple[list[int], list[tuple[int, int]]]:
        """Actual token IDs and source-character offsets; no decode/re-encode loss.

        Mirror optional Transformer lowercasing, preserving an exact map even
        when Unicode lowercasing expands a character. The tokenizer's internal
        normalization already maps its own offsets to its input string.
        """
        prepared, original = [], []
        lower = self._model[0].do_lower_case
        for i, char in enumerate(text):
            value = char.lower() if lower else char
            prepared.append(value)
            original.extend([i] * len(value))
        encoded = self._model.tokenizer(
            "".join(prepared),
            add_special_tokens=False,
            truncation=False,
            return_offsets_mapping=True,
            return_attention_mask=False,
        )
        offsets = [
            (original[a], original[b - 1] + 1)
            for a, b in encoded["offset_mapping"]
            if b > a
        ]
        ids = [
            t
            for t, (a, b) in zip(
                encoded["input_ids"], encoded["offset_mapping"], strict=True
            )
            if b > a
        ]
        return ids, offsets

    def embed_token_safe_documents(self, texts: Sequence[str]) -> FloatArray:
        """Hard invariant immediately before encode; never silently truncate."""
        rows = self.audit_inputs(texts)
        if any(r["would_truncate"] for r in rows):
            raise ValueError("embedding passage exceeds model max_seq_length")
        return self.embed_documents(texts)

    def visible_input_prefix(self, text: str) -> str:
        """Source prefix represented by a real max-length tokenization.

        Includes special tokens in the tokenizer call. Used only to diagnose
        historical direct-chunk truncation, never to construct ground truth.
        """
        stripped = text.strip()
        prepared = []
        original = []
        for i, char in enumerate(stripped):
            value = char.lower() if self._model[0].do_lower_case else char
            prepared.append(value)
            original.extend([i] * len(value))
        encoded = self._model.tokenizer(
            "".join(prepared),
            add_special_tokens=True,
            truncation=True,
            max_length=self.max_seq_length,
            return_offsets_mapping=True,
            return_attention_mask=False,
        )
        end = max((b for a, b in encoded["offset_mapping"] if b > a), default=0)
        return stripped[: original[end - 1] + 1] if end else ""


def document_embedding_text(chunk) -> str:
    """Single passage template shared by encoding and input audit."""
    return f"{chunk.document_title}\n{chunk.text}"


def audit_embedding_inputs(embedder, chunks) -> dict:
    from accelerator_rag.corpus.audit import distribution

    rows = []
    for start in range(0, len(chunks), 128):
        batch = chunks[start : start + 128]
        rows.extend(
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "language": c.language,
                "page": c.page_start,
                **a,
            }
            for c, a in zip(
                batch,
                embedder.audit_inputs([document_embedding_text(c) for c in batch]),
                strict=True,
            )
        )

    def summary(group):
        count = len(group)
        exceeding = sum(r["would_truncate"] for r in group)
        return {
            "total_chunks": count,
            "chunks_exceeding_limit": exceeding,
            "percentage_exceeding_limit": 100 * exceeding / count if count else 0,
            "token_length_distribution": distribution(
                [r["token_count"] for r in group]
            ),
        }

    return {
        "model_max_seq_length": embedder.max_seq_length,
        **summary(rows),
        "input_template": 'document_title + "\\n" + chunk.text',
        "special_tokens_included": True,
        "by_language": {
            lang: summary([r for r in rows if r["language"] == lang])
            for lang in sorted({r["language"] for r in rows})
        },
        "by_document": {
            doc: summary([r for r in rows if r["document_id"] == doc])
            for doc in sorted({r["document_id"] for r in rows})
        },
        "worst_examples": sorted(rows, key=lambda r: -r["token_count"])[:20],
    }
