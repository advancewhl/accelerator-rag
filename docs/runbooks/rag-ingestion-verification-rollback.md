---
title: "RAG 知识入库、验证与回滚手册"
doc_type: "runbook"
applicable_system_version: "M0 0b62844；含 2026-10-29 工作区 Markdown 入库实现"
alignment_algo_hash: "不适用"
verified_date: "2026-10-29"
document_revision: "2026-10-29-ingestion-r3"
owner: "未指派"
---

# RAG 知识入库、验证与回滚手册

本文帮助维护人员把一份新文档或修订稿加入 RAG，并确认使用者能够检索到正确版本、打开原文和核对答案。流程分为准备文档、检查解析、构建候选索引、验证结果、切换服务；失败时恢复上一组可用文件与索引。

截至本次核验，工作区已实现 PDF 和 Markdown 的解析与入库路径。2026-10-29 本轮通过实际服务目录确认，线上仍是 13 份 PDF，这批 Markdown 尚未上线。后续操作仍需重新查询当前服务。

## 1. 先判断你做到哪一步了

| 当前状态 | 已完成什么 | 还要做什么 |
| --- | --- | --- |
| 文档保存在 `docs/` | 内容可以阅读和审阅 | 登记版本，生成入库用原文快照 |
| 解析和切块通过 | 程序能处理该文件 | 抽查内容，再构建候选索引 |
| 向量已写入候选索引 | 检索数据已准备 | 核对两路索引、配置和原文，启动候选服务 |
| 文档出现在服务目录 | 服务已加载相关索引内容 | 提问并检查检索、引用和回答 |
| 上述检查通过并完成切换 | 新文档可以供用户使用 | 保存本次版本、验证结果和回滚位置 |

入库的完成标准是：目标内容能检索到，引用能回到对应版本的原文，答案能被原文支持。HTTP 200、文档数量和 `answered` 标签分别只能证明其中一部分。

## 2. 准备文档：先让人读得懂，再交给系统

### 2.1 一份文档要解决一个明确任务

先说明读者是谁、要完成什么、适用于哪个系统版本。正文按操作或理解顺序展开；源码定位、审计过程和历史讨论放在附录或独立记录中。

修订时尤其要检查三个问题：参数是否带适用条件，历史行为是否标明版本，推断是否被写成事实。不要为了提高题集命中率，把问题的标准答案逐条塞进正文。

如果文档与评测题来自同一轮整理，应将这些题作为开发和回归材料。独立测试题需要另行采集、标注，并在方法开发前冻结，不能仅换一种问法就称为独立测试。

### 2.2 登记原文和版本

PDF 原文放在 `data/l0_raw/` 下，登记于 `data/documents/registry.json`。本批 Markdown 的编辑源在 `docs/waveform/`、`docs/runbooks/`，入库副本放在 `data/l0_raw/` 对应目录，使用独立的 `data/documents/registry-md.json`。

登记记录包含以下字段。格式和分类约束以 `src/accelerator_rag/corpus/registry.py`、`taxonomy.py` 为准。

| 字段 | 填写要点 |
| --- | --- |
| `doc_id` | 稳定、唯一的小写标识；修订同一文档时保留身份 |
| `title` | 给读者看的标题，也参与检索输入与引用展示 |
| `source_path` | `data/l0_raw/` 下的相对路径，与文件格式一致 |
| `category`、`topic` | 使用已有分类，避免自行创造程序不识别的值 |
| `document_type`、`language` | 如 `md`、`zh`；可登记的格式不一定都有解析器 |
| `version` | 标明这份文档的修订版；系统版本可另写在正文或元数据中 |
| `status` | 记录文档状态；当前不能靠它自动阻止文档进入索引 |

同一软件版本下也可能修订文档。更新了会影响答案的内容，应更新文档修订标识，并保留旧原文以便解释旧实验。`alignment_algo_hash` 只在相关 Waveform 文档中描述算法身份，RAG 入库本身不执行或验证该算法。

### 2.3 更新 Markdown 快照

在开发工作区根目录，使用已安装项目依赖的 Python 环境运行：

```bash
python scripts/snapshot_markdown_docs.py
python scripts/md_corpus_report.py --output tmp/md-ingestion-report.json
```

第一个命令按 Markdown 登记表复制编辑源，并更新快照记录；第二个命令解析这些副本、切块并输出报告。两者都不写向量索引。

更新快照会替换对应的本地副本。若该副本还用于解释一轮旧实验，应先把旧原文和登记表保存在该实验目录。生产服务正在使用的原文，应随对应索引一起切换，避免旧索引引用到新原文。

## 3. 检查解析：数字通过以后，还要看内容

报告中的文档数应与本次登记范围相符。逐篇查看警告、章节数、块数和可检索块数；发现某篇没有有效块时，先定位内容或解析问题，再继续建索引。

至少选取一段操作步骤、一张参数表、一段版本说明，比较原文与解析后的文本。重点看条件是否与结论分离、单位是否保留、表格行列关系是否仍能读懂。块数增加并不自动表示内容更完整。

| 来源 | 当前处理方式 | 引用位置的含义 |
| --- | --- | --- |
| PDF | 解析、清洗，再按 `pdf-chunks-v3` 切块 | `page_start`、`page_end` 是物理页码 |
| Markdown | 按标题分节，再按 `md-chunks-v1` 切块 | 同名字段是从 1 开始的章节序号 |

Markdown 调整标题或章节顺序后，章节号可能变化。当前 `/view` 使用 Markdown 阅读器，支持 `#section-N` 定位；`/sections` 返回与入库解析器一致的章节序号和原文。引用通过 `locator_kind=section` 区分 PDF 物理页。验证时按当前修订版章节和引文定位。

需要查看单篇解析结果时，可在项目根目录使用以下本地示例。它只读入库副本，不连接模型或索引。

```bash
PYTHONPATH=src python - <<'PY'
from accelerator_rag.ingestion import IngestionService

service = IngestionService('.', registry_path='data/documents/registry-md.json')
document = service.ingest_document_record('waveform-alignment-semantics')
for chunk in document.chunks:
    print(chunk.page_start, chunk.page_end)
    print(chunk.text)
    print()
PY
```

PDF 的解析检查入口和已有实验命令见[知识检索手册](knowledge-retrieval.md)、[语料基线手册](corpus-baseline.md)。部分历史实验脚本绑定了固定语料数量和问题集，不能直接当作任意新语料的发布入口。

## 4. 建索引前，先确定工作环境和回退点

### 4.1 哪些步骤在哪台机器上做

| 环境 | 路径或地址 | 适合完成的工作 |
| --- | --- | --- |
| 开发机 | `/home/whloong/projects/accelerator-rag-prab` | 编辑、登记、解析检查、通过转发访问服务 |
| GPU 主机 | `10.101.9.190`，工作区 `/opt/accelerator-rag` | 使用本地模型建索引、验证候选服务、切换正式服务 |
| 运行容器 | 工作区挂载为 `/workspace` | 按容器路径读取模型、索引与原文 |
| 本机转发入口 | `http://127.0.0.1:18003` | 访问 GPU 主机的 RAG HTTP 服务 |

能访问本机转发端口不等于具有 GPU 主机登录权限。开发机也不一定具有全部 PDF、模型和索引。

本地 Conda 环境可能以 editable 方式指向另一个工作区。运行直接导入包的命令时，使用 `PYTHONPATH=src`，确保处理的是当前工作区代码。

### 4.2 保存能够成套恢复的文件

本次变更至少要保留上一版服务配置、原文与登记表、服务代码，以及配置实际引用的两路索引。记录存放位置和本次将要替换的文件范围。

推荐在两路索引的独立副本上构建候选版本。本文采用维护窗口流程：先停止正式服务，保存旧配置、代码和原文，复制索引，再在同一工作区安装本次候选文件。完成验证后切换；失败则成套恢复旧版本。这样不会让运行中的旧索引引用已替换的新原文。

在 GPU 主机停止独立 RAG 容器：

```bash
docker stop accelerator-rag
```

构建程序和服务不能同时打开同一组本地 Qdrant 目录。需要不停服构建时，应另设完整候选工作区，隔离原文、代码、配置和索引，而不只复制索引目录。

将配置复制为 `config/rag-markdown-candidate.json`，把两个 `index_path` 分别指向候选副本。模型路径、集合名和模型契约沿用原配置。候选目录应与正式目录分开，且容器内路径必须能通过挂载实际访问。

## 5. 构建候选索引并启动验证

### 5.1 先干跑，确认处理范围

```bash
python scripts/build_markdown_index.py --dry-run \
  --registry data/documents/registry-md.json
```

确认输出只包含计划更新的文档。这个命令不打开索引、不加载 GPU 模型，也不能证明嵌入和索引写入会成功。

### 5.2 在候选副本上写入

GPU 主机需准备相同版本的代码、原文快照、登记表和候选配置。下面示例在运行镜像中建索引，使用与服务相同的 `/workspace` 路径；执行前确认 GPU 2 可用，以及候选配置的两个索引路径均已改为副本。

```bash
docker run --rm --name accelerator-rag-indexer \
  --gpus device=2 \
  -v /opt/accelerator-rag:/workspace:ro \
  -v /opt/accelerator-rag/tmp:/workspace/tmp \
  -w /workspace \
  -e PYTHONPATH=/workspace/src \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  --entrypoint /usr/bin/python3 \
  accelerator-rag-runtime:20261026 \
  scripts/build_markdown_index.py --apply \
  --config config/rag-markdown-candidate.json \
  --registry data/documents/registry-md.json
```

脚本按登记表逐篇更新两路索引。登记文档没有合格块时会报错，避免静默保留旧版本；目标集合必须已存在。Qdrant 客户端通过 `closing` 释放资源。它会替换这些文档的旧 passage，保留其他文档；不会自动修改配置，也不会删除已从登记表移除但仍留在索引中的文档。两路更新不是一个事务，一路失败时不能把另一路单独上线。

记录每一路输出的 `points_after`，分别写入候选配置的 `point_count`。两路模型可能将同一父块拆成不同数量的 passage，因此点数不必相等，也不等于文档块数。

仅修改文档时，模型和 passage 契约没有变化，`dense_index_contract_id` 通常保持原值。若模型、tokenizer 或 passage 配置改变，应按新契约构建独立集合，不能只改配置中的契约字符串。

### 5.3 启动候选服务

下面在 GPU 主机用同一运行镜像启动候选服务。先确认端口 8004 空闲、GPU 2 可用，以及仓库外的环境文件已配置生成模型访问参数：

```bash
docker run --rm --name accelerator-rag-candidate \
  --gpus device=2 --network host --ipc host \
  --env-file /opt/rag-production.env \
  -v /opt/accelerator-rag:/workspace:ro \
  -v /opt/accelerator-rag/tmp:/workspace/tmp \
  -w /workspace \
  -e PYTHONPATH=/workspace/src \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  --entrypoint /usr/bin/python3 \
  accelerator-rag-runtime:20261026 \
  -m accelerator_rag.rag \
  --config config/rag-markdown-candidate.json \
  --host 127.0.0.1 --port 8004
```

命令在前台输出日志，另开终端执行后续检查。容器采用主机网络，因此 GPU 主机可通过 `127.0.0.1:8004` 访问；开发机需要另设对应转发。默认配置中的 `/workspace` 是容器路径，直接改为宿主机 Python 运行时必须同时调整配置路径。其他部署参数见[生产服务手册](rag-production.md)。

候选服务启动时会检查模型顺序、契约、集合、点数和父块一致性。当前检索使用 BM25 与双路语义召回，再进行重排和证据处理；不能把它描述成尚未实现混合检索。

## 6. 验证：用真实问题检查文档是否有用

### 6.1 先看服务和原文

以下命令在候选服务所在环境执行；通过转发访问时，改为对应的本机端口。

```bash
curl --noproxy '*' -fsS http://127.0.0.1:8004/health
curl --noproxy '*' -fsS http://127.0.0.1:8004/v1/rag/documents
curl --noproxy '*' -fsS \
  http://127.0.0.1:8004/v1/rag/documents/waveform-alignment-semantics
```

核对计划加入的文档 ID、版本以及原文内容。只有在基线确实是 13 份 PDF、此次恰好新增 4 份 Markdown 时，预期总数才是 17。

### 6.2 再用自然问题检查回答

本批文档可先用以下问题做上线前抽查。检查要点留在评审记录中，只把问题正文发送给服务。

| 测试问题 | 人工核对重点 |
| --- | --- |
| 我采了 20 台 BPM，任务失败了，已经生成的文件还能用吗？ | 是否先查看逐设备、逐段结果，再判断适用性 |
| 每台都有两万个点，为什么对齐后只剩几百个？ | 是否检查任务、编号窗口和步长，避免直接认定设备坏了 |
| 两条曲线都从 0 秒开始，可以直接比较相位吗？ | 是否解释有效点起点和偏移信息 |
| 10 Hz 是国庆后才出现的吗？ | 是否引用历史记录，并说明归档证据的范围 |
| 今天这台 BPM 的故障已经修好了吗？ | 静态文档缺少实时状态时，是否明确缺少依据 |

逐条检查答案是否回答了用户的问题、是否保留必要条件、引文是否真的支持结论、引用版本是否一致。对数值尤其检查单位、比较符和“设计要求／实测结果”的区别。Phase 1 已出现过把“小于某值”写成“指标为某值”的错误，接口和状态检查无法发现它。

### 6.3 保留必要的回归证据

原有 36 题接口回归入口如下。运行前按变更影响决定是否需要全量回归，定向文档检查不必反复触发完整评测。

```bash
python scripts/rag_framework_check.py \
  --base-url http://127.0.0.1:8004 \
  --output tmp/md-candidate-http.json
```

该脚本读取原冻结的 32 题，并追加 4 题；`--questions` 要求 `queries` 下含 `id`、`query`、`answerable`，不能直接传入另一种结构的 50 题种子集。需要检查轮次和检索预算时，提供候选服务的 `--trace-dir`；没有 trace 时不要声称这些项目已核验。

新 50 题使用 `scripts/run_validity_pilot.py`，先校验版本、章节／页码、原文摘录及可检索块。HTTP 模式会先检查线上目录版本，缺少目标 Markdown 时停止，不把错误语料上的问答计为新基线。完整命令和评分规则见[50 题协议](../rag/validity-pilot-50.md)。

`rag_framework_review.py` 和 `rag_framework_metrics.py` 是既有 PDF 基准的复核工具。使用前核对其输入目录、原文要求和固定题集假设；它们不能直接替代这批 Markdown 的引用与语义检查。特别是 metrics 脚本绑定旧报告目录，不能把旧结果写成本次候选版本的结果。

报告至少分开记录接口通过、证据定位和人工语义判断。项目的 Hit@K 按题目要求的证据覆盖计算：`all` 模式要求覆盖全部证据组，`any` 模式要求任一组；MRR@5 使用首次满足题目完整判断的排名。具体定义见[评测说明](../../data/evaluation/README.md)。

## 7. 切换服务与回滚

### 7.1 通过验证后再切换

先执行 `docker stop accelerator-rag-candidate`，释放候选索引。将通过验证的原文、登记表、代码和候选配置作为同一发布版本；正式配置引用两路已验证的候选索引路径。

在 GPU 主机使用既有部署入口切换独立 RAG 服务：

```bash
RAG_ENV_FILE=/opt/rag-production.env \
  bash /opt/accelerator-rag/deploy/rag-start.sh
```

该入口会替换已有的独立 RAG 容器。切换后检查健康状态、文档目录和本次新增内容的一条代表性问题，确认运行环境与候选验证一致。保留旧配置、原文和索引，直到本次发布完成验收。

### 7.2 出问题时恢复哪一层

| 故障 | 优先检查 | 恢复方式 |
| --- | --- | --- |
| 服务启动失败 | 配置路径、模型顺序、契约和点数 | 恢复上一版成套配置与兼容代码 |
| 两路索引只更新成功一路 | 建索引输出和各路实际状态 | 保持旧版本服务，修复或重建候选副本 |
| 回答引用旧内容或混合版本 | 候选索引、原文快照、文档版本 | 恢复上一版索引和对应原文，重新检查更新范围 |
| 文档目录有记录但引用打不开 | 原文是否存在、路径与格式是否匹配 | 恢复该版本原文及兼容的展示代码 |
| 服务正常但语义结果退步 | 具体问题、引文和本次文档修改 | 恢复旧发布版本，定位内容或检索变化后再验证 |

回滚时先停用正在持有目标索引的服务，恢复上一次保存的代码、配置、登记表和原文，让配置重新指向旧的两路索引，再通过相同部署入口启动。不要把旧原文与新索引混搭，也不要一边运行服务一边覆盖其索引目录。

回滚后检查健康状态、目录和失败场景对应的问题，并记录恢复到哪个版本。现有脚本没有跨代码、原文、两路索引的自动事务回滚，这些步骤由维护人员执行。

## 8. 维护参考与完成记录

一次入库记录应让接手的人看懂：改了哪些文档、为什么改、使用哪个版本、解析有没有丢内容、两路索引放在哪里、哪些问题已验证、失败时回到哪里。文档数量和状态标签不能代替这些信息。

| 需要追查的行为 | 本仓库入口 |
| --- | --- |
| 登记与原文路径 | `src/accelerator_rag/corpus/registry.py` |
| PDF、Markdown 解析及切块 | `src/accelerator_rag/ingestion.py`、`corpus/markdown_parser.py`、`corpus/chunking.py` |
| Markdown 快照与本地报告 | `scripts/snapshot_markdown_docs.py`、`scripts/md_corpus_report.py` |
| 更新候选索引 | `scripts/build_markdown_index.py`、`retrieval/dense.py` |
| 启动检查与文档展示 | `src/accelerator_rag/rag/runtime.py`、`rag/api.py`、`rag/catalog.py` |
| 混合召回 | `src/accelerator_rag/rag/retrieval.py` |
| 正式服务启停 | `deploy/rag-start.sh`、[生产服务手册](rag-production.md) |

本文以 M0 `0b62844` 和 2026-10-29 工作区中的 Markdown 支持代码为依据。工作区能力与生产部署状态分开记录；Phase 1 历史材料见[交付目录](../../reports/phase1-m0-20261029/)。本文重写本身没有执行 GPU 建索引、服务切换或回滚。
