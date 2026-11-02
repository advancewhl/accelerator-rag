# K1/K4 资料治理候选：逐文件处置、版本族与冲突

编制日期：2026-11-02
批次：`2026-11-02-shine-control`
状态：候选草案，未提交、未批准
依据计划：`docs/roadmap/knowledge-base-v2-plan.md`（`2026-11-02-r1`）

> **重要声明：本报告和三个 JSON 是候选治理数据，不是已批准的现行版本，也不是生产入库决定。**
> 所有版本关系、冲突结论、业务类型和处置理由，都需要资料责任人、领域审核人和开发负责人确认。
> 本批未读全文、未 OCR、未做 Office 转换、未联网、未修改 `src/` 或 `tests/`。

## 1. 范围与方法

### 1.1 输入

- `docs/roadmap/knowledge-base-v2-plan.md`：重点 §3（资料类型与纳入策略）、§5（文档身份）、§6（重复/版本族/冲突）、§10.2（新旧语料迁移）、§11.1（验证集）、§15（交付与维护）。
- `reports/incoming-2026-11-02/ANALYSIS.md`：批次内容画像、重复关系、版本冲突和 OCR/转换限制。
- `reports/incoming-2026-11-02/document-decisions.csv`：218 行逐文件初始处置（`handling`、`priority`、`note`）。
- `reports/incoming-2026-11-02/inventory.clean.json`：218 个文件的扩展名、字符数、页数、无文本页数、封面/首段文字（`head`）。
- `data/documents/registry.json`（旧 13 份 PDF）与 `data/documents/registry-md.json`（旧 4 份 Markdown）：确认原有 17 份资料；总体设计族引用其中 2017 初步设计的 `doc_id`，脚本实际读取 `registry.json` 做成员校验。

### 1.2 生成方式

生成脚本：`scripts/build_v2_governance.py`。

- 只使用 Python 标准库，不 import `accelerator_rag`，不联网。
- 所有枚举、格式映射、业务类型规则、27 个排除文件的重分流、版本族和冲突候选都写在脚本常量里。
- 脚本读取 CSV、ANALYSIS、计划、inventory 和 `registry.json`；`--check-only` 只校验不写文件；`--root` 可在 repo 之外运行。
- 输出三个 UTF-8 JSON，使用 `ensure_ascii=False`，字段顺序固定。

### 1.3 处置规则

1. CSV `handling=ingest|convert|ocr` → `disposition=text_index`；`planned_action` 分别为 `ingest|convert|ocr`。
2. `xlsx/csv/ods` 中的端子表/清单 → `structured_index`；但 IP 表按“配置快照”规则处理。
3. 签字图片 JPG → `attachment_only`。
4. `zip/rar` → `catalog_only`。
5. Office 临时锁文件 → `excluded`。
6. 代码、日志、IP 表 → `catalog_only` 或 `deferred`，逐项写明用途和理由。
7. 图纸类 PDF → `attachment_only`。
8. 每条记录必须有非空 `reason`；`notes` 记录来源、未知项和后续确认点。

`document_kind` 只依据文件名、目录名、CSV note 和 inventory 首段判断；没有全文语义分类。无法判断的（嵌套包、王睿归档报告、控制需求工作联系单、归档封面、临时文件）写 `unknown`，并在 `notes` 说明。

### 1.4 校验

脚本内置以下断言：

- CSV 恰好 218 行，路径唯一。
- `dispositions` 恰好 218 条，`source_path` 唯一，且等于批次前缀 + `batch_relative_path`。
- 所有枚举值在允许集合内；每条 `reason` 非空。
- 版本族的 `batch_path` 必须存在于 CSV，`legacy_doc_id` 必须存在于 `registry.json`。
- 同一 `batch_path` 不得出现在多个族中。
- 冲突记录的 `owner` 为“待指派”，未解决时 `resolution` 为空。

## 2. 产出文件

| 文件 | 内容 |
| --- | --- |
| `data/documents/v2/dispositions.draft.json` | 218 条逐文件候选处置 |
| `data/documents/v2/family-candidates.draft.json` | 21 个版本族候选 |
| `data/documents/v2/conflict-candidates.draft.json` | 6 条冲突候选 |
| `scripts/build_v2_governance.py` | 可重复运行的生成脚本 |
| `reports/knowledge-base-v2/K1-governance-candidates.md` | 本报告 |

## 3. 处置计数

### 3.1 按 disposition

| disposition | 数量 | 说明 |
| --- | ---: | --- |
| `text_index` | 191 | 进入文本索引：19 ingest + 155 convert + 17 ocr |
| `structured_index` | 2 | 端子表、补充材料清单 |
| `attachment_only` | 4 | 3 张签字 JPG + 1 份图纸 PDF |
| `catalog_only` | 16 | 2 个压缩包 + 14 份 IP 表/配置脚本/说明 |
| `deferred` | 3 | 3 份 caput 运行日志 |
| `excluded` | 2 | 2 个 Office 临时锁文件 |
| **合计** | **218** | |

### 3.2 按 planned_action

| planned_action | 数量 |
| --- | ---: |
| `ingest` | 19 |
| `convert` | 155 |
| `ocr` | 17 |
| `structured` | 2 |
| `attachment` | 4 |
| `catalog` | 16 |
| `defer` | 3 |
| `exclude` | 2 |
| **合计** | **218** |

### 3.3 按 source_format

| source_format | 数量 |
| --- | ---: |
| `pdf` | 37 |
| `docx` | 122 |
| `doc` | 16 |
| `pptx` | 19 |
| `xlsx` | 2 |
| `csv` | 3 |
| `ods` | 1 |
| `txt` | 1 |
| `image` | 3 |
| `archive` | 2 |
| `code` | 6（3 个 `.py`、1 个 `.sh`、1 个 `.acf`、1 个 `.log`） |
| `other` | 6（无扩展名文件：S99logServer、caputLog-202004141600、caputlog-offset、temIPList、tmpIPAlive、tmpIPList） |
| **合计** | **218** |

### 3.4 按 priority

| priority | 数量 | 说明 |
| --- | ---: | --- |
| `P0` | 19 | 与计划 §2.2 的初始 P0 一致 |
| `P1` | 86 | 与计划一致 |
| `P2` | 86 | 与计划一致 |
| `P3` | 20 | 代码/IP 表/图纸/端子表等初步不进入文本索引 |
| `exclude` | 7 | 压缩包、签字 JPG、Office 临时文件 |
| **合计** | **218** | |

### 3.5 disposition × source_format

| disposition | archive | code | csv | doc | docx | image | ods | other | pdf | pptx | txt | xlsx | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `text_index` | 0 | 0 | 0 | 15 | 121 | 0 | 0 | 0 | 36 | 19 | 0 | 0 | 191 |
| `structured_index` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 |
| `attachment_only` | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 1 | 0 | 0 | 0 | 4 |
| `catalog_only` | 2 | 5 | 3 | 0 | 0 | 0 | 1 | 4 | 0 | 0 | 1 | 0 | 16 |
| `deferred` | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 3 |
| `excluded` | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| **合计** | **2** | **6** | **3** | **16** | **122** | **3** | **1** | **6** | **37** | **19** | **1** | **2** | **218** |

### 3.6 按 document_kind（候选）

| document_kind | 数量 |
| --- | ---: |
| `overall_design` | 2 |
| `subsystem_design` | 53 |
| `standard_specification` | 15 |
| `interface_specification` | 2 |
| `operation_manual` | 32 |
| `installation_maintenance` | 8 |
| `test_plan` | 5 |
| `test_report` | 13 |
| `acceptance_report` | 10 |
| `development_summary` | 7 |
| `review_opinion` | 29 |
| `meeting_record` | 3 |
| `configuration_snapshot` | 19 |
| `structured_list` | 11 |
| `drawing` | 1 |
| `unknown` | 8 |
| **合计** | **218** |

`unknown` 的 8 份是：2 个嵌套压缩包、2 份王睿归档报告、1 份控制需求工作联系单、2 个 Office 临时文件、1 份硬线归档报告封面。它们不表示资料无价值，只表示当前证据不足以判定业务类型。

`operation_manual` 共 32 份；其中 31 份归入 `shine-control-operation-manual-series`，另 1 份是 `3 样机验收/米清茹补充材料/Git及GitLab的使用说明.docx`，归入 `shine-ioc-management`。

## 4. 27 个初步排除文件的重分流

CSV 有 27 行 `handling=exclude`（7 行 `priority=exclude`，20 行 `priority=P3`）。按计划 §3.2 和 §6.1，逐项重分流如下。

| 数据行 | 文件 | priority | 新 disposition | planned_action | 理由摘要 |
| ---: | --- | --- | --- | --- | --- |
| 1 | `3 样机验收/陈广花补充材料/一号测试厅归档文档.rar` | exclude | `catalog_only` | `catalog` | 嵌套 RAR；仅登记容器与内部路径，未解压评估 |
| 2 | `归档文档（202310）/2023控制系统硬线项目归档文件(1).zip` | exclude | `catalog_only` | `catalog` | 嵌套 ZIP；与已解压目录对应，避免重复索引 |
| 81 | `归档文档（20221117）/归档清单（20221117签字版）.jpg` | exclude | `attachment_only` | `attachment` | 扫描签字页，无正文 |
| 82 | `归档文档（202410）/硬线项目归档文件移交清单（签字版）.jpg` | exclude | `attachment_only` | `attachment` | 扫描签字页，无正文 |
| 83 | `归档文档（20251119）/2025硬线归档/移交清单-签字版.jpg` | exclude | `attachment_only` | `attachment` | 扫描签字页，无正文 |
| 84 | `3 样机验收/~$率图像采集样机研制总结报告.docx` | exclude | `excluded` | `exclude` | Office 临时锁文件，162 bytes，无正文 |
| 85 | `操作手册/~$INE激光界面操作手册.doc` | exclude | `excluded` | `exclude` | Office 临时锁文件，162 bytes，无正文 |
| 199 | `3 样机验收/米清茹补充材料/代码/README.txt` | P3 | `catalog_only` | `catalog` | 代码目录说明，目录登记 |
| 200 | `3 样机验收/米清茹补充材料/代码/S99logServer` | P3 | `catalog_only` | `catalog` | 启动脚本，配置快照，未执行 |
| 201 | `3 样机验收/米清茹补充材料/代码/acsTest.acf` | P3 | `catalog_only` | `catalog` | EPICS 访问安全配置，未执行 |
| 202 | `3 样机验收/米清茹补充材料/代码/caput.log` | P3 | `deferred` | `defer` | 运行日志；采集时间、完整性、用途未确认 |
| 203 | `3 样机验收/米清茹补充材料/代码/caputLog-202004141600` | P3 | `deferred` | `defer` | 历史运行日志；完整性未确认 |
| 204 | `3 样机验收/米清茹补充材料/代码/caputlog-offset` | P3 | `deferred` | `defer` | 运行日志偏移文件；用途未确认 |
| 205 | `3 样机验收/米清茹补充材料/代码/genIPList.py` | P3 | `catalog_only` | `catalog` | IP 表生成脚本，配置快照 |
| 206 | `3 样机验收/米清茹补充材料/代码/hla-ip.csv` | P3 | `catalog_only` | `catalog` | IP 表，目录登记，访问范围待确认 |
| 207 | `3 样机验收/米清茹补充材料/代码/hla-ip.ods` | P3 | `catalog_only` | `catalog` | IP 表，目录登记，访问范围待确认 |
| 208 | `3 样机验收/米清茹补充材料/代码/importIPFile.py` | P3 | `catalog_only` | `catalog` | IP 导入脚本，配置快照 |
| 209 | `3 样机验收/米清茹补充材料/代码/ps-ip.csv` | P3 | `catalog_only` | `catalog` | IP 表，目录登记，访问范围待确认 |
| 210 | `3 样机验收/米清茹补充材料/代码/shine-proto-ip.csv` | P3 | `catalog_only` | `catalog` | IP 表，目录登记，访问范围待确认 |
| 211 | `3 样机验收/米清茹补充材料/代码/temIPList` | P3 | `catalog_only` | `catalog` | IP 表；与 tmpIPList 完全重复 |
| 212 | `3 样机验收/米清茹补充材料/代码/tmpIPAlive` | P3 | `catalog_only` | `catalog` | IP 存活列表，配置快照 |
| 213 | `3 样机验收/米清茹补充材料/代码/tmpIPList` | P3 | `catalog_only` | `catalog` | IP 表；与 temIPList 完全重复 |
| 214 | `3 样机验收/米清茹补充材料/代码/updateCaputlogDb.py` | P3 | `catalog_only` | `catalog` | caput 日志库维护脚本，配置快照 |
| 215 | `3 样机验收/米清茹补充材料/代码/updateCaputlogDb.sh` | P3 | `catalog_only` | `catalog` | caput 日志库维护脚本，配置快照 |
| 216 | `3 样机验收/陈广花补充材料/水平测试平台2控制柜电路图V2.pdf` | P3 | `attachment_only` | `attachment` | 94 页图纸，正文主要是图框文字 |
| 217 | `3 样机验收/陈广花补充材料/端子对应表最终版3.8现场改造.xlsx` | P3 | `structured_index` | `structured` | 端子表，按 §7.4 结构化试点 |
| 218 | `3 样机验收/陈广花补充材料/补充材料清单.xlsx` | P3 | `structured_index` | `structured` | 补充材料清单；计划 §2.2 提目录管理，当前按结构化候选 |

数据行按 CSV 数据顺序编号（不含表头），与 `dispositions.draft.json` 数组顺序一致（从 1 开始）。

重分流合计：`catalog_only` 16、`attachment_only` 4、`deferred` 3、`excluded` 2、`structured_index` 2，共 27。

需要注意：

- 2 个压缩包只登记容器，不把压缩包本身当正文；是否展开子文件、是否与已解压目录共享资产，待确认。
- IP 表和配置脚本可能涉及内部地址/访问范围。首版默认只做目录登记，不进入公共搜索片段、下载接口或回答日志；是否作为版本化附件保留，由资料责任人确认。
- `temIPList` 与 `tmpIPList` 在 ANALYSIS §4.2 中列为完全重复（SHA-256 相同）；两者都登记，但最终只保留一个资产。
- 签字 JPG 只作为附件，不进入文本索引；签字 PDF（评审意见、2023 移交清单）按 CSV `handling=ocr` 保留为 `text_index`，OCR 后作为证据，签字页另作附件核对。

## 5. 版本族候选

共建立 21 个族，157 条成员记录（156 个批次路径 + 1 个旧 `doc_id`）。156 条处置记录写入了 `target_family_id`，其余 62 条暂未归族（多为单份文档、结构化清单、配置快照或业务类型未知项）。

| family_id | 标题 | 成员 | relation | confidence | 需确认 |
| --- | --- | ---: | --- | --- | --- |
| `accelerator-overall-design` | 加速器总体设计（2017 初步设计 / 2024 优化设计 V6 / 控制章节） | 3 | `version_and_scope_candidate` | medium | 是 |
| `shine-total-control-integration-design` | 总控集成系统设计（2022 技术设计 / 评审申请书 / 2024-10 设计报告） | 3 | `related_design_series` | medium | 是 |
| `shine-equipment-control-design` | 设备控制系统设计（2018 初步 / 2022 技术 / 2024 数据交互） | 4 | `version_family` | medium | 是 |
| `shine-upper-software-design` | 上层应用软件设计（2018 初步 / 2022 技术） | 3 | `version_family` | medium | 是 |
| `shine-interlock-system-design` | 联锁系统设计（2019 初步 / 2022 技术 / 运行模式 / 2024 专题） | 6 | `version_family` | high | 是 |
| `shine-timing-system-design` | 定时系统设计（2018 初步/样机 / 2023 监控 / 2024–2025 归档） | 13 | `version_and_evidence_chain` | medium | 是 |
| `shine-control-network-design` | 控制网络设计（2018 初步 / 2023 配置 / 2024 装置网络） | 3 | `version_family` | medium | 是 |
| `shine-data-storage-and-archive` | 数据存储与存档（2018 初步 / 2023 设计 / 2024 Archiver / 2025 安全管理） | 7 | `version_family` | medium | 是 |
| `shine-ioc-management` | IOC 管理与安装维护（设计规范 / 管理规范 / 2024–2025 模板、开发、安装） | 7 | `series` | medium | 是 |
| `shine-power-supply-control-design` | 电源与功率源控制（2018 初步 / 2024 PDU / 2025 热备电源） | 7 | `version_family` | medium | 是 |
| `shine-vacuum-control-design` | 真空控制设计（2018 初步 / 2018 样机评审 / 2024 注入段总结） | 3 | `version_family` | medium | 是 |
| `shine-motion-control-design` | 运动控制设计（2018 初步 / 2022 四自由度平台） | 3 | `version_family` | medium | 是 |
| `shine-alarm-system-design` | 报警系统设计（2018 初步 / 2022 安装配置） | 2 | `version_family` | medium | 是 |
| `shine-control-standards-2024` | 总控相关标准和规范（2024 合并版 / 5 份单项 / 扫描副本） | 8 | `contains_and_equivalent` | high | 是 |
| `shine-device-naming-rules` | 设备与控制信号命名规则（编号表 / 信号 / 机柜 / 命名 / 技术代号） | 6 | `related_normative_cluster` | medium | 是 |
| `shine-control-operation-manual-series` | 控制系统界面操作手册（第一/二/三版 + 归档副本） | 31 | `series` | medium | 是 |
| `shine-prototype-fast-interlock-acceptance` | 快联锁样机测试与验收证据链 | 11 | `evidence_chain` | high | 否 |
| `shine-prototype-constant-temperature-cabinet-acceptance` | 恒温机柜控制样机测试与验收证据链 | 8 | `evidence_chain` | high | 否 |
| `shine-prototype-control-system-development-environment-acceptance` | 控制系统开发环境样机测试与验收证据链 | 10 | `evidence_chain` | high | 否 |
| `shine-prototype-vacuum-control-acceptance` | 真空设备控制样机测试与验收证据链 | 8 | `evidence_chain` | high | 否 |
| `shine-prototype-high-frame-rate-image-acquisition-acceptance` | 高帧率图像采集样机测试与验收证据链 | 11 | `evidence_chain` | high | 否 |

### 5.1 加速器总体设计

族 `accelerator-overall-design` 包含：

- 旧 `doc_id` `shine-accelerator-preliminary-design-report-2017`（2017-12-26）。
- 批次文件 `1、硬X射线自由电子激光装置优化设计报告-加速器分册V6（返回通读版本）.docx`。
- 批次文件 `六、加速器控制20240422.docx`（2024 工程设计报告·加速器控制章）。

证据：ANALYSIS §4.3 对比 2018 初步设计 8 GeV 与 V6 7.2 GeV；计划 §6.2 要求梳理“既有初步设计、优化设计 V6、控制章节之间的范围关系”。V6 文件名含“返回通读版本”，批准状态、生效时间和替代范围均 unknown，不能自动当作现行版。

### 5.2 操作手册

族 `shine-control-operation-manual-series` 包含 31 份：

- 第一版：`操作手册/` 根目录的 12 份（准直器、功率源、四自由度平台、定时、恒温机柜、Archiver Desktop、Web 查询、温湿度、激光、PDU、电源、联锁）。
- 第二版：`操作手册/第二版/` 的 4 份（2023-12）。
- 第三版：`操作手册/第三版（202411）/` 的 6 份（2024-11）。
- 2023 归档副本：6 份（功率源、温湿度、电源、定时、恒温机柜、联锁）。
- 2024 归档副本：3 份（存档查询、注入器联锁、注入段真空）。

证据：ANALYSIS §2 列出操作手册 23 份；§4.2 指出 3 组操作手册与 2023 归档完全重复（功率源、温湿度、电源）；目录名含第一版/第二版（20231206）/第三版（202411）。

注意：这是一个“手册合集”级候选族，不等于每个功能都已经建立独立的版本链。例如准直器第一版与第三版的按钮集合已有可见差异（见冲突 6），但第三版是否替代第一版、适用哪台设备/哪个软件版本，尚未确认。最终应按功能拆成若干子族，或在 `revision_label` 和 `scope` 中写清适用范围。

### 5.3 分系统设计

已建立的分系统设计族：

- `shine-interlock-system-design`：2019 初步、2022 技术、2022 运行模式、2022 评审申请、2024 快联锁远程下装、2024 磁铁电源温度联锁。技术设计是否整篇替代初步设计、快联锁样机是否属于同一族，待确认。
- `shine-timing-system-design`：2018 主定时初步、2018 定时样机设计/评审、2023 Nagios/SNMP 监控、2024 devSnmp/安装测试、2025 L1 研制总结/诊断平台/EPICS-SNMP。
- `shine-control-network-design`：2018 控制网络初步、2023 OPI/IOC 网络配置、2024 装置控制网络设计。
- `shine-data-storage-and-archive`：2018 数据存储/通道存档初步、2023 数据存储/存档查询设计、2024 Django Archiver、2025 运行数据安全管理。
- `shine-ioc-management`：IOC 设计规范 v1.2、IOC 管理规范（2023-09-08）、Git/GitLab、2025 IOC 模板/开发/安装维护、2024 EPICS 模块安装。
- `shine-power-supply-control-design`、`shine-vacuum-control-design`、`shine-motion-control-design`、`shine-alarm-system-design`、`shine-equipment-control-design`、`shine-upper-software-design`、`shine-total-control-integration-design`：按同名子系统跨代次文件建立，均为 medium confidence。

“技术设计晚于初步设计”只生成待核实的替代候选；没有确认“整篇替代”“指定章节替代”还是“仅替代某个指标”。计划 §6.2 要求的关系已在族中表达，但没有下沉到章节或指标级依赖。

### 5.4 标准规范

族 `shine-control-standards-2024` 包含 8 份：

- `SHINE-OP-TL-002 2024 总控相关标准和规范.pdf`（2024 合并版，20 页）。
- `总控相关标准和规范/` 下 5 份单项规范（EPICS 软件版本、PyDM 界面、数据格式与存储、联锁硬件信号接口、设备控制及通讯接口）。
- `1 硬线工程/25. 联锁系统硬件信号接口规格.pdf`（3 页扫描副本）。
- `1 硬线工程/26. 设备控制及通讯接口标准.pdf`（2 页扫描副本）。

ANALYSIS §4.2 已确认合并版完整包含 5 份单项规范的正文，建议保留合并版作为检索主来源，单项版用于章节定位。两份扫描副本与单项文本版的等价关系尚未逐字核对；当前按 CSV `handling=ocr` 保留为 `text_index`，确认等价后可降为 `attachment_only`。

### 5.5 测试与验收证据链

已建立 5 个样机证据链族：

| 样机 | 成员数 | 覆盖环节 |
| --- | ---: | --- |
| 快联锁 | 11 | 样机设计、设计评审、工艺评审、测试大纲、自测、测试报告、研制总结、验收申请、验收书、验收评审（PDF/PPTX） |
| 恒温机柜 | 8 | 设计、测试大纲、自测、测试报告、研制总结、验收申请、验收书、验收评审 |
| 控制系统开发环境 | 10 | 设计、评审、测试大纲、自测、测试报告、研制总结、验收申请、验收书、验收评审（PDF/PPTX） |
| 真空设备控制 | 8 | 设计评审、测试大纲、自测、测试报告、研制总结、验收申请、验收书、验收评审 |
| 高帧率图像采集 | 11 | 设计、评审、工艺评审、测试大纲、自测、测试报告、研制总结、验收申请、验收书、验收评审（PDF/PPTX） |

这些族的成员关系由文件名和目录直接支持，confidence 为 high；但各文件的批准状态、签署日期、测试条件、测量范围仍 unknown。它们回答的是“证据链有哪些环节”，不是“验收已经通过”或“指标已经达到”。

### 5.6 命名规则

族 `shine-device-naming-rules` 是相关规范簇，不是版本族：SHINE-AC 编号、控制信号命名规则（签发版）、机柜命名规则、2023-06-13 专题会纪要、SHINE-OP-TL-018 设备命名规则（R0-2019-09-03）、SHINE-OP-TL-004 技术代号规则（2022-09-26）。它们之间可能有引用/补充关系，但当前没有证据表明是同一文档的多个修订。

## 6. 冲突候选

共 6 条。所有 `owner` 均为“待指派”，未解决项的 `resolution` 为空。

| # | 主题 | revision_a | revision_b | 类型 | 状态 |
| ---: | --- | --- | --- | --- | --- |
| 1 | 设计能量口径：8 GeV 与 7.2 GeV | `1 硬线工程/20. 常规功率源控制初步设计报告.docx` | `1、硬X射线自由电子激光装置优化设计报告-加速器分册V6（返回通读版本）.docx` | `design_parameter` | `open` |
| 2 | 网络安全设计报告封面日期晚于批次日期且审核栏未填写 | `硬X射线自由电子激光装置网络安全设计报告.docx` | `docs/roadmap/knowledge-base-v2-plan.md` | `document_metadata` | `needs_source_check` |
| 3 | V6“返回通读版本”的批准状态与替代范围 | V6 `.docx` | `data/documents/registry.json#shine-accelerator-preliminary-design-report-2017` | `approval_status` | `needs_source_check` |
| 4 | 白兔定时设计指标与原型实测口径 | `2 重大专项/11. 定时样机设计报告.pdf` | `归档文档（20251119）/2025硬线归档/硬X射线自由电子激光装置项目L1段定时系统研制总结.docx` | `design_vs_measured` | `needs_source_check` |
| 5 | 快联锁响应时间的测量范围（站内/站间、FPGA/PLC） | `2 重大专项/8. 快联锁样机设计报告.docx` | `3 样机验收/快联锁样机自测报告.docx` | `measurement_scope` | `needs_source_check` |
| 6 | 准直器操作手册第一版与第三版操作步骤差异 | `操作手册/SHINE准直器界面操作手册.docx` | `操作手册/第三版（202411）/SHINE注入器段准直器控制界面操作手册.docx` | `operation_step` | `open` |

上表为便于阅读使用批次相对路径；`conflict-candidates.draft.json` 中的 `revision_a`/`revision_b` 使用完整 `source_path`（批次文件加 `data/l0_raw/incoming/2026-11-02-shine-control/资料/` 前缀），避免脱离批次上下文后无法定位。

### 6.1 8 GeV 与 7.2 GeV

ANALYSIS §4.3 和 inventory 首段都显示：2018 年《常规功率源控制初步设计报告》称“能量为 8GeV 的超导直线加速器”；《束流分配及功率源控制初步设计报告》（2018-10）称“已加速至 8GeV”；V6“一、概述”称“能量 7.2 GeV”。这是文本层面的真实差异，不是脚本推断。

需要确认：两代设计是否同一基线；V6 是否整篇替代旧设计；8 GeV 是否旧方案/预留升级/不同运行模式；回答“设计能量是多少”时如何按代次和适用范围分别表述。`status=open`，不能用一个数字覆盖另一个。

### 6.2 网络安全报告的日期与审核状态

计划 §2.3 记录：网络安全设计报告封面写明 2026 年 11 月 5 日，晚于计划编制日期 2026-11-02；审核栏未填写。inventory 首段进一步显示：编制史武军、吕慧慧、唐小丰；审核、审定、会签栏空白；日期“2026年11月5日”。

不能据此断言报告无效，也不能把它当作已批准现行依据。需要确认签发流程、生效日期、是否已在现场部署，以及封面日期是否为计划发布日期而非实际编制日期。`status=needs_source_check`。

### 6.3 V6 的批准状态与替代范围

V6 文件名含“返回通读版本”。计划 §2.3 明确要求“保留原版本标签；向资料责任人确认批准状态、范围和生效时间”。`registry.json` 中 2017 初步设计报告 `version=初步设计报告 (2017-12-26)`、`status=reference`，只是登记参考，不能证明其现行性。

需要确认：V6 是否正式批准；替代整篇还是部分章节；是否仅替代指标；生效时间；与 2017/2018 版的关系。`status=needs_source_check`。

### 6.4 白兔定时设计指标与原型实测口径

ANALYSIS §4.1 称《定时样机设计报告》给出“时钟精度 1 ns、抖动 <30 ps”，并明确“属设计指标，不是原型 II 实测口径”。inventory 首段显示《定时样机评审报告》也列“精度达到 1ns，抖动小于 30ps”；《L1 段定时系统研制总结》（2025-11）的“技术指标”只写“抖动小于 30ps”。

就目前可见的摘录/首段而言，三处都没有给出原型 II 的实测值、测量设备、积分带宽和时间窗口；需读全文确认。回答“实测抖动是多少”时不能把设计指标当实测结果。`status=needs_source_check`。

### 6.5 快联锁响应时间的测量范围

ANALYSIS §4.1 称《快联锁样机设计报告》给出“单节点信号响应 <10 µs、整系统故障响应 <100 µs；FPGA 快保护约 11.8 µs，PLC 约 33 ms”。inventory 首段显示《快联锁样机自测报告》称“站点内响应时间小于 10 μs、站点间响应时间小于 100 μs”；测试报告 PDF 为 17 页扫描件，未 OCR。

需要确认：测量的是站点内还是站点间；FPGA 还是 PLC；设计指标还是实测值；测试报告的测量通道、触发条件和统计口径。`status=needs_source_check`。

### 6.6 准直器操作手册第一版与第三版

inventory 首段显示：第一版列 `VER_ORIGIN_VEL`/`HOR_ORIGIN_VEL`、`VER_AUTO_DIST`/`HOR_AUTO_DIST`、`VER_ENABLE`/`HOR_ENABLE`、`VER_ORIGIN`/`HOR_ORIGIN`、`VER_AUTO_MV`/`HOR_AUTO_MV`；第三版新增 `ALARM_CLEAR`、`ONEKEY_LOC`、`VER_LOC`/`HOR_LOC`、`VER/HOR HOLE/GAP` 等按钮。

这是文本层面的步骤差异，但第三版是否替代第一版、适用哪台设备/哪个软件版本，尚未确认。`status=open`，不能把两版步骤混在同一答案中。

## 7. 未核实事项与使用限制

### 7.1 全文与解析

- 未读全文。除 inventory 的 `head`（首段/封面文字）和 ANALYSIS 的抽查摘录外，没有逐份阅读正文。
- 未 OCR。17 份 OCR 候选共 169 页，17 份均为整本无文本层。其中 `1 硬线工程/25`（3 页）、`26`（2 页）已有文本版。计划 §2.2 估计确认等价后约 15 份、166 页；按 CSV 页数直接相减为 164 页，差异原因未核实，需以原件页数和等价判断为准。所有扫描件的可读性只按页数判断，未逐页确认。
- 未做 docx/pptx/doc→PDF 转换，未检查中文排版、表格、插图、备注和公式保真。
- 未逐份核对 `document_kind`。业务类型主要来自文件名、目录名、CSV note 和 inventory 首段；`1 硬线工程/24. 控制需求工作联系单.pdf`、王睿归档报告、硬线归档报告封面等写为 `unknown`。
- 未对 V6 做单独试运行。V6 约 899,640 字符、310.8 MB，解析/转换的内存、时长和章节输出未测量。

### 7.2 版本与状态

- 未确认任何文档的批准状态。`approved`/`draft`/`withdrawn` 均未核实；当前只用 `unknown` 或文字说明。
- 未确认生效日期、失效日期、替代范围和适用设备/软件版本。日期只来自封面文字或文件名；没有用文件修改时间填充生效日期。
- 未确认版本号/修订号。除文件名和封面可见的 `V6`、`R0`、`2024`、`2023-12`、`2024-11` 等标签外，不编造修订号。
- 版本族关系是候选。`version_family`、`version_and_scope_candidate`、`series`、`related_design_series`、`related_normative_cluster` 都表示“待确认的关系类型”，不是已批准的替代关系。
- “技术设计晚于初步设计”只作为替代候选；没有确认替代整篇、指定章节还是仅替代某个指标。

### 7.3 重复与指纹

- ANALYSIS §4.2 的“完全重复”只对已核对的 5 组负责；本报告没有对全库做全文向量相似度比对。
- inventory 的 `sha256_64m` 只读取前 64 MiB，不能单独证明大文件完全相同。超过 64 MiB 的文件如需认定完全重复，应另做完整内容确认。
- 操作手册与 2023 归档的 3 组完全重复（功率源、温湿度、电源）已在 notes 标注；`temIPList`/`tmpIPList` 也标注为完全重复。最终应共享原始资产，避免重复索引。

### 7.4 访问范围与安全

- 网络安全设计报告、IP 表、地址分配、内部配置可能具有不同于论文资料的访问范围。当前未确认允许使用群体，未做权限隔离。
- IP 表/配置脚本默认只做 `catalog_only` 或 `deferred`，不进入公共目录、搜索片段、下载接口或回答日志。
- 未读取 `/home/whloong/projects/secret.txt` 或任何服务器凭据；未连接服务器，未修改生产索引。

### 7.5 其他未做

- 本草案未直接写入 `registry.json`、`registry-md.json` 或 `registry-v2.json`；合并由主线脚本负责。截至本次编写，主线已生成 [K1-governance-merge.md](K1-governance-merge.md)，消费了 21 个候选族、6 条冲突和 218 条处置（210 修订 / 235 处置）。若主线在本次重生成后再次合并，以主线报告为准。本草案未建索引、未启动服务、未跑评测。
- 本草案未直接登记正式修订；`target_family_id` 只是草案 slug。主线的 `registry-v2.json` 合并结果另见 [K1-governance-merge.md](K1-governance-merge.md)。
- 未确认 `data/l0_raw/incoming/2026-11-02-shine-control/资料/` 是否会被长期保留；该目录当前被 `.gitignore` 覆盖。

## 8. 需要人工/源码确认的事项

按优先级列出：

1. **V6 批准状态**：是否正式批准、替代范围（整篇/章节/指标）、生效时间、与 2017/2018 版的关系。
2. **网络安全报告**：封面日期 2026-11-05 的含义、签发/审核状态、生效日期、是否已部署、访问范围。
3. **设计能量 8 GeV vs 7.2 GeV**：两代设计是否同一基线；8 GeV 的适用条件；回答时如何按代次表述。
4. **定时指标**：原型 II 的实测抖动、测量设备/带宽/时间窗口；设计指标与实测值的区分。
5. **快联锁响应时间**：站点内/站点间、FPGA/PLC、设计/实测的测量范围；测试报告 17 页扫描件的 OCR 与复核。
6. **操作手册版本链**：第一/二/三版与 2023/2024 归档副本的逐功能对应关系；第三版是否替代第一版；3 组完全重复的合并决定。
7. **标准规范主来源**：合并版 vs 5 份单项 vs 2 份扫描副本；是否只保留合并版作为检索主来源；扫描副本是否降为 `attachment_only`。
8. **25/26 扫描副本**：当前按 `text_index/ocr` 登记；ANALYSIS §3.2 建议直接用文本版。确认等价后可降为 `attachment_only`。
9. **补充材料清单**：计划 §2.2 提出进入目录管理；当前按 `structured_index` 候选处置。确认是结构化索引还是仅目录登记。
10. **访问范围**：网络安全、IP 表、地址分配、内部配置的允许使用群体；是否需要权限隔离。
11. **族映射**：`shine-total-control-integration-design`、`shine-equipment-control-design`、`shine-upper-software-design`、`shine-power-supply-control-design`、`shine-vacuum-control-design`、`shine-motion-control-design`、`shine-alarm-system-design` 的成员是否确属同一逻辑文档；是否应拆成更细的子族。
12. **owner 指派**：6 条冲突的 `owner` 目前均为“待指派”；需在 K1 结束前由资料负责人和领域审核人确认。

## 9. 复现与校验

生成：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python -I \
  scripts/build_v2_governance.py
```

只校验不写文件：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python -I \
  scripts/build_v2_governance.py --check-only
```

JSON 语法校验：

```bash
for f in data/documents/v2/dispositions.draft.json \
         data/documents/v2/family-candidates.draft.json \
         data/documents/v2/conflict-candidates.draft.json; do
  /home/whloong/miniconda3/envs/accelerator-rag/bin/python -m json.tool "$f" > /dev/null
done
```

本次运行结果：

- dispositions：218。
- 唯一 `source_path`：218。
- `text_index`：191（19 ingest + 155 convert + 17 ocr）。
- `structured_index`：2；`attachment_only`：4；`catalog_only`：16；`deferred`：3；`excluded`：2。
- 版本族：21；成员记录 157（156 个批次路径 + 1 个旧 `doc_id`）；156 条处置有 `target_family_id`。
- 冲突：6。
- 另用主线 `accelerator_rag.corpus.schema_v2.DispositionRecord` 对 218 条逐条校验：0 错误（只读兼容性检查；生成脚本本身不 import 该模块）。

脚本不 import `accelerator_rag`，不联网。所有枚举和映射常量在脚本内；输入变化时重新运行即可复现。

## 10. 结论

- 218 个输入文件均有唯一处置记录；`source_path` 无重复。
- 191 份进入文本索引候选（19 直接 ingest、155 转格式、17 OCR）；27 份初步排除文件全部重分流，没有“无理由排除”。
- 建立了 21 个有文件名/目录/ANALYSIS 证据的版本族候选，覆盖总体设计、操作手册、分系统设计、标准规范、五类样机验收证据链、IOC/定时/网络/数据存储和命名规则。
- 记录了 6 条冲突候选，覆盖任务要求的 8 GeV vs 7.2 GeV、网络安全日期/审核、V6 批准状态、定时设计 vs 实测、快联锁测量范围，并补充了准直器操作步骤差异。
- **这些是候选，不是已批准的现行版本。** 在 K1 契约评审、K2 代表样本和 K4 全批治理完成前，不得把本报告的 `target_family_id`、`disposition` 或冲突结论直接当成生产入库依据。
