"""Rank-based comparisons. Raw cosine is deliberately never compared across models."""

import json
from itertools import combinations


def answerable_ranks(report):
    return {
        c["id"]: c["first_complete_rank"] for c in report["cases"] if c["answerable"]
    }


def complementarity(bm25, dense):
    a, b = answerable_ranks(bm25), answerable_ranks(dense)
    if a.keys() != b.keys():
        raise ValueError("comparison query sets differ")
    groups = {k: [] for k in ("both_hit", "bm25_only", "dense_only", "both_miss")}
    for q in a:
        key = (
            "both_hit"
            if a[q] and b[q]
            else "bm25_only"
            if a[q]
            else "dense_only"
            if b[q]
            else "both_miss"
        )
        groups[key].append(q)
    return {"counts": {k: len(v) for k, v in groups.items()}, "query_ids": groups}


def pairwise(models):
    result = []
    for a, b in combinations(models, 2):
        x, y = answerable_ranks(models[a]), answerable_ranks(models[b])
        if x.keys() != y.keys():
            raise ValueError("comparison query sets differ")
        groups = {"a_wins": [], "b_wins": [], "same": []}
        for q in x:
            left, right = x[q] or 6, y[q] or 6
            groups[
                "a_wins" if left < right else "b_wins" if right < left else "same"
            ].append(q)
        result.append(
            {
                "model_a": a,
                "model_b": b,
                "basis": "first_complete_rank; missing=outside Top-5",
                "counts": {k: len(v) for k, v in groups.items()},
                "query_ids": groups,
            }
        )
    return result


def markdown(report):
    lines = [
        "# Stage 2.7 Embedding 模型受控比较",
        "",
        "所有小样本指标仅作诊断（diagnostic only）。完整 Top-5 父 Chunk、获胜 passage、分数和证据组判断见同名 JSON。",
        "",
        "## 实验边界",
        "",
        "固定 13 份 PDF、pdf-chunks-v3、资格策略、21 条可回答查询、11 条负例和 evidence-contract-v1。固定 cosine、passage policy 和 parent max-child 聚合。不同模型的 cosine 绝对值不横向比较。",
        "",
        "## 工程修正",
        "",
        "`index_document()` 替换指定文档并保留其他文档。`index_corpus()` 验证完整 corpus。两个 store 只共享 collection 基础能力。持久化回归测试验证重开、stale 清理、其他文档的 payload/vector 不变及编码次数。模型指纹逐块计算权重 SHA-256。",
        "",
        "## 总体指标",
        "",
        "Model | Hit@1 | Hit@3 | Hit@5 | MRR@5",
        "--- | ---: | ---: | ---: | ---:",
    ]
    for name, row in report["models"].items():
        m = row["evaluation"]["metrics"]
        lines.append(
            name
            + " | "
            + " | ".join(f"{m[k]:.4f}" for k in ["Hit@1", "Hit@3", "Hit@5", "MRR@5"])
        )
    for name, row in report["models"].items():
        lines += [
            "",
            f"## {name}",
            "",
            "### 身份和成本",
            "",
            "```json",
            json.dumps(
                {
                    k: v
                    for k, v in row.items()
                    if k
                    not in {
                        "evaluation",
                        "complementarity",
                        "known_failures",
                        "cross_language",
                    }
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "### 诊断切片",
            "",
            "切片 | 数量 | Hit@1 | Hit@3 | Hit@5 | MRR@5",
            "--- | ---: | ---: | ---: | ---: | ---:",
        ]
        for section in [
            "by_query_language",
            "by_language_relation",
            "by_category",
            "by_expected_document",
        ]:
            for key, m in row["evaluation"][section].items():
                lines.append(
                    key
                    + f" | {m['count']} | "
                    + " | ".join(
                        f"{m[k]:.4f}" for k in ["Hit@1", "Hit@3", "Hit@5", "MRR@5"]
                    )
                )
        lines += [
            "",
            "### BM25 互补性",
            "",
            "```json",
            json.dumps(row["complementarity"], indent=2),
            "```",
            "",
            "### 负例分数（仅在本模型内解释）",
            "",
            "组别 | 数量 | 最小值 | 中位数 | 最大值",
            "--- | ---: | ---: | ---: | ---:",
        ]
        for group, scores in row["evaluation"]["top1_scores"].items():
            d = scores["distribution"]
            if d["count"]:
                lines.append(
                    f"{group} | {d['count']} | {d['min']:.4f} | {d['median']:.4f} | {d['max']:.4f}"
                )
        lines += [
            "",
            "未设置拒答阈值。高分只表示相似性，领域负例仍会返回结果。",
            "",
            "### 逐条跨语言查询",
            "",
        ]
        for c in row["cross_language"]:
            lines += [
                f"- `{c['id']}`：查询语言 {c['query_language']}；目标文档语言 {c['target_languages']}；完整证据首次排名 {c['first_complete_rank']}；Top-5：{', '.join(c['top5_parent_ids'])}。"
            ]
        lines += ["", "### 已知失败逐条诊断", ""]
        for c in row["known_failures"]:
            lines += [
                f"#### {c['id']}",
                "",
                f"完整父 Chunk 证据首次排名：{c['first_complete_rank']}；仅按获胜 passage 判断的完整证据首次排名：{c.get('first_complete_passage_rank')}。",
                "",
            ]
            for r, trace in zip(c["results"], c["passage_trace"], strict=True):
                chunk = r["chunk"]
                lines += [
                    f"- Rank {r['rank']}：`{chunk['chunk_id']}`，第 {chunk['page_start']} 页；score {r['score']:.4f}；父 Chunk 匹配至少一组 evidence：{r['judged_relevant']}；获胜 passage `{trace['passage_id']}`；passage 本身匹配 evidence：{trace['matched_evidence']}。"
                ]
            lines.append("")
    if report.get("analysis_notes"):
        lines += ["## 人工证据复核与解释限制", ""]
        for note in report["analysis_notes"]:
            lines += [note, ""]
    lines += [
        "## 模型两两比较",
        "",
        "比较 first_complete_rank，双双缺失记为 same。",
        "",
        "```json",
        json.dumps(report["pairwise"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 结论",
        "",
        report.get("recommendation", "运行结束后按实测数据填写。"),
        "",
    ]
    if report["excluded"]:
        lines += [
            "## 排除的模型",
            "",
            "```json",
            json.dumps(report["excluded"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    result = "\n".join(lines)
    if report.get("validation_markdown"):
        result += "\n" + report["validation_markdown"]
    return result
