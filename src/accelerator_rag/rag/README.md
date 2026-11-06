# 独立 RAG 代码目录

本目录实现基于原始文档证据的问答服务。总体导航见 [RAG 文档入口](../../../docs/rag/README.md)，启动和排障见 [生产运行手册](../../../docs/runbooks/rag-production.md)。

## 模块职责

| 文件 | 职责 |
| --- | --- |
| `__main__.py` | `python -m accelerator_rag.rag` 入口，支持 HTTP 服务和单次命令行问答。 |
| `runtime.py` | 加载已签名索引与本地模型，构建运行时，检查生成接口。 |
| `api.py` | HTTP 问答、健康检查、文档目录、原件/正文/媒体阅读、表格精确查询（`/v1/rag/structured/lookup`，返回排序行、表头—值对与原表定位链接）和静态资源路由。 |
| `service.py` | 请求隔离、共享 GPU 检索锁、请求 ID 和过程记录。 |
| `workflow.py` | 检索前拆题、召回、证据选择、核查和定向补检索。 |
| `retrieval.py` | BM25、双路语义和结构化精确行候选融合；同页/阅读顺序邻近补全（统一重排前预留位置）和统一重排，精确命中优先保留。 |
| `context.py` | 保留规范父块，构建请求内稳定的来源与片段 ID。 |
| `evidence.py` | 按覆盖、冲突和预算选择证据子集，区分版本比较；只保留冲突一侧时相关需求保留冲突状态。 |
| `answer.py` | 结构化输出契约、证据评估、答案综合、数值检查、完整性核查和引用解析。 |
| `catalog.py` | 从实际索引生成只读文档目录、去重收录数及 PDF 页数。 |
| `reader.py`、`release.py` | Office/表格规范化正文阅读（发布快照优先）与发布身份。 |
| `__init__.py` | 导出 `RagService`。 |

## 请求流转

HTTP 请求依次进入 `api.py`、`runtime.py`、`service.py` 和 `workflow.py`。流程先调用 `answer.py` 拆题，再交给 `retrieval.py` 召回、`context.py` 建立片段、`evidence.py` 选择子集，最后生成并核查回答。缺项进入有界补检索。

正式配置使用该闭环；`service.py` 保留旧检索接口兼容路径，供已有调用与测试使用。两条路径的历史验收结果不能混合统计。

## 前端文件

| 文件或目录 | 用途 |
| --- | --- |
| `web/index.html`、`app.js`、`workbench.css` | 工作台三视图：文档问答（多资料范围、需求覆盖、引用）、表格查询（精确行、定位原表）、资料库（分组、筛选、多选范围）；本机保存查询记录。 |
| `web/office-document.html`、`office-document.js`、`style.css` | Office/表格正文阅读页：块锚点、表格行高亮（`row=`）、大表筛选、图片与公式。 |
| `web/markdown-document.*` | Markdown 原文阅读页。 |
| `web/pdf-reader.js` | 当前页面内的 PDF 阅读器。 |
| `web/document.html`、`document.js` | 独立 PDF 查看路由使用的页面。 |
| `web/katex/` | 本地公式渲染资源及许可证。 |
| `web/markdown/` | 本地 Markdown 渲染资源、版本来源及许可证。 |
| `web/pdfjs/` | 本地 PDF.js、字体、字符映射和解码资源；来源见 `source.json`。 |

第三方资源与手写业务代码分别审查。保留其许可证、字体和解码文件；文件数量不能作为本项目新增业务模块数量。

## 相关文件

- [生产配置](../../../config/rag-production.json)。
- [测试目录](../../../tests/rag)。
- [证据闭环设计](../../../docs/architecture/rag-evidence-workflow.md)。
- [相对上次提交的变更说明](../../../docs/rag/changes-since-4099ce1.md)。
