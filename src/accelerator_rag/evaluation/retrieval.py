"""Deterministic, excerpt-level evidence judgments; no score threshold."""

from dataclasses import asdict, dataclass, replace
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata
from typing import Protocol
from accelerator_rag.corpus.audit import distribution
from accelerator_rag.corpus.eligibility import assess_retrieval_eligibility
from accelerator_rag.domain.knowledge import KnowledgeChunk, RetrievalResult
from accelerator_rag.ingestion import IngestedDocument


def normalize_evidence(text: str) -> str:
    """Unicode compatibility/whitespace equivalence, not fuzzy matching.

    Remove a hyphen only when separated from the next lowercase fragment by
    actual whitespace. Inline technical compounds retain their hyphen.
    """
    text = unicodedata.normalize("NFKC", text).replace("\x00", "")
    text = re.sub(r"(?<=[A-Za-z])-\s+(?=[a-z])", "", text)
    return re.sub(r"\s+", "", text).casefold()


@dataclass(frozen=True)
class EvidenceTarget:
    document_id: str
    page: int
    excerpt: str


@dataclass(frozen=True)
class EvidenceGroup:
    alternatives: tuple[EvidenceTarget, ...]


@dataclass(frozen=True)
class EvaluationQuery:
    id: str
    query: str
    language: str
    category: str
    answerable: bool
    evidence_groups: tuple[EvidenceGroup, ...]
    judgment_mode: str = "all"
    negative_type: str | None = None
    language_relation: str = "same_language"


class Retriever(Protocol):
    def search(self, query: str, *, top_k: int) -> list[RetrievalResult]: ...


def target_matches(chunk, target: EvidenceTarget) -> bool:
    return (
        chunk.document_id == target.document_id
        and chunk.page_start <= target.page <= chunk.page_end
        and normalize_evidence(target.excerpt) in normalize_evidence(chunk.text)
    )


def load_queries(
    path: Path, documents: list[IngestedDocument], *, eligible_chunks=None
) -> list[EvaluationQuery]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("schema_version") != 2
        or not raw.get("judgment_revision")
    ):
        raise ValueError("query set needs schema_version=2 and judgment_revision")
    items = raw.get("queries")
    if not isinstance(items, list) or not items:
        raise ValueError("query set must contain nonempty queries")
    corpus = {d.record.doc_id: d for d in documents}
    if eligible_chunks is None:
        eligible_chunks = [
            c
            for d in documents
            for c in d.chunks
            if assess_retrieval_eligibility(c).eligible
        ]
    queries, seen = [], set()
    for item in items:
        if (
            type(item["answerable"]) is not bool
            or item["judgment_mode"] not in {"any", "all"}
            or item["language"] not in {"zh", "en"}
        ):
            raise ValueError("invalid answerable / judgment_mode / language")
        if not item["id"].strip() or item["id"] in seen or not item["query"].strip():
            raise ValueError("duplicate/empty query identity or text")
        seen.add(item["id"])
        if not item.get("judgment_note", "").strip():
            raise ValueError("judgment_note required")
        groups, relations = [], []
        for group in item["evidence_groups"]:
            alternatives = []
            for t in group["alternatives"]:
                target = EvidenceTarget(**t)
                if (
                    target.document_id not in corpus
                    or type(target.page) is not int
                    or not normalize_evidence(target.excerpt)
                ):
                    raise ValueError("invalid evidence target")
                doc = corpus[target.document_id]
                context = f"{item['id']} {target.document_id} page {target.page}: {target.excerpt!r}"
                if not 1 <= target.page <= doc.parsed.page_count:
                    raise ValueError(f"invalid physical ground truth page: {context}")
                if normalize_evidence(target.excerpt) not in normalize_evidence(
                    doc.parsed.pages[target.page - 1].text
                ):
                    raise ValueError(
                        f"ground truth evidence not found in raw PDF: {context}"
                    )
                # Every declared alternative must be real and retrievable. This
                # stronger invariant also guarantees one eligible match/group.
                if not any(target_matches(c, target) for c in eligible_chunks):
                    raise ValueError(
                        f"ground truth evidence is not retrievable after cleaning/chunking: {context}"
                    )
                langs = set(doc.record.language.split("-"))
                relations.append(
                    "same_language" if item["language"] in langs else "cross_language"
                )
                alternatives.append(target)
            if not alternatives:
                raise ValueError(f"invalid empty evidence group: {item['id']}")
            groups.append(EvidenceGroup(tuple(alternatives)))
        if bool(groups) != item["answerable"]:
            raise ValueError(
                "answerable needs evidence groups; no-answer must have none"
            )
        negative_type = item.get("negative_type")
        if not item["answerable"] and negative_type not in {"obvious", "hard_domain"}:
            raise ValueError("no-answer needs obvious/hard_domain negative_type")
        if item["answerable"] and negative_type is not None:
            raise ValueError("answerable must not have negative_type")
        # Mixed expected sources: conservatively cross-language if any target
        # needs another language. zh-en supports either query language.
        relation = (
            "cross_language" if "cross_language" in relations else "same_language"
        )
        queries.append(
            EvaluationQuery(
                item["id"],
                item["query"],
                item["language"],
                item["category"],
                item["answerable"],
                tuple(groups),
                item["judgment_mode"],
                negative_type,
                relation,
            )
        )
    return queries


def relevant(result, query):
    return any(
        target_matches(result.chunk, t)
        for g in query.evidence_groups
        for t in g.alternatives
    )


def metric_summary(rows):
    rows = [r for r in rows if r["answerable"]]
    n = len(rows)
    return {
        "count": n,
        **{
            f"Hit@{k}": sum(
                r["first_complete_rank"] is not None and r["first_complete_rank"] <= k
                for r in rows
            )
            / n
            if n
            else None
            for k in (1, 3, 5)
        },
        "MRR@5": sum(
            1 / r["first_complete_rank"] if r["first_complete_rank"] else 0
            for r in rows
        )
        / n
        if n
        else None,
        "interpretation": "diagnostic only",
    }


def judge_results(q: EvaluationQuery, results: list[RetrievalResult]) -> dict:
    satisfied, complete, at_k = set(), None, {}
    for i in range(1, 6):
        if i <= len(results):
            satisfied.update(
                j
                for j, g in enumerate(q.evidence_groups)
                if any(target_matches(results[i - 1].chunk, t) for t in g.alternatives)
            )
        if i in (1, 3, 5):
            at_k[str(i)] = len(satisfied)
        success = (
            bool(satisfied)
            if q.judgment_mode == "any"
            else bool(q.evidence_groups) and len(satisfied) == len(q.evidence_groups)
        )
        if success and complete is None:
            complete = i
    return {
        **asdict(q),
        "first_complete_rank": complete,
        "groups_satisfied_at_k": at_k,
        "top1_score": results[0].score if results else None,
        "results": [{**asdict(r), "judged_relevant": relevant(r, q)} for r in results],
    }


def evaluate(retriever: Retriever, queries: list[EvaluationQuery], *, depth=5) -> dict:
    if depth != 5 or not queries:
        raise ValueError("evaluation needs queries and retrieval depth = 5")
    return summarize_cases(
        [judge_results(q, retriever.search(q.query, top_k=depth)) for q in queries]
    )


def ranking_sha256(cases) -> str:
    """Freeze scores, ranks, parent payloads and complete historical passage traces."""
    value = [
        {
            "id": c["id"],
            "query": c["query"],
            "results": [
                {k: v for k, v in r.items() if k != "judged_relevant"}
                for r in c["results"]
            ],
            "passage_trace": c.get("passage_trace"),
        }
        for c in cases
    ]
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def rejudge(cases, queries: list[EvaluationQuery]) -> dict:
    """Rejudge saved results without retrieval, model loading or encoding."""
    before = ranking_sha256(cases)
    by_id = {q.id: q for q in queries}
    if (
        not cases
        or len(by_id) != len(queries)
        or len({c["id"] for c in cases}) != len(cases)
        or set(by_id) != {c["id"] for c in cases}
    ):
        raise ValueError("stored cases and queries must have identical unique IDs")
    rows = []
    for old in cases:
        q = by_id[old["id"]]
        for field in (
            "query",
            "language",
            "category",
            "answerable",
            "judgment_mode",
            "negative_type",
            "language_relation",
        ):
            if old[field] != getattr(q, field):
                raise ValueError(f"query semantics/metadata changed: {q.id} {field}")
        if len(old["results"]) > 5 or [r["rank"] for r in old["results"]] != list(
            range(1, len(old["results"]) + 1)
        ):
            raise ValueError("stored Top-5 must have consecutive ranks")
        results = [
            RetrievalResult(
                r["rank"], r["score"], KnowledgeChunk(**r["chunk"]), r["retriever"]
            )
            for r in old["results"]
        ]
        judged = judge_results(q, results)
        row = deepcopy(old)
        row.update({k: v for k, v in judged.items() if k != "results"})
        for result, new in zip(row["results"], judged["results"], strict=True):
            result["judged_relevant"] = new["judged_relevant"]
        if "passage_trace" in old:
            # Trace bytes/annotations are historical and remain untouched.
            passages = [
                replace(r, chunk=replace(r.chunk, text=t["passage_excerpt"]))
                for r, t in zip(results, old["passage_trace"], strict=True)
            ]
            row["first_complete_passage_rank"] = judge_results(q, passages)[
                "first_complete_rank"
            ]
        rows.append(row)
    if ranking_sha256(rows) != before:
        raise RuntimeError("rejudgment changed frozen rankings")
    return summarize_cases(rows)


def summarize_cases(rows):
    answerable = [r for r in rows if r["answerable"]]
    negatives = [r for r in rows if not r["answerable"]]
    slices = {}
    for field, name in [
        ("language", "by_query_language"),
        ("language_relation", "by_language_relation"),
        ("category", "by_category"),
    ]:
        slices[name] = {
            v: metric_summary([r for r in answerable if r[field] == v])
            for v in sorted({r[field] for r in answerable})
        }

    def expected(r):
        return {
            t["document_id"] for g in r["evidence_groups"] for t in g["alternatives"]
        }

    slices["by_expected_document"] = {
        doc: metric_summary([r for r in answerable if doc in expected(r)])
        for doc in sorted(set().union(*(expected(r) for r in answerable)))
    }
    scores = {}
    for name, group in [
        ("answerable", answerable),
        ("obvious", [r for r in negatives if r["negative_type"] == "obvious"]),
        ("hard_domain", [r for r in negatives if r["negative_type"] == "hard_domain"]),
    ]:
        scores[name] = {
            "distribution": distribution(
                [r["top1_score"] for r in group if r["top1_score"] is not None]
            ),
            "values": [{"query_id": r["id"], "score": r["top1_score"]} for r in group],
            "query_count": len(group),
        }
    overall = metric_summary(rows)
    return {
        "metrics": {
            **overall,
            "answerable_query_count": len(answerable),
            "no_answer_query_count": len(negatives),
        },
        "overall": overall,
        **slices,
        "metric_definition": "Hit@K = fraction of answerable queries with at least one accepted evidence target in Top-K; all mode additionally requires every evidence group. MRR@5 uses first_complete_rank.",
        "retrieval_depth": 5,
        "top1_scores": scores,
        "no_answer_behavior": {
            "queries_returning_results": sum(bool(r["results"]) for r in negatives),
            "queries_returning_empty": sum(not r["results"] for r in negatives),
            "correct_hits": 0,
            "threshold": None,
        },
        "cases": rows,
    }
