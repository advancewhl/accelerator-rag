"""Bounded requirement -> recall -> subset -> review -> targeted recall loop."""

from dataclasses import asdict, replace
import json
from time import perf_counter

from pydantic import Field, StrictStr

from .answer import (
    AnswerContractError,
    Contract,
    _call,
    _temporal_gap,
    extract_requirements,
    generate,
    resolve,
    select_evidence,
)
from .context import EvidenceContextBuilder
from .evidence import choose_subset


class SupplementaryQuery(Contract):
    requirement_id: StrictStr
    text: StrictStr = Field(min_length=1, max_length=1500)


class SupplementaryQueries(Contract):
    queries: list[SupplementaryQuery] = Field(min_length=1, max_length=3)


_QUERY_LIMIT = 8


def _retrieval_queries(query, requirements, limit=_QUERY_LIMIT):
    """Original question plus per-requirement English and local-language probes.

    Each requirement contributes an English paraphrase (``search_query``, or
    its own question when absent) and, when present, a verbatim local-language
    probe (``search_query_local``).  Duplicates are removed in construction
    order: original, English probes, local probes.

    A request must not fan out into 13 separate dense/lexical searches.  The
    cap first guarantees one primary probe per requirement (local language
    preferred because it preserves device, PV, terminal and version
    identifiers verbatim), then spends spare slots on English paraphrases.
    With six requirements the original plus six primaries fit in seven slots,
    leaving one bilingual synonym.  Survivors keep the construction order so
    retrieval traces stay stable.
    """

    english = [
        r.search_query.strip() or r.question.strip() for r in requirements
    ]
    local = [r.search_query_local.strip() for r in requirements]
    primary, secondary = [], []
    for requirement, english_text, local_text in zip(
        requirements, english, local, strict=True
    ):
        probe = local_text or english_text or requirement.question.strip()
        if probe:
            primary.append(probe)
        if local_text and english_text and english_text != local_text:
            secondary.append(english_text)
    ordered = list(
        dict.fromkeys(
            [query, *[text for text in english if text],
             *[text for text in local if text]]
        )
    )
    if len(ordered) <= limit:
        return ordered
    # Every requirement must get at least one dedicated probe.  The original
    # question is always first; primary probes follow in requirement order;
    # spare slots go to English paraphrases for the same requirements.
    priority = list(dict.fromkeys([query, *primary, *secondary]))
    keep = set(priority[:limit])
    return [text for text in ordered if text in keep][:limit]


def _supplement_queries(query, requirements, supplements, limit=_QUERY_LIMIT):
    """Targeted round-two probes, with the original/local identities retained."""

    targeted = [item.text.strip() for item in supplements if item.text.strip()]
    local = [
        requirement.search_query_local.strip()
        for requirement in requirements
        if requirement.search_query_local.strip()
    ]
    english = [
        requirement.search_query.strip() or requirement.question.strip()
        for requirement in requirements
    ]
    return list(
        dict.fromkeys([query, *targeted, *local, *english])
    )[:limit]


def plan_supplement(provider, query, requirements, missing, context, feedback):
    allowed = {r.id for r in requirements if r.id in missing}

    def check(result):
        if any(q.requirement_id not in allowed for q in result.queries):
            raise AnswerContractError(
                "supplementary query targets an unknown requirement"
            )

    return _call(
        provider,
        "submit_supplementary_queries",
        SupplementaryQueries,
        "只为 missing_requirements 生成最多 3 个定向补检索查询，不回答问题。"
        "用英文术语检索英文资料，可沿已有段落的术语追查上下文和连接；保留系统和设备范围。"
        "根据反馈明确缺什么；不能重复一个泛问题，也不能把猜测的保护功能或接线当成事实。"
        "历史回答与核查反馈不是证据。",
        {
            "query": query,
            "missing_requirements": [
                r.model_dump() for r in requirements if r.id in allowed
            ],
            "evidence": json.loads(context.model_content),
            "feedback": feedback,
        },
        check,
    ).queries


def run_workflow(
    provider,
    retriever,
    query,
    lock,
    count_tokens,
    *,
    max_rounds=2,
    token_budget=6000,
    audit=None,
    scope=None,
):
    started = perf_counter()
    requirements = extract_requirements(provider, query)
    trace = audit if audit is not None else {}
    trace.update(
        {
            "requirements": [r.model_dump() for r in requirements],
            "rounds": [],
            "scope": scope.describe() if scope is not None else None,
        }
    )
    queries = _retrieval_queries(query, requirements)
    merged, anchors, feedback, best = {}, [], None, None
    retrieval_seconds = rerank_seconds = 0.0
    for round_index in range(max_rounds):
        retrieval_started = perf_counter()
        retrieval_kwargs = {"anchors": anchors}
        if scope is not None:
            retrieval_kwargs["scope"] = scope
        with lock:
            hits, retrieval_trace = retriever.retrieve(
                query, queries, **retrieval_kwargs
            )
        duration = perf_counter() - retrieval_started
        rerank_seconds += retrieval_trace.get("rerank_seconds", 0)
        retrieval_seconds += max(0, duration - retrieval_trace.get("rerank_seconds", 0))
        for hit in hits:
            old = merged.get(hit.chunk.chunk_id)
            if old is not None and old.chunk != hit.chunk:
                raise ValueError("inconsistent request evidence")
            merged[hit.chunk.chunk_id] = hit
        ordered = sorted(merged.values(), key=lambda h: (-h.score, h.chunk.chunk_id))[
            :20
        ]
        builder = EvidenceContextBuilder(max_sources=20)
        context = builder.build([replace(h, rank=i) for i, h in enumerate(ordered, 1)])
        while len(ordered) > 1 and count_tokens(context.model_content) > 18000:
            ordered.pop()
            context = builder.build(
                [replace(h, rank=i) for i, h in enumerate(ordered, 1)]
            )
        if count_tokens(context.model_content) > 18000:
            raise AnswerContractError("candidate evidence exceeds request token budget")
        row = {
            "round": round_index + 1,
            "retrieval": retrieval_trace,
            "candidates": json.loads(context.model_content),
        }
        trace["rounds"].append(row)
        assessment = select_evidence(
            provider, query, requirements, context, assessment=True, feedback=feedback
        )
        selected, selection, subset_trace = choose_subset(
            context, assessment, count_tokens, token_budget=token_budget, query=query
        )
        row.update(
            {
                "assessment": assessment.model_dump(),
                "selected_support": selection.model_dump(),
                "subset": subset_trace,
                "results": [asdict(h) for h in selected.sources.values()],
            }
        )
        anchors = list(selected.sources.values()) or ordered[:3]
        missing = {r.id for r in selection.requirements if not r.supported}
        missing = {
            rid
            for rid in missing
            if not _temporal_gap(
                next(r.question for r in requirements if r.id == rid), context
            )
        }
        if missing and round_index + 1 < max_rounds:
            feedback = {
                r.id: {"reason": r.reason, "missing": r.missing}
                for r in selection.requirements
                if r.id in missing
            }
            supplements = plan_supplement(
                provider, query, requirements, missing, context, feedback
            )
            queries = _supplement_queries(query, requirements, supplements)
            row["supplementary_queries"] = [q.model_dump() for q in supplements]
            continue
        generation_audit = {}
        answer = generate(
            provider,
            query,
            selected,
            requirements=requirements,
            selection=selection.requirements,
            audit=generation_audit,
            retry_feedback=feedback,
        )
        result = resolve(answer, selected)
        row["generation"] = generation_audit
        row["response"] = result
        quality = (
            sum(r["supported"] for r in result["requirements"]),
            sum(r["coverage"] == "partial" for r in result["requirements"]),
        )
        if best is None or quality > best[0]:
            best = (quality, result, round_index + 1)
        if result["status"] == "answered" or round_index + 1 >= max_rounds:
            break
        missing = {
            r["id"]
            for r in result["requirements"]
            if not r["supported"] and not _temporal_gap(r["text"], context)
        }
        if not missing:
            break
        feedback = generation_audit
        supplements = plan_supplement(
            provider, query, requirements, missing, context, feedback
        )
        queries = _supplement_queries(query, requirements, supplements)
        row["supplementary_queries"] = [q.model_dump() for q in supplements]
    if best is None:
        raise AnswerContractError("workflow produced no answer")
    result = best[1]
    total = perf_counter() - started
    result["latency"] = {
        "retrieval_seconds": retrieval_seconds,
        "rerank_seconds": rerank_seconds,
        "generation_seconds": max(0, total - retrieval_seconds - rerank_seconds),
        "total_seconds": total,
    }
    trace["selected_round"] = best[2]
    return result, trace
