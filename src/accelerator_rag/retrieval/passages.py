"""Model-specific Dense representation; canonical evidence stays unchanged."""

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import re
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.embedding import document_embedding_text
from accelerator_rag.corpus.audit import distribution

PASSAGE_ALGORITHM = "dense-passages-v1"


@dataclass(frozen=True)
class PassageConfig:
    max_tokens: int | None = None
    guard_tokens: int = 16
    overlap_tokens: int = 32

    def __post_init__(self):
        if (
            (
                self.max_tokens is not None
                and (type(self.max_tokens) is not int or self.max_tokens <= 0)
            )
            or type(self.guard_tokens) is not int
            or type(self.overlap_tokens) is not int
            or self.guard_tokens < 0
            or self.overlap_tokens < 0
        ):
            raise ValueError("invalid passage budget configuration")


@dataclass(frozen=True)
class EmbeddingPassage:
    passage_id: str
    parent: KnowledgeChunk
    passage_ordinal: int
    text: str
    char_start: int
    char_end: int
    token_count: int
    contract_id: str

    @property
    def parent_chunk_id(self):
        return self.parent.chunk_id

    @property
    def document_title(self):
        return self.parent.document_title

    def __post_init__(self):
        if (
            not self.passage_id.strip()
            or not self.contract_id.strip()
            or type(self.passage_ordinal) is not int
            or self.passage_ordinal < 0
            or type(self.token_count) is not int
            or self.token_count <= 0
        ):
            raise ValueError("invalid passage identity/ordinal/token_count")
        if (
            not 0 <= self.char_start < self.char_end <= len(self.parent.text)
            or not self.text.strip()
            or self.parent.text[self.char_start : self.char_end].strip() != self.text
        ):
            raise ValueError("passage must be a nonempty exact parent substring")


class PassageBuilder:
    def __init__(self, embedder, config=PassageConfig()):
        self.embedder, self.config = embedder, config
        self.limit = config.max_tokens or embedder.max_seq_length
        if self.limit > embedder.max_seq_length:
            raise ValueError("passage max_tokens exceeds model limit")
        self.contract = {
            "algorithm": PASSAGE_ALGORITHM,
            "config": asdict(config),
            "tokenizer": embedder.tokenizer_contract(),
            "effective_max_tokens": self.limit,
        }
        self.contract_id = sha256(
            json.dumps(self.contract, sort_keys=True).encode()
        ).hexdigest()

    def count(self, title, text):
        return self.embedder.audit_inputs([f"{title}\n{text}"])[0]["token_count"]

    def build(self, chunks):
        if len({c.chunk_id for c in chunks}) != len(chunks):
            raise ValueError("duplicate parent chunk IDs")
        passages = []
        for parent in chunks:
            windows = []
            full_count = self.count(parent.document_title, parent.text)
            if full_count <= self.limit:
                windows = [(0, len(parent.text), full_count)]
            else:
                overhead = self.count(parent.document_title, "")
                budget = self.limit - self.config.guard_tokens - overhead
                if budget <= self.config.overlap_tokens or budget < 1:
                    raise ValueError(
                        f"title leaves insufficient passage body budget: {parent.chunk_id}"
                    )
                ids, offsets = self.embedder.body_tokens(parent.text)
                if not ids or len(ids) != len(offsets):
                    raise ValueError("tokenizer exposes no usable body token offsets")
                ends = [b for _, b in offsets]
                start = 0
                while start < len(ids):
                    begin = 0 if start == 0 else offsets[start][0]
                    end = min(len(ids), start + budget)
                    stop = len(parent.text) if end == len(ids) else offsets[end - 1][1]
                    # Prefer boundaries in the latter half of the available
                    # token window; avoid tiny windows and overlap-only loops.
                    floor = min(
                        end, start + max(self.config.overlap_tokens + 1, budget // 2)
                    )
                    floor_char = offsets[floor - 1][1]
                    if end < len(ids):
                        for pattern in (
                            r"\n\s*\n",
                            r"[.!?。！？](?:\s+|(?=[\u3400-\u9fff]))",
                            r"\s+",
                        ):
                            boundaries = [
                                begin + m.end()
                                for m in re.finditer(pattern, parent.text[begin:stop])
                                if begin + m.end() >= floor_char
                            ]
                            if boundaries:
                                candidate = boundaries[-1]
                                natural_end = bisect_right(ends, candidate)
                                if natural_end > start + self.config.overlap_tokens:
                                    end = natural_end
                                    stop = candidate
                                    break
                    # Tokenization can change at substring boundaries. Count the
                    # final title+body template, not independent token sums.
                    safe = self.limit - self.config.guard_tokens
                    count = self.count(
                        parent.document_title, parent.text[begin:stop].strip()
                    )
                    while count > safe and end > start + 1:
                        end -= 1
                        stop = offsets[end - 1][1]
                        count = self.count(
                            parent.document_title, parent.text[begin:stop].strip()
                        )
                    if count > safe:
                        raise ValueError("no nonempty token-safe passage fits template")
                    windows.append((begin, stop, count))
                    if end == len(ids):
                        break
                    next_start = max(start + 1, end - self.config.overlap_tokens)
                    if next_start <= start:
                        raise RuntimeError("passage split made no progress")
                    start = next_start
            for ordinal, (a, b, count) in enumerate(windows):
                text = parent.text[a:b].strip()
                identity = {
                    "contract": self.contract_id,
                    "parent": parent.chunk_id,
                    "ordinal": ordinal,
                    "text": text,
                    "title": parent.document_title,
                    "range": [a, b],
                }
                pid = (
                    parent.chunk_id
                    + ":p:"
                    + sha256(
                        json.dumps(
                            identity, ensure_ascii=False, sort_keys=True
                        ).encode()
                    ).hexdigest()
                )
                passages.append(
                    EmbeddingPassage(
                        pid, parent, ordinal, text, a, b, count, self.contract_id
                    )
                )
        # Independent final-template validation, before any vector writes.
        rows = self.embedder.audit_inputs(
            [document_embedding_text(p) for p in passages]
        )
        if any(r["token_count"] > self.limit for r in rows):
            raise ValueError("final passage input exceeds token budget")
        if any(
            r["token_count"] != p.token_count
            for p, r in zip(passages, rows, strict=True)
        ):
            raise ValueError("inconsistent tokenizer passage counts")
        return passages


def passage_statistics(passages, builder):
    counts = Counter(p.parent_chunk_id for p in passages)
    lengths = distribution([p.token_count for p in passages])
    return {
        "algorithm": PASSAGE_ALGORITHM,
        "contract": builder.contract,
        "contract_id": builder.contract_id,
        "model_max_seq_length": builder.embedder.max_seq_length,
        "eligible_parent_chunks": len(counts),
        "embedding_passages": len(passages),
        "parents_with_1_passage": sum(n == 1 for n in counts.values()),
        "parents_split": sum(n > 1 for n in counts.values()),
        "average_passages_per_parent": len(passages) / len(counts),
        "passages_per_parent": distribution(list(counts.values())),
        "passage_token_length": lengths,
        "passages_exceeding_limit": sum(
            p.token_count > builder.embedder.max_seq_length for p in passages
        ),
        "all_passage_inputs_within_model_limit": all(
            p.token_count <= builder.embedder.max_seq_length for p in passages
        ),
        "guard_policy": "Already-fitting parent inputs remain unchanged; split windows reserve guard_tokens in the complete title+body+specials template.",
        "by_document": {
            doc: {
                "parents": len(
                    {p.parent_chunk_id for p in passages if p.parent.document_id == doc}
                ),
                "passages": sum(p.parent.document_id == doc for p in passages),
            }
            for doc in sorted({p.parent.document_id for p in passages})
        },
    }
