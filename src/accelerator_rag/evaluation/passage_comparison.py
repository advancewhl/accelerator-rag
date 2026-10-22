"""Frozen-query A/B diagnostics. Never selects evidence from search rankings."""

from collections import Counter
from dataclasses import asdict
import re
from accelerator_rag.embedding import document_embedding_text
from accelerator_rag.evaluation.retrieval import normalize_evidence, target_matches


def truncation_diagnosis(embedder, queries, chunks, dense_a):
    old = {c["id"]: c for c in dense_a["cases"]}
    relevant_ids = {
        c.chunk_id
        for q in queries
        for g in q.evidence_groups
        for t in g.alternatives
        for c in chunks
        if target_matches(c, t)
    }
    audited = {}
    prefixes = {}
    for c in chunks:
        if c.chunk_id in relevant_ids:
            text = document_embedding_text(c)
            audited[c.chunk_id] = embedder.audit_inputs([text])[0]
            prefixes[c.chunk_id] = embedder.visible_input_prefix(text)
    rows = []
    for q in queries:
        if not q.answerable:
            continue
        groups = []
        for g in q.evidence_groups:
            matches = []
            for t in g.alternatives:
                for c in chunks:
                    if not target_matches(c, t):
                        continue
                    full = normalize_evidence(document_embedding_text(c))
                    prefix = normalize_evidence(prefixes[c.chunk_id])
                    title_size = len(normalize_evidence(c.document_title))
                    body = full[title_size:]
                    needle = normalize_evidence(t.excerpt)
                    spans = [
                        (m.start(), m.end())
                        for m in re.finditer(re.escape(needle), body)
                    ]
                    if not spans or not full.startswith(prefix):
                        position = "unclassified_normalization_boundary"
                    else:
                        cutoff = max(0, len(prefix) - title_size)
                        if any(b <= cutoff for a, b in spans):
                            position = "fully_before_limit"
                        elif any(a < cutoff < b for a, b in spans):
                            position = "crosses_limit"
                        else:
                            position = "fully_after_limit"
                    matches.append(
                        {
                            "target": asdict(t),
                            "parent_chunk_id": c.chunk_id,
                            **audited[c.chunk_id],
                            "evidence_position": position,
                        }
                    )
            groups.append(matches)
        hidden_groups = [
            all(
                m["evidence_position"] in {"crosses_limit", "fully_after_limit"}
                for m in group
            )
            for group in groups
        ]
        needs_after = (
            any(hidden_groups) if q.judgment_mode == "all" else all(hidden_groups)
        )
        any_trunc = any(m["would_truncate"] for group in groups for m in group)
        rows.append(
            {
                "query_id": q.id,
                "stage25_failure": old[q.id]["first_complete_rank"] is None,
                "relevant_parent_would_truncate": any_trunc,
                "required_group_not_fully_visible_in_any_direct_parent": needs_after,
                "groups": groups,
            }
        )
    failures = [r for r in rows if r["stage25_failure"]]
    return {
        "position_method": "Real tokenizer max-length offsets -> source prefix -> deterministic normalized evidence matching. Ambiguous normalization at boundary is unclassified, never guessed. This describes evidence position, not embedding understanding or retrieval causality.",
        "answerable_queries": len(rows),
        "stage25_failure_count": len(failures),
        "failures_with_truncating_relevant_parent": sum(
            r["relevant_parent_would_truncate"] for r in failures
        ),
        "failures_with_required_group_not_fully_visible": sum(
            r["required_group_not_fully_visible_in_any_direct_parent"] for r in failures
        ),
        "position_counts": dict(
            Counter(
                m["evidence_position"]
                for r in rows
                for group in r["groups"]
                for m in group
            )
        ),
        "queries": rows,
    }


def query_comparison(a, b):
    prior = {c["id"]: c for c in a["cases"]}
    rows = []
    for case in b["cases"]:
        if not case["answerable"]:
            continue
        old = prior[case["id"]]
        before = old["first_complete_rank"]
        after = case["first_complete_rank"]
        status = (
            "unchanged"
            if before == after
            else "improved"
            if (after or 6) < (before or 6)
            else "regressed"
        )
        rows.append(
            {
                "query_id": case["id"],
                "stage25_first_complete_rank": before,
                "stage25_Hit@5": before is not None,
                "stage26_first_complete_rank": after,
                "stage26_Hit@5": after is not None,
                "status": status,
                "stage25_top3": old["results"][:3],
                "stage26_top3": case["results"][:3],
                "matched_passages": case["passage_trace"][:3],
            }
        )
    return {"counts": dict(Counter(r["status"] for r in rows)), "queries": rows}


def comparison_markdown(r):
    import json
    from accelerator_rag.evaluation.reporting import _cell

    lines = [
        "# RAG Stage 2.6 Dense Passage Compatibility",
        "",
        "本轮只改变 Dense 表示。Corpus、eligibility、BM25、query set、query template、模型和余弦距离保持一致。",
        "",
        "## 总体 A/B",
        "",
        "| 检索器 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("bm25", "dense_a", "dense_b"):
        m = r[name]["metrics"]
        lines.append(
            "| "
            + name
            + " | "
            + " | ".join(
                str(m[k]) if k == "count" else f"{m[k]:.4f}"
                for k in ("count", "Hit@1", "Hit@3", "Hit@5", "MRR@5")
            )
            + " |"
        )
    for slice_name in (
        "by_query_language",
        "by_language_relation",
        "by_category",
        "by_expected_document",
    ):
        lines += [
            "",
            f"## {slice_name}",
            "",
            "所有切片均为 diagnostic only。zh-en 支持两种语言；混合来源保守归为 cross_language。",
            "",
            "| 切片 / 检索器 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for key in r["dense_a"][slice_name]:
            for name in ("dense_a", "dense_b"):
                m = r[name][slice_name][key]
                lines.append(
                    "| "
                    + key
                    + " / "
                    + name
                    + " | "
                    + " | ".join(
                        str(m[k]) if k == "count" else f"{m[k]:.4f}"
                        for k in ("count", "Hit@1", "Hit@3", "Hit@5", "MRR@5")
                    )
                    + " |"
                )
    lines += [
        "",
        "## 全部 answerable query 回归表",
        "",
        "| Query | A rank | A Hit@5 | B rank | B Hit@5 | status |",
        "|---|---:|---|---:|---|---|",
    ]
    for row in r["query_comparison"]["queries"]:
        lines.append(
            f"| {row['query_id']} | {row['stage25_first_complete_rank']} | {row['stage25_Hit@5']} | {row['stage26_first_complete_rank']} | {row['stage26_Hit@5']} | {row['status']} |"
        )
    lines += [
        "",
        "## 变化与诊断 case",
        "",
        "以下展示全部变化，并补足至少 5 个诊断 case；未变化的问题不伪称改善。",
        "",
    ]
    cases = r["query_comparison"]["queries"]
    selected = [c for c in cases if c["status"] != "unchanged"]
    diagnosis_by_id = {q["query_id"]: q for q in r["truncation_diagnosis"]["queries"]}
    remaining = sorted(
        [c for c in cases if c not in selected],
        key=lambda c: (
            not diagnosis_by_id[c["query_id"]]["relevant_parent_would_truncate"],
            c["query_id"],
        ),
    )
    selected += remaining[: max(0, 5 - len(selected))]
    for c in selected:
        lines += [f"### {c['query_id']}（{c['status']}）", ""]
        for label, key in [("A", "stage25_top3"), ("B", "stage26_top3")]:
            for result in c[key]:
                chunk = result["chunk"]
                lines += [
                    f"- {label} rank {result['rank']}，score {result['score']:.6f}，`{chunk['document_id']}`，物理页 {chunk['page_start']}，`{chunk['chunk_id']}`。",
                    "  " + _cell(chunk["text"])[:300],
                ]
        lines += ["", "命中 passage：", ""]
        for t in c["matched_passages"]:
            lines += [
                f"- parent `{t['parent_chunk_id']}`，passage ordinal {t['passage_ordinal']}，score {t['passage_score']:.6f}。",
                "  " + _cell(t["passage_excerpt"])[:380],
            ]
        lines.append("")
    for name, title in [
        ("passage_statistics", "Passage 统计与预算"),
        ("truncation_diagnosis", "历史截断与证据位置"),
        ("controls", "控制变量核验"),
        ("index", "索引与耗时"),
        ("metadata", "可复现信息"),
    ]:
        value = r[name]
        if name == "truncation_diagnosis":
            value = {k: v for k, v in value.items() if k != "queries"}
        lines += [
            f"## {title}",
            "",
            "```json",
            json.dumps(value, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    lines += [
        "## 负例分数对照",
        "",
        "| 检索器 | 类型 | 问题数 | 分布 |",
        "|---|---|---:|---|",
    ]
    for name in ("dense_a", "dense_b"):
        for label in ("answerable", "obvious", "hard_domain"):
            values = r[name]["top1_scores"][label]
            lines.append(
                f"| {name} | {label} | {values['query_count']} | {_cell(values['distribution'])} |"
            )
    lines += [
        "",
        "没有实现 score threshold。分数相似不等于问题可回答。零截断证明输入适配，不保证模型理解证据。公式损坏、目录及页眉残留仍属于已知限制。",
        "",
    ]
    return "\n".join(lines)
