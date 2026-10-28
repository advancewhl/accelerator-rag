"""Bounded exhaustive coverage selection under source, conflict and token limits."""

from itertools import combinations
import json
import re

from .answer import Selection


def choose_subset(
    context, assessment, count_tokens, *, max_sources=5, token_budget=6000, query=""
):
    """Maximize coverage, then penalize repeated text and context cost.

    Enumerate bounded candidates using conservative additive costs, then verify
    actual serialized tokens. This is not a corpus-wide optimum. Conflicting
    evidence is a hard constraint, stronger than a soft penalty.
    """
    if type(max_sources) is not int or not 1 <= max_sources <= 5:
        raise ValueError("invalid selected source limit")
    if type(token_budget) is not int or token_budget < count_tokens("[]"):
        raise ValueError("token budget is too small")
    records = {r["source_id"]: r for r in json.loads(context.model_content)}
    sizes = {
        sid: count_tokens(json.dumps([record], ensure_ascii=False))
        for sid, record in records.items()
    }
    sources = list(context.sources)
    bundles = {r.id: [r.span_ids, *r.alternatives] for r in assessment.requirements}
    options = {
        rid: [{context.spans[s][0] for s in bundle} for bundle in values if bundle]
        for rid, values in bundles.items()
    }
    needs = {
        rid: set().union(*values) if values else set()
        for rid, values in options.items()
    }
    compare_versions = bool(
        re.search(r"对照|对比|比较|各自|分别|\bcompare\b|\bcontrast\b", query, re.I)
        and re.search(r"版本|年份|年代|年.*文档|\bversions?\b|\byears?\b|\beditions?\b", query, re.I)
    )
    hard_conflicts, scope_differences = [], []
    for conflict in assessment.conflicts:
        versions = {
            context.sources[sid].chunk.document_version for sid in conflict.source_ids
        }
        # In an explicit version comparison, different version statements are
        # objects of the comparison. Preserve both with their source labels;
        # never force them into one operating condition or a common value.
        destination = (
            scope_differences
            if compare_versions and len(versions) > 1 and "unknown" not in versions
            else hard_conflicts
        )
        destination.append(conflict)
    conflicts = [set(c.source_ids) for c in hard_conflicts]
    texts = {sid: " ".join(context.sources[sid].chunk.text.split()) for sid in sources}
    best, best_value = (), 0.0
    for size in range(1, min(max_sources, len(sources)) + 1):
        for subset in combinations(sources, size):
            selected = set(subset)
            cost = sum(sizes[sid] for sid in subset)
            if cost > token_budget or any(c <= selected for c in conflicts):
                continue
            complete = sum(
                r.supported and any(option <= selected for option in options[r.id])
                for r in assessment.requirements
            )
            partial = sum(bool(needs[r.id] & selected) for r in assessment.requirements)
            duplicates = sum(texts[a] == texts[b] for a, b in combinations(subset, 2))
            relevance = sum(
                max(0.0, min(1.0, context.sources[sid].score)) for sid in subset
            )
            value = (
                100 * complete
                + 10 * partial
                - 3 * duplicates
                - cost / token_budget
                - 0.05 * size
                + 0.01 * relevance
            )
            if value > best_value:
                # Tokenizers are not additive at record boundaries. Check the
                # actual serialized subset before accepting it.
                if count_tokens(context.subset(subset).model_content) <= token_budget:
                    best, best_value = subset, value
    selected_context = context.subset(best)
    selected_support = []
    for original in assessment.requirements:
        support = original.model_copy(deep=True)
        available = [
            bundle
            for bundle in bundles[original.id]
            if bundle and all(s in selected_context.spans for s in bundle)
        ]
        if available:
            chosen = min(
                available,
                key=lambda bundle: (
                    sum(len(context.spans[s][1]) for s in bundle),
                    len(bundle),
                ),
            )
            support.span_ids = list(chosen)
            support.supported = original.supported
            if chosen != original.span_ids:
                support.reason = "选中同一要求的等价证据组合；仅以该组合原文作答。"
        else:
            support.span_ids = list(
                dict.fromkeys(
                    s
                    for bundle in bundles[original.id]
                    for s in bundle
                    if s in selected_context.spans
                )
            )
            support.supported = False
        support.alternatives = []
        retained_items, missing_items = [], []
        for item in support.items:
            item.span_ids = [span for span in item.span_ids if span in support.span_ids]
            if item.span_ids:
                retained_items.append(item)
            else:
                missing_items.append(item.name)
        support.items = retained_items
        if missing_items:
            support.supported = False
            support.missing = "Missing list items: " + ", ".join(missing_items)
        if original.span_ids and not available:
            involved = [
                c.reason
                for c in hard_conflicts
                if set(c.source_ids) & needs[original.id]
            ]
            support.missing = support.missing or (
                "来源存在未解决的条件冲突：" + "；".join(involved)
                if involved
                else "当前证据预算下未能保留全部所需片段。"
            )
        selected_support.append(support)
    return (
        selected_context,
        Selection(requirements=selected_support),
        {
            "selected_sources": list(best),
            "objective": best_value,
            "context_tokens": count_tokens(selected_context.model_content),
            "token_budget": token_budget,
            "max_sources": max_sources,
            "conflicts": [c.model_dump() for c in hard_conflicts],
            "scope_differences": [c.model_dump() for c in scope_differences],
        },
    )
