# 工作台与新格式阅读改进计划

日期：2026 年 11 月 2 日（设计与本地实施）。状态：W1、W2 已在代码层实现；W3、W4 部分实现；W5 完成图片/公式/媒体锚点部分，OCR 区域 overlay 与预览未做。生产发布与重建尚未执行。主任务见[新批次文档类型接入检查与改进计划](new-document-types-review.md)。

目标是让用户在工作台中完成“找到资料、选定范围、提出问题、核对原文”。优先解决本批新增资料看不了和查阅范围不清的问题。

## 1. 新增资料无法在线阅读的原因

**多数新增资料原本打不开，直接原因是新格式的阅读链路尚未接入。** 这与文件是否已被解析、是否进入索引是两回事；本轮已在代码层补上阅读链路，生产发布仍待重建。

按已保存生产构建记录和当前格式支持范围，207 份修订中，52 份为 PDF／Markdown，155 份为 DOCX、DOC、PPTX、XLSX。后面 155 份全部来自本批新增资料。

| 位置 | 原行为 | 用户看到的结果 | 本轮状态 |
| --- | --- | --- | --- |
| 文档目录 | 只对 PDF、Markdown 提供 `document_url` | 新格式的阅读按钮不可用 | 目录增加 `reader_kind`、`reader_available`、`download_url`；Office 也可打开正文 |
| 回答引用 | 非 PDF／Markdown 的 `document_url` 为 `null` | 引用可显示位置，但打不开 | citation 增加格式、治理状态、`source_block_ids` 与阅读链接 |
| `/view` 接口 | 生产运行时未登记 Office，先返回 404；仅在测试注入 `documents` 时触达 501 `READER_NOT_IMPLEMENTED` | 没有对应阅读页面 | Office 返回 `office-document.html`；未知格式仍 501 |
| 原文件接口 | Office 未登记，直接 404；若只登记而不改 MIME，会把 DOCX 声明为 PDF | 不能把该接口当作原件下载入口 | 显式 MIME、`Content-Disposition: attachment`、RFC 5987 中文文件名；PDF/Markdown 仍 inline |
| 正文接口 | 不存在 | 只能看 PDF/Markdown | 新增 `/v1/rag/documents/{id}/content`，分页、锚点、快照优先 |

前端的“该格式阅读页未接入”反映的是真实能力缺口；单纯改按钮文案、显示文件扩展名或刷新目录不能解决。

本次依据本地实现和已保存构建记录判断，未重新逐一访问线上文件。52 份指 48 个 PDF + 4 个 Markdown 文件，不等于本次逐一确认过全部链接可用；155 份指 119 DOCX + 15 DOC + 19 PPTX + 2 XLSX 个公开修订。

依据：[目录](../../src/accelerator_rag/rag/catalog.py)、[原文接口](../../src/accelerator_rag/rag/api.py)、[引用生成](../../src/accelerator_rag/rag/answer.py)、[工作台前端](../../src/accelerator_rag/rag/web/app.js)。

## 2. 第一优先：补齐各格式的实际阅读能力

| 格式 | 工作台阅读方式 | 引用定位 | 原件入口 | 本地状态 |
| --- | --- | --- | --- | --- |
| DOCX | 规范化正文按块渲染，标题、段落、表格、图片、备注分别显示；常见公式按 LaTeX 渲染 | `source_block_ids` + `position_locator` | 下载原始 DOCX | 已实现正文/图片/常见公式；排版预览/脚注未做 |
| DOC | 阅读转换件正文，明确标注原始格式 | 转换后的段落锚点 | 下载原始 DOC，转换件按需生成 | 已实现；LibreOffice 不可用时返回 503 |
| PPTX | 同页文本、标题、表格、图片与备注分别显示；对象按视觉顺序排列；缩略图后续补 | 幻灯片序号、形状定位与对象序号 | 下载原始 PPTX | 已实现正文/图片/对象顺序；缩略图未做 |
| XLSX | 工作表与表格正文；表头固定与命中行高亮后续补 | 工作表与单元格范围 | 下载原始 XLSX | 已实现整表正文；行窗口分页未做 |
| 扫描 PDF | 原页与 OCR 文字对照 | 物理页，后续补区域定位 | 保留 PDF 原件 | 原 PDF 阅读器可用；OCR 对照未做 |

阅读器优先读取发布包的 `parsed/<revision_id>.json` 快照；快照缺失时才按需解析原件，并在页面顶部标明“按原件即时解析”。这样既避免正常发布时临时重解析，也不把缺失快照伪装成一致内容。DOC 的转换件同样优先使用构建期快照。单文件超过 64 MiB 且没有快照时，阅读器拒绝按需解析并返回 503，要求发布快照；阈值可用 `reader_max_on_demand_bytes` 调整。

第一步就提供正确格式的原件下载，解决“只能看文件名”的问题；同时接入规范化正文阅读。派生 PDF 或幻灯片预览需要后续生成，但不能用不存在的页码充当定位。

Word 公式使用有效 LaTeX 源码和兼容渲染器。常见 OMML 结构（分式、上下标、根式、求和、矩阵等）已转 LaTeX 并由 KaTeX 渲染；无法可靠转换的结构保留 OMML 文本并标记 `latex_status=unresolved`，阅读器显示“公式未恢复，请对照原件”，不生成猜测公式。字号匹配与裁切核对仍未实现。

## 3. 第二优先：让目录说明资料能怎么用

原目录给文档统一显示“已收录 · 可检索”，把“已入索引”“默认可问”“能打开正文”混为一谈。本轮改为分别显示：

- 资料已收录，默认问答可用（`current`／`reference`）。
- 已收录，需选择版本或历史范围（`historical`）。
- 待核实，选择后可查阅，不等于现行依据（`pending_review`）。
- 仅原件，正文阅读不可用。

默认问答覆盖 121 个修订、5,921／8,431 个父块；其余 86 个本批新增修订、2,510 个父块需显式范围。目录读取服务返回的 `usage_statuses`，不把数量写死。

目录已增加格式和资料状态筛选，支持标题、版本、分类与主题搜索。“今天新增”暂不可用，因为运行时候选块不携带 `received_at`；需要发布包附带登记表快照或目录清单后才能提供。别名搜索同样缺少数据字段。

同一设备的同一文档按版本折叠这一条暂不启用：F11 已把 31 个操作手册修订拆为 16 个设备族并保留系列标签，但前端尚未按新族重新验证折叠；生产重建后应按“设备族内版本折叠、系列标签仅作分类”开放。

## 4. 第三优先：把资料选择接到问答

文档卡片已提供“在此资料中提问”。选择后，输入框上方显示范围 chip（文档标题、版本、资料状态），发送请求时构造 `{query, scope:{mode:"version", revision_ids:[...]}}`，不再把标题拼进问题文字。

范围 chip 可移除；移除后回到“全部默认资料”。切换范围只影响下一次查询，不自动重发当前问题。待核实资料也可显式选择，回答和引用继续显示其状态。

服务端 `scope` 原本已支持 `revision_ids`、`family_ids`、`usage_statuses`、`document_kinds`、`evidence_roles`、`topics`；本轮增加 `approval_statuses`。`revision_ids` 单次最多 32 条，因此 41 份待核实资料不能靠逐条枚举，应结合状态与主题筛选。

后续版本比较使用独立的两侧选择。当前服务尚未实现 `compare` 模式（返回 422 `COMPARE_NOT_IMPLEMENTED`），因此不展示可点击却无法完成的比较按钮。

## 5. 建议的工作区布局

沿用现有问答与右侧证据布局，先扩展内容，不优先进行整页视觉重做。

| 区域 | 内容 | 主要交互 |
| --- | --- | --- |
| 资料目录 | 筛选、最近新增、文档与版本 | 打开资料、选择查询范围 |
| 问答区 | 当前范围、问题、答案和缺失信息 | 在所选资料中提问，点击引用 |
| 原文区 | 格式对应的阅读器、命中位置及上下文 | 高亮、前后段／页切换、原件下载 |

在桌面端允许扩大原文区宽度；在窄屏上切换问答和原文。切换资料或回到目录时保留已输入问题、筛选条件和阅读位置，减少反复查找。当前已保留问题草稿与筛选条件，阅读位置恢复仍属于 W5。

引用卡显示标题、版本、资料性质、准确位置和短摘录。段落、幻灯片和单元格分别使用对应名称，不统一称为“页”。citation 已携带 `usage_status`、`approval_status`、`document_kind`、`content_role`、`review_status`、`formula_status`；前端在引用卡显示 OCR 待复核、备注、公式未恢复等状态。阅读器内的高亮仍只到块级，区域级高亮属于 W5。

## 6. 实施顺序与完成标准

| 顺序 | 工作 | 本地状态 | 用户可见的完成标准 |
| --- | --- | --- | --- |
| W1 | 原件下载、格式与内容类型 | 已实现 | 新格式文档能取得正确的原文件 |
| W2 | DOCX／DOC 结构化阅读、PPT 页面阅读、XLSX 表格阅读 | 已实现正文与分页；预览/缩略图/单元格窗口未做 | 点击引用能到对应段落、幻灯片或单元格 |
| W3 | 目录状态、格式筛选、最近新增 | 状态与格式筛选已实现；“最近新增/别名”缺数据 | 用户看得出已收录资料的阅读和查询方式 |
| W4 | 单文档／多文档范围与输入框标签 | 单文档范围 chip 已实现；多文档选择与待核实徽标细化未做 | 问答实际使用所选资料范围 |
| W5 | 图片、公式、OCR 对照和阅读位置保留 | 图片/公式/媒体锚点已实现；OCR 区域 overlay、原页对照与位置恢复未做 | 用户能核对复杂内容，往返阅读不丢位置 |

W1、W2 直接解决当前“新增资料看不了”的问题。W3、W4 与主计划中的资料范围和文档族完善相配合；W5 跟随各格式内容恢复逐步完成。W2 的正文阅读优先使用发布快照；快照缺失时按需解析并明确标注，生产发布应把 `parsed/`、`records/`、`media/` 与 `media-manifest.json` 一起冻结，并在运行配置中设置 `snapshot_dir`。

完成后，用户从目录选一份新增资料，可以打开正文、定位命中内容、在该资料范围内提问，再回到原文核对。仅增加格式图标或文档数量，不算完成这项工作。

## 7. 本轮实施记录

| 能力 | 接口/位置 | 说明 |
| --- | --- | --- |
| 原件下载 | `GET /v1/rag/documents/{id}` | 显式 MIME；Office 使用 attachment 与 RFC 5987 文件名；PDF/Markdown 仍 inline |
| 正文阅读 | `GET /v1/rag/documents/{id}/content` | 优先读 `snapshot_dir/parsed/<id>.json`；缺失时按需解析并返回 `snapshot_missing`；支持 `offset`、`limit`、`block_id` 与 `next_offset` |
| 文档元数据 | `GET /v1/rag/documents/{id}/metadata` | 返回目录行、格式、`reader_kind`、`snapshot_available`；不返回服务器路径 |
| 阅读页 | `/documents/{id}/view` | Office 返回 `office-document.html`；未知格式仍 501 |
| 锚点 | citation 的 `anchor_block_id` / `source_block_ids` / `position_locator` / `document_ordinal` | 表格块以表体为主锚点；阅读器按 `block_id` 聚焦并高亮整块 |
| 目录状态 | `/v1/rag/documents` | `reader_available`、`reader_kind`、`download_url`、`usage_statuses`、`document_kinds` |
| 范围入口 | 前端 scope chip | 单份资料发送 `mode=version` + `revision_ids`；待核实资料保留状态 |
| 精确行查询 | `GET /v1/rag/structured/lookup` | 只读诊断入口；问答侧已接入 `structured-exact` 通道 |
| 图片媒体 | `GET /v1/rag/documents/{id}/media/{name}` | 只从发布快照 `media/<id>/` 读取；校验文件名，返回图片 MIME；快照缺失时阅读器不显示图片 |
| 图片/公式渲染 | Office 阅读页 | 图片按 `media_url` 显示并保留图注；常见 OMML 公式按 KaTeX 渲染，未转换公式显示原文与状态 |

验证：`tests/rag/test_reader.py` 覆盖 DOCX 正文、分页、锚点、MIME 与快照优先；`tests/rag/test_catalog*.py` 覆盖目录字段；`tests/rag/test_version_scope_api.py` 覆盖 scope 与 approval 过滤；前端通过 `node --check`。另用临时模拟服务与真实 V6 DOCX／DOC 原件做过一次浏览器冒烟：目录筛选、范围 chip、引用打开、快照分页、锚点高亮和 DOC 按需转换均通过；这不替代生产验收。

已知限制：

- 生产运行配置尚未提供 `snapshot_dir`；未配置时正文按原件即时解析，V6 这类大文档首次打开较慢。
- DOC 按需转换依赖 LibreOffice；当前沙箱转换失败返回 503，生产应使用构建期快照。
- XLSX 正文一次返回整张表，尚未做行窗口分页；命中行高亮未做。
- PPTX 缩略图、DOCX 预览 PDF、OCR 区域 overlay 未实现；公式只覆盖常见 OMML 结构，无法可靠转换的仍显示“未恢复”。
- 媒体只提供 PNG/JPEG/GIF/BMP/WebP；SVG 为安全原因不提供，EMF/WMF/TIFF 等浏览器不可渲染格式只保留原件下载。
- 构建已生成 `media-manifest.json`（逐文件字节数与 sha256），但发布包尚未配置 `snapshot_dir` 或把 `media/` 纳入冻结清单；因此图片可见性仍属于生产发布前置条件。
- 目录“最近新增”、别名搜索未实现；文档族已完成拆分，但前端版本折叠尚未启用，需生产重建后验证。
