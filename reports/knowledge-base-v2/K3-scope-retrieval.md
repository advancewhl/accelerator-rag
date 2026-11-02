# K3：版本感知检索、API 与目录

实现日期：2026-11-02　｜　状态：代码与单元测试完成；未在生产索引上验证

## 1. 统一范围契约

`src/accelerator_rag/retrieval/scope.py` 的 `RetrievalScope` 在请求入口生成一次，贯穿：

- BM25 先筛选后评分；
- E5 / Qwen3 两路 dense 在 Qdrant 查询时按 payload 过滤；
- 同页补全只补同修订且 allowed 的邻居；
- reranker 只看到 allowed 候选；
- 第二轮补检索继续使用同一 scope。

默认策略：`usage_status in {current, reference}`、`access_scope=internal`、允许旧 payload 缺失元数据。`RagService.answer()` 在调用方未传 scope 时会套用该默认策略；旧式 `{"query":...}` 请求因此仍能检索 v1 块（元数据为空），但不会把 Schema v2 的 `historical`/`pending_review` 块带进默认答案。显式模式：

| 模式 | 行为 |
| --- | --- |
| `default` | 当前 + 参考；可选 topic/kind/role 过滤 |
| `version` | 必须给 `revision_ids` 或 `family_ids`；包含全部可查询状态 |
| `reference` | 显式参考，包含 `pending_review` |
| `compare` | **未实现**，返回 422 `COMPARE_NOT_IMPLEMENTED` |

## 2. 候选筛选发生在选取之前

| 路径 | 实现 |
| --- | --- |
| BM25 | 评分循环内先 `scope.allows(chunk)`，不合格父块不占 top_k；空集合返回 `[]` |
| Dense | `QdrantPassageStore.search_passages(..., query_filter=...)` 在服务端过滤；候选上限按过滤后点数计算 |
| Dense 双路 | 同一 scope 传给 E5/Qwen3；聚合前再次防御性过滤 |
| 同页补全 | anchor 必须 allowed；邻居先按 scope 过滤再取前 6 |
| Workflow | 每轮 `retrieve` 都传 scope |
| Reranker | 只接收 allowed 候选 |

**没有**采用“先取前 N 再丢弃旧版本”。默认 scope 也构造服务端 filter：只允许 current/reference + internal，并用显式空值/unknown 分支接纳旧 v1 payload；只有调用方完全未传 scope（历史直接调用）才跳过服务端 filter。

## 3. Qdrant filter

`build_scope_filter()` 翻译七个轴：

- `revision_ids` → `document_id` MatchAny
- `family_ids` → `family_id` MatchAny，或旧 payload 的 `document_id` 回退
- `document_kinds` / `evidence_roles` / `topics` → 对应字段 MatchAny
- `usage_statuses` → `usage_status` MatchAny，或空/null/`unknown`
- `access_scopes` → `access_scope` MatchAny，或空/null/`unknown`

已在本机 qdrant-client 1.18.0 验证 `FieldCondition`、`MatchAny`、`MatchValue`、`IsEmptyCondition`、嵌套 `Filter` 可用。`version_scope` 的 `allow_unknown_usage=False` 会排除旧 payload；要显式查询旧块，需允许 unknown，或先用 Schema v2 重建索引。

## 4. API 与响应

`POST /v1/rag/answer`：

```json
{
  "query": "问题",
  "scope": {
    "mode": "version",
    "release_id": "kb-2.0.0-rc.1",
    "revision_ids": ["shine-timing-system-design-rev-..."],
    "usage_statuses": ["historical", "reference"]
  }
}
```

- 旧请求 `{"query": "..."}` 行为不变。
- 顶层与 scope 内均 `extra=forbid`；`revision_ids`/`family_ids` 必须是 slug，`document_kinds`/`topics`/`usage_statuses` 必须属于受控词表，否则 422。
- 请求中的 `release_id` 必须等于当前运行时配置的发布号；未知/不匹配分别返回 422 `RELEASE_NOT_CONFIGURED` / `RELEASE_NOT_FOUND`，不会把客户端声称的发布号回显成实际检索的索引。
- `mode=version` 缺 revision/family → 422 `VERSION_SCOPE_REQUIRED`。
- `mode=compare` → 422 `COMPARE_NOT_IMPLEMENTED`。
- 响应新增 `release_id`、`retrieval_scope`；现有字段保留。

`GET /v1/rag/releases/current` 返回发布号、构建号、文档/修订/族/索引节计数。无 manifest 时 `build_id=unknown`，不编造。

## 5. 目录

`DocumentCatalog` 新增每文档：

`revision_labels`、`family_ids`、`usage_statuses`、`document_kinds`、`evidence_roles`、`approval_statuses`、`access_scopes`、`position_kinds`。

顶层新增 `families`：按 `effective_family_id` 分组，列出修订、版本标签、使用状态、批准状态和适用范围令牌。旧 chunk 缺失字段统一 `unknown`；族回退到 `document_id`；不暴露 `source_path` 或绝对路径。`reader_available` 仅对 PDF/Markdown 为 true；DOCX/PPTX/XLSX 的 `document_url` 为 null，UI 禁用“阅读原文”，阅读页属于后续发布包。`access_scope=restricted` 的 chunk 不进入目录，受限原文不会出现在下载/view 接口。

## 6. 验证

| 检查 | 结果 |
| --- | --- |
| K3 新增测试 | 32 项（scope 过滤、API、catalog） |
| 全量测试（K3 完成时） | **365 passed, 1 skipped**（skip 为无 tesseract）；K2/K4 合并后最终 **454 passed, 2 skipped** |
| Ruff | 修改/新增文件通过 |
| 真实 Qdrant filter 捕获 | 通过（fake client + 实际 query_filter 断言） |

## 7. 未验证 / 剩余风险

1. **未在生产双路索引上验证**：本机无 `/workspace`、无 GPU、无冻结索引；Qdrant 过滤只在单元测试与本机客户端模型上验证。
2. **旧 v1 payload 的空值语义**：默认 filter 用 `IsEmpty`/空字符串/`unknown` 显式接纳旧 payload；已在测试中验证，但生产 Qdrant 版本需在上线前复测。父块级 `scope.allows` 仍作为防御层保留。
3. **未建 payload index**：大集合上过滤可能较慢。
4. **`compare` 未实现**：独立证据分组与差异呈现仍是 K3 剩余项。
5. **release manifest 未接入**：`build_id` 恒为 unknown；真实发布清单/附件计数待 K4。
6. **`revision_count` 语义**：当前等于 catalog 行数（每个 document_id 一个修订）；多修订 payload 落地后需重定义。
7. **阅读器未覆盖 DOCX/PPTX/XLSX**：`/view` 只对 PDF/Markdown 返回阅读页；其他格式返回 501 `READER_NOT_IMPLEMENTED`，不会静默套用 Markdown 阅读器。段落/幻灯片/单元格阅读页与冻结阅读副本属于 K4 发布包。
