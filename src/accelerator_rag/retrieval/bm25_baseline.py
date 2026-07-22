from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

import jieba

from accelerator_rag.retrieval.semantic_search import DocumentChunk

# 匹配技术词、PV名、数字和中文文本
TOKEN_PATTERN = re.compile(
    r"[A-Za-z][A-Za-z0-9_.-]*(?::[A-Za-z0-9_.-]+)+"
    r"|[A-Za-z][A-Za-z0-9_.+-]*"
    r"|\d+(?:\.\d+)?"
    r"|[\u4e00-\u9fff]+"
)


@dataclass(frozen=True)
class BM25SearchResult:
    """BM25 检索结果。"""

    chunk: DocumentChunk
    score: float


def tokenize(text: str) -> list[str]:
    """将文本切为合适基础关键词检索的token"""

    raw_tokens = TOKEN_PATTERN.findall(text)

    tokens: list[str] = []

    for token in raw_tokens:
        # 中文文本交给jieba分词
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            tokens.extend(word.strip() for word in jieba.lcut(token) if word.strip())
        else:
            # 英文缩写、pv名统一转小写
            tokens.append(token.casefold())

    return tokens


class BM25BaselineRetriever:
    """用于Day5学习和对比试验的内存BM25检索器"""

    def __init__(
        self, chunks: Sequence[DocumentChunk], *, k1: float = 1.5, b: float = 0.75
    ) -> None:
        if not chunks:
            raise ValueError("chunks cannot be empty")

        if k1 <= 0:
            raise ValueError("k1 must be greater than 0")

        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1")

        self._chunks = list(chunks)
        self._k1 = k1
        self._b = b

        self._tokenized_documents = [
            tokenize(f"{chunk.title} {chunk.text}") for chunk in self._chunks
        ]

        self._document_lengths = [len(tokens) for tokens in self._tokenized_documents]

        self._average_document_length = sum(self._document_lengths) / len(
            self._document_lengths
        )

        self._document_frequency: Counter[str] = Counter()

        for tokens in self._tokenized_documents:
            self._document_frequency.update(set(tokens))

    def _idf(self, term: str) -> float:
        document_count = len(self._chunks)

        document_frequency = self._document_frequency.get(
            term,
            0,
        )

        return math.log(
            1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
        )

    def _score_document(
        self,
        query_tokens: Sequence[str],
        document_tokens: Sequence[str],
        document_length: int,
    ) -> float:
        term_frequency = Counter(document_tokens)

        score = 0.0

        for term in set(query_tokens):
            frequency = term_frequency.get(term, 0)

            if frequency == 0:
                continue

            idf = self._idf(term)

            denominator = frequency + self._k1 * (
                1 - self._b + self._b * document_length / self._average_document_length
            )

            score += idf * frequency * (self._k1 + 1) / denominator
        return score

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
    ) -> list[BM25SearchResult]:
        if not query.strip():
            raise ValueError("query connot be empty")

        if top_k <= 0:
            raise ValueError("top_k must be great than 0")

        query_tokens = tokenize(query)

        results: list[BM25SearchResult] = []

        for chunk, tokens, document_length in zip(
            self._chunks, self._tokenized_documents, self._document_lengths, strict=True
        ):
            score = self._score_document(
                query_tokens=query_tokens,
                document_tokens=tokens,
                document_length=document_length,
            )
            if score > 0:
                results.append(
                    BM25SearchResult(
                        chunk=chunk,
                        score=score,
                    )
                )
        results.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        return results[:top_k]
