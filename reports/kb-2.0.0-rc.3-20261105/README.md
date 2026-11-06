# kb-2.0.0-rc.3 本地实现记录：线缆表入库、召回修复、工作台重建与题集

日期：2026-11-05。状态：**已完成 GPU 构建、候选验证与 8003 切换（2026-11-06）**；`rc.2` 保留为唯一回滚。人工语义评分与 K7 观察期未完成。

## 1. 新增资料：SHINE 网络线缆表与交换机配置表

| 项目 | 结果 |
| --- | --- |
| 输入 | `SHINE线缆表.zip`，16 个文件（13 XLSX、2 XLS、1 份字节相同的副本） |
| 原件位置 | `data/l0_raw/incoming/2026-11-05-shine-cables/SHINE线缆表/`（不进 Git） |
| 登记 | `scripts/register_cable_tables.py` 幂等写入 `registry-v2.json`：15 条修订、15 个文档族、16 条处置；“FEL1 - 副本”按 sha256 判重为 `excluded` |
| 治理字段 | `structured_index`、`usage_status=reference`、`approval_status=unknown`；“已核对/已发”只记为标签；2023 版总表与后续分段表的替代关系未确认，不登记 |
| 本地构建 | `cables-local-20261105`：15/15 解析成功，1,074 父块，6,115 行记录 |
| 行→父块映射 | 6,115 条记录 0 条行号越界、0 条行文本不在所指父块中 |

### 1.1 表格解析改进（`corpus/structured_parser.py`，profile 仍为 `openpyxl-cells-v1`）

- **标题、双行表头**：合并标题行进入 caption；“终端设备位置 / 设备用途”这类第二表头行与第一行合并为一行列名，`header_range` 保留物理范围。
- **分组行**：只有一个单元格的“FEL2-CN01柜（DEVSW001）”类行成为分组，切成独立表格块；分组名写入 caption、块元数据和每条行记录（`_group` 列）。
- **重复表头**：交换机配置表中多次出现的“设备 | 端口 | 系统 | 网络分配”开启新块。
- **纵向合并单元格**：数据区按左上角值向下填充，元数据记录填充数 `merged_cells_filled`；表头区双向填充。
- **尾部空列**：`.xls` 转换后报告的 255 列裁掉空列。单元格内换行改为空格，避免拆断管道表格行。
- **XLS**：新增 `SourceFormat.XLS`，构建期经 LibreOffice 转 XLSX 后解析，`source_format` 保持 `xls`；阅读器只在缺快照时按需转换。构建机必须安装 LibreOffice **Calc** 组件；GPU 主机原先只有 Writer/Impress，2026-11-05 补装 `libreoffice-calc` 后转换通过。
- 切块标签改用表格自身的物理行号（`chunking_v2._physical_label`），非连续分段也能得到正确的 `Sheet!A2:N2;A6:N36`。普通单表头工作表的块与标签不变。

### 1.2 精确行查询（`corpus/table_records.py`）

- 行记录按父块标签中的数据行范围指向真正包含该行的父块（修复审阅 4.1：rc.2 生产 898 条中 851 条指错）。
- 键：整格值、按分隔符拆出的组件、去标点形式、去 `UN-`/`LA-` 区段前缀形式；仍是精确匹配，不做前缀或模糊匹配。
- 排序：按同时命中的条件数与选择性（IDF）加权；纯数字词不计（避免命中“序号”列）。
- 端口：识别“第20口 / 端口5 / 42号端口”，在“端口”列的区间（如 `17-24`）内判断，或对应电缆编号 `-E020`。
- 问题点名的标识符（如 `FEL3-CN01`）在表中不存在时，不向问答注入只满足其余条件的行。

## 2. 召回问题修复（对应 [11-03 审阅](../rag-method-review-20261103/README.md) 第一批）

| 审阅项 | 修复 | 回归测试 |
| --- | --- | --- |
| 4.1 行记录指错父块 | 见 1.2；检索器每个查询最多注入 10 个精确父块 | `test_table_records.py`、`test_structured_lookup.py` |
| 4.2 族别名在 Qdrant 与 Python 不一致 | Qdrant 族过滤增加 `series:` 标签分支；`approval_statuses`、`tags` 也进入服务端预过滤（文本匹配为超集，客户端再按 `RetrievalScope.allows` 精确复核） | `test_scope_filtering.py` 内存 Qdrant 计数对照 |
| 4.5 冲突在裁剪后消失 | 只保留冲突一侧时，相关需求不再标为完整支持，`missing` 写明冲突；trace 增加 `unresolved_conflicts` | `test_workflow.py`（原“冲突一侧算支持”的断言按新规则改写） |
| 4.6 OCR 限制按证据集合判断 | 改为按数值绑定：待复核 OCR/公式片段中的数值若无原生文本佐证，精确题降级；`review_status=reviewed/verified/confirmed` 的片段恢复正常使用 | `test_workflow.py` 两例 |
| 4.8 邻近块被截断、精确优先失效 | 召回统一重排前为邻近上下文预留最多 12 个位置；工作流跨轮合并和 token 裁剪均保持结构化精确命中在前 | `test_structured_lookup.py`、`test_workflow.py` |

未处理：4.3（数值单位/比较符的确定性核查）、4.4（跨文档定量组合规则）、4.7（图片内容召回）、4.9（版本适用性推理）属于研究或后续批次，本轮不宣称完成。

## 3. 工作台重建（`rag/web/`）

| 视图 | 能力 |
| --- | --- |
| 文档问答 | 多资料范围 chip（≤32 份，含状态提示）；答案下方“需求覆盖”列出完整/部分/缺依据及缺项；引用卡显示位置、版本、状态与摘录 |
| 表格查询 | 调用 `/v1/rag/structured/lookup`，按资料分组显示最佳/部分匹配行、命中条件、表头—值对；“定位原表”在右栏打开并高亮该物理行；“就此提问”带范围转入问答 |
| 资料库 | 按分类·主题分组；格式、状态、搜索筛选；勾选多份资料后一次设为提问范围；历史/待核实资料标注“需选定范围” |

公共能力：问答与表格查询历史保存在本机浏览器（读写有异常保护）；右栏阅读器在三个视图共用；浅色/深色主题；窄屏折叠导航并上下堆叠。Office 阅读页增加表头吸顶、大表筛选框、`row=` 行高亮。新样式文件 `workbench.css`；`style.css` 继续服务 Office 阅读页。

`/v1/rag/structured/lookup` 新增 `hits`（分数、命中条件、`fields` 表头—值、`location`、`view_url`）、`unmatched_identifiers`，可重复的 `document_id` 参数和 `limit`；原 `records` 字段保留。

验证：本地以真实 `cables-local-20261105` 目录/行记录/快照和桩回答启动预览，确认三视图、行定位高亮、多选范围提问、深色与窄屏布局，控制台无错误。桩回答不是模型输出。

## 4. 题集

| 题集 | 文件 | 状态 |
| --- | --- | --- |
| 线缆/端口 20 题 | `data/evaluation/cable-lookup-v1.json`（`scripts/build_cable_benchmark.py` 生成） | 开发集；金标准行由独立 openpyxl 读取原件并核对 `required_values` |
| 旧 50 题 | `data/evaluation/validity-pilot-v2.json`；题干修订版 `validity-pilot-v3.json` | 回归用；v3 按评分裁决补充 8 道题干，答案不变 |
| K5 60 题 | `data/evaluation/kb2-question-plan-v1.json` | 仍为 `draft`：13 题待原文核对、8 题来自二手分析，冻结需人工审核，本轮不冻结 |
| **100 题工程回归集** | `data/evaluation/kb2-benchmark-100-v1.json`（`scripts/build_benchmark_100.py` 生成） | 旧 50 + 线缆 20 + 已验证新题 30；用于 rc.3 与 rc.2 对照，核验见[报告](../benchmark-100-20261105/README.md) |

线缆题含端口区间、跨表联合（端口→VLAN＋电缆终端）、电缆编号、设备列表、`.xls`、改线标注（“改为CN06”）、不存在对象、现场状态与版本边界。运行器 `scripts/run_cable_benchmark.py` 自动检查查找命中、状态、必需值、禁止断言和引用是否覆盖金标准行；语义质量仍需人工评分。

**本地查找层结果**（真实行记录，无生成模型）：17 道有金标准行的题中，最佳匹配命中 17/17，全部金标准行同在最佳匹配 16/17（未全中的是颜色汇总题，属语义题）。这是同一作者编写的开发集，不能当作独立测试结果。问答层结果待线上运行。

## 5. 本地验证

```bash
PYTHONPATH=src ~/miniconda3/envs/accelerator-rag/bin/python -m pytest -q   # 587 passed, 1 skipped
~/miniconda3/envs/accelerator-rag/bin/ruff check src tests scripts          # 通过
node --check src/accelerator_rag/rag/web/{app,pdf-reader,office-document}.js
```

## 6. GPU 构建、验证与上线（2026-11-05 / 06，已完成）

1. **构建**：`kb2-prod-20261105-v3`，222/222 条公开修订解析成功（225 条注册 − 3 条 restricted），
   0 失败、0 待 OCR；10,793 父块、10,654 可索引父块；6,989 条行记录 0 错位；
   3,086 个媒体文件（631 MB）；102 个族。
   GPU 主机原先缺 LibreOffice Calc，`.xls` 转换失败；补装 `libreoffice-calc` 后通过。
2. **索引**：E5 13,766 points、Qwen3 10,654 points；两路父块/正文/证据哈希一致；
   Qwen3 首轮 batch 8 在显存不足时 OOM，改 batch 2 续建完成。
3. **候选与上线**：候选容器（8013）健康，`release_id=kb-2.0.0-rc.3`、222 文档、10,654 段；
   线缆查找 17/17、线缆问答 16/19 状态正确；100 题对照见
   [100 题报告](../benchmark-100-20261105/README.md)。
4. **切换**：2026-11-06 00:04 将 8003 切到 rc.3；随后执行 rc.2 回滚演练（健康、207 文档/8,661 段），
   再切回 rc.3。`kb-2.0.0-rc.2` 保留为唯一回滚版本；rc.1、md-20261030 与旧容器已清理。
5. **发布清单**：[release-manifest.json](release-manifest.json)（status=live，rollback_verified=true）。

未完成：人工语义评分、K7 观察期；并发 3 时 rc.3 尾部延迟高于 rc.2，需观察。
