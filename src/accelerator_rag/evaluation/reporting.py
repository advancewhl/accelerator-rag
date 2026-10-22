"""Human-readable review reports generated from measured JSON, not hand-picked scores."""

from typing import Any


def _cell(value: Any) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    # Keep machine JSON/chunks untouched; render raw control/PUA evidence as
    # explicit code points rather than emitting binary Markdown or font boxes.
    return "".join(
        f"\\u{ord(char):04x}"
        if (
            ord(char) < 32
            or 0xE000 <= ord(char) <= 0xF8FF
            or 0xF0000 <= ord(char) <= 0xFFFFD
            or 0x100000 <= ord(char) <= 0x10FFFD
        )
        else char
        for char in text
    )


def audit_markdown(report: dict) -> str:
    overview, meta = report["overview"], report["metadata"]
    lines = [
        "# RAG Stage 2.5 Corpus Quality Audit",
        "",
        f"生成日期：{meta['generated_on']}。算法：`{meta['chunking_algorithm']}`。",
        f"配置：`{meta['chunking_config']}`；阈值：`{meta['audit_config']}`。",
        "",
        f"成功处理 {overview['successfully_ingested_documents']} 份 PDF，共 {overview['total_pages']} 页、"
        f"{overview['total_chunks']} 个 Chunk、{overview['total_chunk_chars']} 字符。"
        "统计保留短 Chunk；告警和候选污染不等于已确认错误。",
        "",
        "## 每篇文档",
        "",
        "| 文档 ID | 页数 | Chunk | 字符 | 空 Chunk 页 |",
        "|---|---:|---:|---:|---:|",
    ]
    for d in report["documents"]:
        lines.append(
            f"| {d['document_id']} | {d['page_count']} | {d['chunk_count']} | {d['chunk_chars']} | {d['pages_without_chunks']} |"
        )
    lines += [
        "",
        "## 长度与页面分布",
        "",
        "| 统计量 | Chunk 字符数 | 每页 Chunk 数（含 0） |",
        "|---|---:|---:|",
    ]
    for key in ["min", "p10", "p25", "median", "p75", "p90", "p95", "max", "mean"]:
        lines.append(
            f"| {key} | {report['chunk_lengths'].get(key)} | {report['page_distribution']['chunks_per_page'].get(key)} |"
        )
    lines += [
        "",
        f"极短 Chunk：{report['chunk_lengths']['very_short_chunks']}；"
        f"超长 Chunk：{report['chunk_lengths']['very_long_chunks']}。",
        f"无 Chunk 页面：{len(report['page_distribution']['pages_without_chunks'])}；"
        f"超过每页数量阈值的页面：{len(report['page_distribution']['pages_with_very_many_chunks'])}。",
        "",
        "## Parser 告警分布",
        "",
        "| 文档 ID | 空文本 | 疑似扫描 | 双栏 | 乱码 | 私用字符 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    warning_keys = [
        "empty_text",
        "possible_scanned_page",
        "possible_two_column",
        "possible_garbled_text",
        "private_use_characters",
    ]
    for doc in report["documents"]:
        lines.append(
            "| "
            + doc["document_id"]
            + " | "
            + " | ".join(str(doc["warning_counts"].get(k, 0)) for k in warning_keys)
            + " |"
        )
    lines.append(
        "| 全部 | "
        + " | ".join(str(report["parser_warnings"].get(k, 0)) for k in warning_keys)
        + " |"
    )
    lines += [
        "",
        "## 清洗后候选问题",
        "",
        "| 类型 | 次数 | 主要来源（次数） |",
        "|---|---:|---|",
    ]
    for kind, values in report["quality"].items():
        major = sorted(values["per_document"].items(), key=lambda pair: -pair[1])[:3]
        lines.append(
            f"| {kind} | {values.get('occurrences', values.get('count'))} | "
            + "; ".join(f"{d}: {c}" for d, c in major if c)
            + " |"
        )
    lines += [
        "",
        "内部连字符仅在 corpus 中存在无连字符拼写时列为候选；可能包含真实复合词。"
        "出版编号、版权词和独立数字也可能出现在有效正文中。审计不修改文本。",
        "",
        "## 三类重点文档",
        "",
    ]
    for prefix in [
        "european-xfel-full",
        "shine-accelerator-preliminary",
        "shine-accelerator-control",
    ]:
        doc = next(
            (d for d in report["documents"] if d["document_id"].startswith(prefix)),
            None,
        )
        if doc:
            lines += [
                f"### {doc['title']}",
                "",
                f"{doc['page_count']} 页、{doc['chunk_count']} 个 Chunk；无 Chunk 页面 {doc['pages_without_chunks']}。",
                f"告警：`{doc['warning_counts']}`。清洗后质量信号：`{doc['quality_occurrences']}`。",
                f"Chunk 长度：`{doc['chunk_lengths']}`。",
                "",
            ]
    lines += [
        "## 高优先级异常样本",
        "",
        "以下样本优先展示乱码、NULL 和私用字符，其次为版权词与断词候选。"
        "示例经过截取，精确位置与完整页面统计见同名 JSON。",
        "",
    ]
    for i, finding in enumerate(report["findings"], 1):
        lines += [
            f"{i}. **{finding['kind']}**，次数 {finding['count']}，`{finding['document_id']}`，"
            f"物理页 {finding['page_start']}～{finding['page_end']}，Chunk `{finding['chunk_id']}`。",
            "",
            "> " + _cell(finding.get("signal_context", finding["excerpt"]))[:550],
            "",
        ]
    lines += [
        "## 页面异常样本",
        "",
        "| 文档 | 物理页 | Chunk | 原始字符 | 图像 | 告警 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    page_samples = (
        report["page_distribution"]["pages_with_very_many_chunks"]
        + report["page_distribution"]["pages_without_chunks"]
    )[:30]
    for p in page_samples:
        lines.append(
            f"| {p['document_id']} | {p['page']} | {p['chunk_count']} | {p['raw_chars']} | {p['image_count']} | {_cell(p['warnings'])} |"
        )
    lines += [
        "",
        "## Stage 3 前的待处理事项",
        "",
        "1. 按上表主要文档和物理页审查私用字符、替换字符与表格文本；保留原始证据，确认可恢复性后再修。",
        "2. 对疑似扫描及无 Chunk 页面区分空白、图像页和文本提取失败；本阶段不做 OCR。",
        "3. 复核连字符与 boilerplate 候选，再决定通用清洗修正；本报告不宣称版面和公式语义已经恢复。",
        "",
        "## 可复现性与范围",
        "",
        f"版本记录：`{meta.get('git')}`。工作树为 dirty 时，提交号仅表示基点。",
        "语料仅包含 Registry 中的 PDF；未登记 PPTX/DOCX 不参与。百分位使用线性插值，页面分布包含没有 Chunk 的页面。",
        "耗时记录见 retrieval baseline JSON；原始文档哈希、代码哈希和完整异常归属见本报告 JSON。",
        "",
    ]
    if "cleaning_effects" in report:
        lines += ["## 确定性清洗结果", "", f"`{report['cleaning_effects']}`", ""]
    if "retrieval_eligibility" in report:
        import json

        lines += [
            "## Retrieval eligibility",
            "",
            "```json",
            json.dumps(report["retrieval_eligibility"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    return "\n".join(lines)


def baseline_markdown(report: dict) -> str:
    import json

    lines = [
        "# RAG Stage 2.5 Evidence Retrieval Baseline",
        "",
        "Hit@K = fraction of answerable queries with at least one accepted evidence target in Top-K",
        "",
        "all 模式还要求覆盖全部证据组。组内 OR；all 模式组间 AND，any 模式组间 OR。MRR@5 使用 first_complete_rank。",
        "证据必须同时匹配文档、物理页和规范化后的 Chunk 文本。无答案问题不进入指标分母。",
        "所有切片均为 diagnostic only，样本数不足以支持泛化结论。zh-en 文档支持中英文；存在跨语言目标时保守归入 cross_language。",
        "",
    ]
    for name in ("bm25", "dense"):
        lines += [f"## {name}", ""]
        for section in (
            "overall",
            "by_query_language",
            "by_language_relation",
            "by_category",
            "by_expected_document",
        ):
            lines += [
                f"### {section}",
                "",
                "| 切片 | count | Hit@1 | Hit@3 | Hit@5 | MRR@5 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            groups = (
                {"overall": report[name][section]}
                if section == "overall"
                else report[name][section]
            )
            for key, m in groups.items():
                values = [m[k] for k in ("count", "Hit@1", "Hit@3", "Hit@5", "MRR@5")]
                lines.append(
                    "| "
                    + key
                    + " | "
                    + " | ".join(
                        f"{v:.4f}" if isinstance(v, float) else str(v) for v in values
                    )
                    + " |"
                )
            lines.append("")
        lines += ["### Top-1 分数分布", ""]
        for label, values in report[name]["top1_scores"].items():
            lines += [
                f"- {label}（{values['query_count']} 条）：`{values['distribution']}`。"
            ]
        lines += ["", "### 逐条判断", ""]
        for case in report[name]["cases"]:
            lines += [
                f"**{case['id']}**：{case['query']}",
                "",
                f"first_complete_rank：`{case['first_complete_rank']}`；groups_satisfied_at_k：`{case['groups_satisfied_at_k']}`。",
                "",
            ]
            for r in case["results"][:3]:
                c = r["chunk"]
                lines += [
                    f"- Top {r['rank']}，score {r['score']:.6f}，`{c['document_id']}`，物理页 {c['page_start']}～{c['page_end']}，Chunk `{c['chunk_id']}`。",
                    "  " + _cell(c["text"])[:300],
                ]
            lines.append("")
    for key, title in [
        ("retrieval_eligibility", "检索资格"),
        ("embedding_input_audit", "Dense 输入审计"),
        ("stage_two_comparison", "Stage 2 对照"),
        ("ground_truth_validation", "Ground truth 可检索性"),
        ("index", "索引"),
        ("durations_seconds", "耗时"),
    ]:
        lines += [
            f"## {title}",
            "",
            "```json",
            json.dumps(report.get(key, {}), ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    lines += [
        "## 限制",
        "",
        "没有实现分数阈值。明显负例和领域负例分别记录；领域负例均为静态文档无法支持的指定时刻运行状态。"
        "公式损坏继续保留并审计，私用字符未做未验证映射。token 截断统计不等于已经证明截断是 Dense 失败原因。"
        "Stage 2 历史页级指标与新证据口径不可直接归因比较；另提供旧 Top-5 在新口径下的复判。",
        "",
    ]
    return "\n".join(lines)
