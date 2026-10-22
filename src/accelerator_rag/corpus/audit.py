"""Corpus measurements only: audit never changes or discards evidence."""

from collections import Counter
from dataclasses import asdict, dataclass
import re
from typing import Any

import numpy as np

from accelerator_rag.corpus.chunking import CHUNKING_ALGORITHM, ChunkingConfig
from accelerator_rag.corpus.cleaning import (
    PAGE_NUMBER_PATTERN,
    PUBLICATION_PATTERN,
    RIGHTS_PATTERN,
    RUNNING_CODE_PATTERN,
)
from accelerator_rag.domain.knowledge import KnowledgeChunk
from accelerator_rag.ingestion import IngestedDocument


@dataclass(frozen=True)
class AuditConfig:
    very_short_chars: int = 100
    many_chunks_per_page: int = 10
    example_limit: int = 100

    def __post_init__(self):
        if (
            min(self.very_short_chars, self.many_chunks_per_page, self.example_limit)
            <= 0
        ):
            raise ValueError("audit thresholds must be positive")


@dataclass(frozen=True)
class CorpusAuditReport:
    metadata: dict[str, Any]
    overview: dict[str, int]
    documents: list[dict[str, Any]]
    chunk_lengths: dict[str, float | int]
    page_distribution: dict[str, Any]
    parser_warnings: dict[str, int]
    quality: dict[str, Any]
    identity: dict[str, int | bool]
    findings: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def distribution(values: list[int | float]) -> dict[str, float | int]:
    """Linear interpolation percentiles, including zeros; empty is explicit."""
    if not values:
        return {"count": 0}
    percentiles = np.percentile(values, [10, 25, 50, 75, 90, 95], method="linear")
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": float(np.mean(values)),
        **dict(
            zip(
                ["p10", "p25", "median", "p75", "p90", "p95"],
                map(float, percentiles),
                strict=True,
            )
        ),
    }


def _citation(
    chunk: KnowledgeChunk, kind: str, count: int, offset: int = 0
) -> dict[str, Any]:
    return {
        "kind": kind,
        "count": count,
        "document_id": chunk.document_id,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "source_path": chunk.source_path,
        "chunk_id": chunk.chunk_id,
        "excerpt": chunk.text[:500],
        "signal_context": chunk.text[max(0, offset - 80) : offset + 300],
    }


def _private_use(char: str) -> bool:
    code = ord(char)
    return (
        0xE000 <= code <= 0xF8FF
        or 0xF0000 <= code <= 0xFFFFD
        or 0x100000 <= code <= 0x10FFFD
    )


def audit_corpus(
    documents: list[IngestedDocument],
    registered_documents: int,
    chunking: ChunkingConfig,
    *,
    generated_on: str,
    config: AuditConfig = AuditConfig(),
) -> CorpusAuditReport:
    if len({d.record.doc_id for d in documents}) != len(documents):
        raise ValueError("duplicate ingested document identity")
    chunks = [c for d in documents for c in d.chunks]
    chunk_ids = [c.chunk_id for c in chunks]
    duplicates = len(chunk_ids) - len(set(chunk_ids))
    if duplicates:
        raise ValueError(f"duplicate corpus chunk IDs: {duplicates}")
    lengths = [len(c.text) for c in chunks]
    warning_counts: Counter[str] = Counter()
    per_document = []
    page_counts = []
    empty_pages, many_pages, all_pages = [], [], []
    findings = []
    for doc in documents:
        if doc.parsed.source_path != doc.record.source_path:
            raise ValueError("parsed/registered source mismatch")
        per_page: Counter[int] = Counter()
        for c in doc.chunks:
            if (
                c.document_id != doc.record.doc_id
                or c.source_path != doc.record.source_path
                or c.page_end > doc.parsed.page_count
            ):
                raise ValueError("chunk citation does not match ingested document")
            for page in range(c.page_start, c.page_end + 1):
                per_page[page] += 1
        warnings: Counter[str] = Counter()
        warning_pages: dict[str, list[int]] = {}
        for page in doc.parsed.pages:
            count = per_page[page.page_number]
            page_counts.append(count)
            attribution = {
                "document_id": doc.record.doc_id,
                "page": page.page_number,
                "chunk_count": count,
                "raw_chars": page.char_count,
                "image_count": page.image_count,
                "warnings": page.warnings,
            }
            all_pages.append(attribution)
            if count == 0:
                empty_pages.append(attribution)
            if count > config.many_chunks_per_page:
                many_pages.append(attribution)
            for warning in set(page.warnings):
                warnings[warning] += 1
                warning_pages.setdefault(warning, []).append(page.page_number)
        warning_counts.update(warnings)
        per_document.append(
            {
                "document_id": doc.record.doc_id,
                "title": doc.record.title,
                "source_path": doc.record.source_path,
                "page_count": doc.parsed.page_count,
                "chunk_count": len(doc.chunks),
                "chunk_chars": sum(len(c.text) for c in doc.chunks),
                "chunk_lengths": {
                    **distribution([len(c.text) for c in doc.chunks]),
                    "very_short_chunks": sum(
                        len(c.text) < config.very_short_chars for c in doc.chunks
                    ),
                    "very_long_chunks": sum(
                        len(c.text) > chunking.max_chars for c in doc.chunks
                    ),
                },
                "chunks_per_page": distribution(
                    [per_page[p.page_number] for p in doc.parsed.pages]
                ),
                "language": doc.record.language,
                "category": doc.record.category,
                "topic": doc.record.topic,
                "warning_counts": dict(warnings),
                "warning_pages": warning_pages,
                "pages_without_chunks": sum(
                    per_page[p.page_number] == 0 for p in doc.parsed.pages
                ),
            }
        )
    # Corpus lexical evidence flags candidates; it does not claim every hyphen is wrong.
    vocabulary = {
        m.casefold() for c in chunks for m in re.findall(r"\b[A-Za-z]+\b", c.text)
    }
    signals = {
        "replacement": lambda t: t.count("\ufffd"),
        "null": lambda t: t.count("\x00"),
        "private_use": lambda t: sum(_private_use(char) for char in t),
        "publication_identifiers": lambda t: len(PUBLICATION_PATTERN.findall(t)),
        "copyright_license": lambda t: len(RIGHTS_PATTERN.findall(t)),
        "isolated_page_numbers": lambda t: len(PAGE_NUMBER_PATTERN.findall(t)),
        "running_publication_codes": lambda t: len(RUNNING_CODE_PATTERN.findall(t)),
    }
    quality: dict[str, Any] = {}
    for kind, count_signal in signals.items():
        examples = []
        counts: Counter[str] = Counter()
        pages: set[tuple[str, int]] = set()
        occurrences = 0
        affected = 0
        for c in chunks:
            count = count_signal(c.text)
            if count:
                affected += 1
                occurrences += count
                counts[c.document_id] += count
                pages.update(
                    (c.document_id, p) for p in range(c.page_start, c.page_end + 1)
                )
                if kind in {"replacement", "null"}:
                    offset = c.text.index("\ufffd" if kind == "replacement" else "\x00")
                elif kind == "private_use":
                    offset = next(
                        i for i, char in enumerate(c.text) if _private_use(char)
                    )
                else:
                    pattern = {
                        "publication_identifiers": PUBLICATION_PATTERN,
                        "copyright_license": RIGHTS_PATTERN,
                        "isolated_page_numbers": PAGE_NUMBER_PATTERN,
                        "running_publication_codes": RUNNING_CODE_PATTERN,
                    }[kind]
                    offset = pattern.search(c.text).start()
                examples.append(_citation(c, kind, count, offset))
        examples.sort(key=lambda sample: (-sample["count"], sample["chunk_id"]))
        quality[kind] = {
            "occurrences": occurrences,
            "affected_chunks": affected,
            "affected_pages": len(pages),
            "per_document": dict(counts),
            "examples": examples[: config.example_limit],
        }
        findings.extend(examples[:20])
    hyphens: Counter[str] = Counter()
    candidates = []
    for c in chunks:
        matches = Counter(
            token
            for token in re.findall(r"\b[a-z]{2,}-[a-z]{2,}\b", c.text)
            if token.replace("-", "") in vocabulary
        )
        hyphens.update(matches)
        for token, count in matches.items():
            candidates.append(
                {
                    **_citation(
                        c, "suspicious_hyphenation", count, c.text.index(token)
                    ),
                    "token": token,
                }
            )
    quality["suspicious_hyphenation"] = {
        "count": sum(hyphens.values()),
        "heuristic": "lowercase compound with intact unhyphenated corpus spelling",
        "top_examples": [
            {
                "token": token,
                "count": count,
                "citations": [c for c in candidates if c["token"] == token][:5],
            }
            for token, count in hyphens.most_common(30)
        ],
        "examples": candidates[: config.example_limit],
        "per_document": dict(
            Counter(
                {
                    d.record.doc_id: sum(
                        c["count"]
                        for c in candidates
                        if c["document_id"] == d.record.doc_id
                    )
                    for d in documents
                }
            )
        ),
    }
    findings.extend(sorted(candidates, key=lambda x: -x["count"])[:20])
    for doc in per_document:
        doc["quality_occurrences"] = {
            kind: data["per_document"].get(doc["document_id"], 0)
            for kind, data in quality.items()
        }
    long = [c for c in chunks if len(c.text) > chunking.max_chars]
    short = [c for c in chunks if len(c.text) < config.very_short_chars]
    findings.extend(_citation(c, "very_long_chunk", len(c.text)) for c in long[:20])
    findings.extend(_citation(c, "very_short_chunk", len(c.text)) for c in short[:20])
    priorities = {
        "replacement": 0,
        "null": 0,
        "very_long_chunk": 0,
        "private_use": 1,
        "copyright_license": 2,
        "suspicious_hyphenation": 3,
    }
    findings.sort(
        key=lambda x: (priorities.get(x["kind"], 4), -x["count"], x["chunk_id"])
    )
    return CorpusAuditReport(
        metadata={
            "generated_on": generated_on,
            "chunking_algorithm": CHUNKING_ALGORITHM,
            "chunking_config": asdict(chunking),
            "audit_config": asdict(config),
            "percentile_method": "linear",
            "corpus_document_count": len(documents),
        },
        overview={
            "registered_documents": registered_documents,
            "successfully_ingested_documents": len(documents),
            "total_pages": len(page_counts),
            "total_chunks": len(chunks),
            "total_chunk_chars": sum(lengths),
        },
        documents=per_document,
        chunk_lengths={
            **distribution(lengths),
            "very_short_chunks": len(short),
            "very_long_chunks": len(long),
        },
        page_distribution={
            "chunks_per_page": distribution(page_counts),
            "pages_without_chunks": empty_pages,
            "pages_with_very_many_chunks": many_pages,
            "pages": all_pages,
        },
        parser_warnings=dict(warning_counts),
        quality=quality,
        identity={
            "unique_chunk_count": len(set(chunk_ids)),
            "duplicate_count": duplicates,
            "all_unique": duplicates == 0,
        },
        findings=findings[:30],
    )
