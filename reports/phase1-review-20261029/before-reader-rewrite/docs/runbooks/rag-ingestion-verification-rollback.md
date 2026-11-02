---
title: RAG 知识入库、验证与回滚手册
doc_type: runbook
applicable_system_version: "0b62844（2026-10-28 15:59 提交）。部署清单 reports/rag-framework-20261028/deployment-verification.json 记录 15 个文件的 expected/local/remote SHA-256；2026-10-29 复核：当前工作区 14/15 与清单一致，docs/runbooks/rag-production.md 在部署后被修改并随 0b62844 提交（清单值 90f617bf…，当前值 7588fae2…），差异范围与影响见第 1.4 节。"
alignment_algo_hash: 不适用。本手册描述 RAG 语料的登记、解析、切块、双路嵌入、签名索引、启动核验、HTTP 验证与回滚，不引用也不绑定 Waveform 对齐算法；因此没有可写的算法哈希，而不是“暂缺”。若未来把 Waveform 对齐算法文档纳入本 RAG 语料并要求与实现绑定，须按第 8.4 节的绑定规则补充该字段。
verified_date: 2026-10-29
owner: 未指派（待项目负责人裁决）
audience: 具备 GPU 主机登录权限与部署权限的运维/研发人员
status: draft
---

# RAG 知识入库、验证与回滚手册

本手册回答三个问题：**一份文档怎样才算“入库”**、**入库后怎样验证它真的可被检索并引用**、**出错时怎样退回去**。所有参数、阈值和报错文案以代码为准，并标注 `文件:符号`；无法在本机复现的步骤明确写出执行机器与权限条件。

> 术语约定：**“文件已保存”≠“已入库”**。本手册把“入库”定义为：满足 1) registry 登记通过校验、2) 解析器能产出结构化页/块、3) 切块得到稳定 `chunk_id`、4) 通过资格策略进入 eligible 集合、5) 双路嵌入写入与 `dense_index_contract_id` 绑定的签名索引、6) 生产 runtime 启动核验通过且 HTTP 检索可引用。缺任一环，最多只能记录为“文件已保存”。

**证据等级标记**：`【实测】`=本次 2026-10-29 在本机执行并留档（见 `reports/phase1-m0-20261029/ingestion-path/verification.md`）；`【仓库记录】`=仓库内既有文档/报告，本次未重跑；`【未验证】`=本机权限或数据不足，需在 GPU 主机执行。

---

## 0. 三分钟速查

| 事项 | 现状 | 依据 |
| --- | --- | --- |
| 已入库文档 | 13 份 PDF、2178 物理页、4537 规范父块，其中 4532 个 eligible | `docs/roadmap/CURRENT.md:43`；线上 `/v1/rag/documents` 实测 `indexed_section_count=4532`【实测】 |
| 已实现格式 | **仅 PDF** | `src/accelerator_rag/ingestion.py:55-56`【实测】 |
| Markdown 入库 | **未实现（阻塞）** | 第 8.3 节 |
| 双路索引 | E5 `4746` points、Qwen3 `4532` points，契约 ID 写死在 `config/rag-production.json` | 同文件 + 第 4.4 节【实测】 |
| 启动核验 | 每次启动完整扫描一次，随后只读；禁止第二进程持有同一索引 | `src/accelerator_rag/rag/runtime.py`、`storage/qdrant_passages.py` |
| 自动回滚 | **未实现**，只有手工恢复步骤 | 第 7.7 节 |

---

## 1. 环境与前置条件

### 1.1 两台机器，别搞混

| 角色 | 位置 | 有什么 | 能做什么 |
| --- | --- | --- | --- |
| 开发机（本机） | `/home/whloong/projects/accelerator-rag-prab` | 源码、registry、评测集、测试、报告；**没有** `data/l0_raw`，**没有** `tmp/`（模型与索引） | 改文档/代码、跑纯本地测试、只读 HTTP 检查 |
| GPU 主机 | `10.101.9.190` | 稳定目录 `/opt/accelerator-rag`、原始语料 `/workspace/data/l0_raw`、模型与索引 `/workspace/tmp/stage-two-*`、生产容器 | 建索引、启停容器、跑需要语料的验证 |

本机到 GPU 主机的唯一通道是 SSH 端口转发：用户级服务 `accelerator-rag-tunnel.service` 把 `127.0.0.1:18003` 转发到 `10.101.9.190:8003`（见 `deploy/systemd/user/accelerator-rag-tunnel.service`）。**该转发只提供 TCP 端口，不提供 GPU 主机的 SSH 登录权限**；第 5、7 节的服务器侧命令必须有 GPU 主机登录权限才能执行【实测：本机 `ssh` 到 `10.101.9.190` 返回 `Permission denied`】。

```bash
# 开发机：确认转发仍在（只读）
systemctl --user status accelerator-rag-tunnel.service --no-pager
curl --noproxy '*' -fsS http://127.0.0.1:18003/health
# 期望：Active: active (running)；{"status":"ok"}
```

故障处理：浏览器/curl 提示连接被拒 → 先区分是隧道还是远端服务：

```bash
journalctl --user -u accelerator-rag-tunnel.service -n 50 --no-pager
```

隧道断了按 `docs/runbooks/rag-production.md:44-54` 的安装步骤恢复；远端服务问题见第 5.6 节。

### 1.2 容器与挂载（决定了“哪里能写”）

部署脚本 `deploy/rag-start.sh`【仓库记录】：

```bash
docker run -d --name accelerator-rag --label accelerator-rag.service=standalone \
  --gpus "device=${RAG_GPU_DEVICE:-2}" --network host --ipc host --restart unless-stopped \
  -v "$workspace:/workspace:ro" -v "$workspace/tmp:/workspace/tmp" -w /workspace \
  -e PYTHONPATH=/workspace/src -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  ... -m accelerator_rag.rag --config config/rag-production.json --host 0.0.0.0 --port 8003
```

| 宿主路径 | 容器路径 | 权限 | 用途 |
| --- | --- | --- | --- |
| `/opt/accelerator-rag` | `/workspace` | **只读** | 源码、`config/rag-production.json`、`deploy/`、`data/l0_raw`、`data/documents/registry.json` |
| `/opt/accelerator-rag/tmp` | `/workspace/tmp` | 读写 | 模型、本地 Qdrant 索引、请求 trace、备份 |

推论：对代码/配置/语料的任何修改都必须在**宿主**完成再重启容器；运行期代码不可能被容器内写坏。索引在 `tmp/`（可写），所以“运行期禁止写索引”是靠代码 `freeze_read_only()` 与运维纪律，而不是挂载权限（见第 5.3/5.4 节）。

### 1.3 环境变量与凭据

凭据放在**仓库外**、权限 `600` 的环境文件，当前主机为 `/opt/rag-production.env`。禁止把密钥写入 Git、日志、网页或本手册。

| 变量 | 作用 | 覆盖方式 |
| --- | --- | --- |
| `ACCELERATOR_MODEL_BASE_URL` | 生成模型地址，默认 `http://127.0.0.1:8000/v1` | 环境文件 / 进程环境（`rag/runtime.py:67-70`） |
| `ACCELERATOR_MODEL_NAME` | 模型名，默认取 `config/rag-production.json` 的 `model_name`（`ds-1017`） | 同上（`rag/runtime.py:71-75`） |
| `ACCELERATOR_MODEL_API_KEY` | Bearer 凭据；缺失时不发送认证头 | 同上（`rag/runtime.py:74`、`:170`） |
| `RAG_ENV_FILE` | `rag-start.sh` 传给 `docker --env-file` | 启动命令 |
| `RAG_GPU_DEVICE` / `RAG_WORKSPACE` / `RAG_RUNTIME_IMAGE` | 覆盖 GPU 号、稳定目录、镜像 | 启动命令 |

安全边界（`rag/runtime.py:78-83`）：模型地址的 host 只允许 `127.0.0.1`、`localhost`、`10.101.9.190`；HTTP 客户端 `trust_env=False`、不跟随重定向。

### 1.4 版本标识与部署清单核验

本手册的 `applicable_system_version` 由两部分组成：**git commit** + **部署清单哈希核对结论**，缺一不可（工作区可能脏，单靠 commit 不能标识实际运行代码）。

```bash
# 开发机
git rev-parse --short HEAD                 # 0b62844
git rev-parse HEAD                         # 0b628447c2a50a848d7f5ce7f6b74d5e46fe57cd
git status --porcelain                     # 工作区是否脏；脏则不能只用 HEAD 标识
```

部署清单 `reports/rag-framework-20261028/deployment-verification.json` 逐文件记录 `expected_sha256`/`local_sha256`/`remote_sha256`，共 15 个文件（11 个 `src/accelerator_rag/rag/*.py`、`config/rag-production.json`、`deploy/rag-requirements.txt`、2 份文档）。

复核命令与 2026-10-29 的实际结果【实测】：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python - <<'PY'
import json, hashlib, pathlib
rows = json.load(open("reports/rag-framework-20261028/deployment-verification.json"))
same, diff = 0, []
for r in rows:
    p = pathlib.Path(r["path"])
    cur = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    if cur == r["expected_sha256"]:
        same += 1
    else:
        diff.append((r["path"], r["expected_sha256"], cur))
print("match", same, "of", len(rows))
for path, exp, cur in diff:
    print("DIFF", path, "\n  expected", exp, "\n  current ", cur)
PY
# 输出：match 14 of 15
#       DIFF docs/runbooks/rag-production.md
#         expected 90f617bfef81ab50d2c462ff4f59d3cb02e7350137870195b0297d7ec39cbd7a
#         current  7588fae2093bb207c7d456da6e1c73dee59dc969caf3d202352cdf84d9656290
```

判定与影响：

- 11 个运行时代码文件 + `config/rag-production.json` + `deploy/rag-requirements.txt` **全部一致** → 当前工作区的运行代码与 2026-10-28 部署快照等价，本手册描述的服务行为适用。
- `docs/architecture/rag-evidence-workflow.md` 一致。
- `docs/runbooks/rag-production.md` 不一致：部署值 `90f617bf…` 在 git 历史中不存在（`git log --all -- docs/runbooks/rag-production.md` 只有 `0b62844`，blob 为 `7588fae2…`），说明该文档在部署后又被编辑，并随 `0b62844` 提交。**它只是文档，不改变运行行为**；但意味着“仓库里的 runbook”不等于“GPU 主机上的 runbook”，第 7 节回滚到部署快照时会把该文档恢复成 `90f617bf…` 版本。
- `remote_sha256` 是 2026-10-28 部署时记录的值；本次**无法**重新核对远端文件（无 GPU 主机登录权限），只能引用当时记录【未验证：远端现状】。

### 1.5 本机 Python 环境与一个必须知道的坑

```bash
PY=/home/whloong/miniconda3/envs/accelerator-rag/bin/python
$PY -V            # Python 3.11.15
$PY -c "import pymupdf, httpx, pytest; print(pymupdf.__doc__.split()[1], httpx.__version__, pytest.__version__)"
# 1.28.2: 0.28.1 8.4.2
```

坑：该 conda 环境的 `accelerator-rag` 是 **editable 安装，指向兄弟目录** `/home/whloong/projects/accelerator-rag`，不是本工作区。

```bash
$PY -c "import accelerator_rag; print(accelerator_rag.__file__)"
# /home/whloong/projects/accelerator-rag/src/accelerator_rag/__init__.py
```

在本工作区跑任何脚本/测试，显式加 `PYTHONPATH=src`，并确认导入路径：

```bash
cd /home/whloong/projects/accelerator-rag-prab
PYTHONPATH=src $PY -c "import accelerator_rag; print(accelerator_rag.__file__)"
# /home/whloong/projects/accelerator-rag-prab/src/accelerator_rag/__init__.py
```

两个 checkout 的 `corpus/*`、`ingestion.py`、`retrieval/index_contract.py`、`domain/knowledge.py` 逐字节相同（`config.py` 不同，但生产 RAG 不读它）；不加 `PYTHONPATH=src` 会测到另一份代码，结论看似成立、实际不可归属【实测，见 verification.md 第 1 节】。

### 1.6 禁止事项（本手册所有步骤的前提）

- 禁止在运行期写正式索引、修改 payload、给未知索引“补签”。
- 禁止同时启动第二个进程持有同一组本地 Qdrant 索引（本地模式无并发保护，见 5.4）。
- 禁止把凭据、`/opt/rag-production.env` 内容、模型认证请求头写入 Git、日志或报告。
- 禁止在未备份、未核对 manifest 的情况下覆盖 `/opt/accelerator-rag` 或索引目录。
- 禁止把“接口返回 `answered`”当作“回答正确”（见 6.1）。
- 修改 `src/`、`config/rag-production.json`、`registry.json` 属于**变更**，需走第 7 节的备份流程；本手册不授权任何变更。

---

## 2. 语料登记（`data/documents/registry.json`）

### 2.1 记录结构

registry 是 JSON 数组，每项恰好是 `DocumentRecord` 的 9 个字段（少字段/多字段都会失败，`corpus/registry.py:126-129`）：

| 字段 | 约束 | 代码 |
| --- | --- | --- |
| `doc_id` | 小写字母/数字，单连字符分隔 slug，正则 `^[a-z0-9]+(?:-[a-z0-9]+)*$`；全表唯一 | `registry.py:15,52-53,131-132` |
| `title` | 非空字符串、无首尾空白；参与 embedding 输入与引用展示 | `registry.py:34-50` |
| `source_path` | 必须 `data/l0_raw/` 下的**相对 POSIX** 路径；禁止绝对路径、`..`、反斜杠；扩展名必须等于 `.{document_type}`；全表唯一 | `registry.py:68-79,133-134` |
| `category` | 必须在 `corpus/taxonomy.py:VALID_CATEGORIES`：`control_system`、`high_level_application`、`beam_diagnostics`、`accelerator_physics` | `registry.py:61-62` |
| `topic` | 必须在所属 category 的 `TOPICS_BY_CATEGORY` 内（含 `waveform`，属于 `beam_diagnostics`） | `registry.py:64-66`、`taxonomy.py:4-38` |
| `document_type` | 集合 `{docx, md, pdf, pptx, txt}`——**仅表示可登记**，不代表可入库 | `registry.py:12,55-56` |
| `language` | `{en, unknown, zh, zh-en}` | `registry.py:13,57-58` |
| `version` | 非空字符串，随 chunk 冻结进 `chunk_id` 身份；改动即产生新 chunk ID | `registry.py:34-50`、`chunking.py:71-84` |
| `status` | `{active, deprecated, draft, reference, unknown}`；当前只做统计，不参与过滤 | `registry.py:14,59-60`、`corpus_inventory.py:44` |

示例（当前第一条真实记录）：

```json
{
  "doc_id": "epics-application-developers-guide-r3-16-2",
  "title": "EPICS Application Developer's Guide",
  "source_path": "data/l0_raw/EPICS/EPICS_Application_Developers_Guide_R3.16.2.pdf",
  "category": "control_system",
  "topic": "epics",
  "document_type": "pdf",
  "language": "en",
  "version": "R3.16.2 (2018-10-22)",
  "status": "active"
}
```

### 2.2 什么格式“被接受”

| 格式 | registry 可登记 | 能解析 | 能进索引 | 结论 |
| --- | --- | --- | --- | --- |
| `pdf` | 是 | 是（`pymupdf`） | 是 | 唯一完整支持的格式 |
| `md` / `txt` / `docx` / `pptx` | 是（schema 允许） | **否** | **否** | 登记成功也会在入库入口被拒绝或静默跳过（第 8.3 节） |

### 2.3 登记步骤（PDF，当前唯一可完成入库的格式）

在 **GPU 主机**（语料所在机器）执行：

1. **放文件**：把 PDF 放到 `/opt/accelerator-rag/data/l0_raw/<子目录>/<文件名>.pdf`。文件名与目录随文档来源组织，`source_path` 必须与之完全一致。
2. **加记录**：编辑 `/opt/accelerator-rag/data/documents/registry.json`，按 2.1 加一条。仓库内**没有登记 CLI**，只能手工编辑 JSON，必须走 code review。
3. **加载校验**（只读，不会写任何东西）：

```bash
cd /opt/accelerator-rag && PYTHONPATH=src python - <<'PY'
from accelerator_rag.corpus.registry import load_registry
records = load_registry("data/documents/registry.json")
print("records:", len(records))
print("types:", {t: sum(r.document_type == t for r in records) for t in sorted({r.document_type for r in records})})
PY
# 期望：records: 14（新增后）；types: {'pdf': 14}
```

4. **对账**（登记 ↔ 实际文件）：

```bash
cd /opt/accelerator-rag && PYTHONPATH=src python scripts/corpus_inventory.py; echo "exit=$?"
```

正常输出（当前冻结语料，`docs/runbooks/corpus-baseline.md:19`）应包含：

```text
registered_documents: 13
registered_pdfs: 13
unsupported_unmanaged_source_files: 5
validation: OK
exit=0
```

5. **新增语料 ≠ 自动入库**：生产索引是冻结的签名索引（第 4 节）。新增 PDF 后要**重新构建索引、更新 contract/point_count、重启容器**，而构建脚本对语料数量有硬断言（`src/accelerator_rag/retrieval/multilingual_baseline.py:117`：`assert len(docs) == 13 and len(eligible) == 4532`）。也就是说“加一份文档”是**代码+索引版本变更**，不是配置变更。此步必须由项目负责人裁决并走第 7 节备份流程。

### 2.4 校验点

| 校验点 | 通过标准 |
| --- | --- |
| registry 可解析 | `load_registry` 无异常，记录数符合预期 |
| 对账一致 | `validate_inventory` 通过，`exit=0`；`missing_files`、`unregistered_files` 为空 |
| 未登记的非 PDF | 允许：只出现在 `unsupported_unmanaged_sources`，不影响 PDF 校验 |
| 统计口径 | `by_document_type`、`by_language`、`by_status` 与预期一致（当前冻结语料：13 份全部 pdf；语言 en=10、zh=3，以 `corpus_inventory.py` 实际输出为准） |

【实测】本机没有 `data/l0_raw`，`python scripts/corpus_inventory.py` 退出码 1，报 `raw 目录不存在`——对账步骤只能在 GPU 主机做（verification.md 第 2/6 节）。

### 2.5 失败处理

| 报错 | 原因 | 处理 |
| --- | --- | --- |
| `registry 文件不是合法 JSON: line X, column Y` | 手工编辑引入语法错误 | 按行列修复；用 `python -m json.tool` 先验 |
| `registry 第 N 条记录无效: ... 不能为空/不支持 ...` | 字段缺失、空值、非法枚举 | 对照 2.1 修字段；不要放宽校验 |
| `registry 存在重复 doc_id / 重复 source_path` | 复制粘贴重复 | 删除重复项；`doc_id` 变更等于新文档身份 |
| `source_path 必须位于 data/l0_raw 下` / `安全相对路径` | 绝对路径、`../`、反斜杠 | 改成 `data/l0_raw/...` POSIX 相对路径 |
| `source_path 扩展名必须与 document_type 一致` | `.md` 配 `document_type=pdf` 之类 | 二者必须匹配；注意匹配也不代表能入库 |
| `不支持的 category/topic` | 用了 taxonomy 外的新话题 | 先改 `corpus/taxonomy.py`（代码变更，需评审），或使用已有话题（`waveform` 已存在） |
| `登记但缺失: ...` | 文件没放对位置/改名 | 补文件或修 `source_path`；**不要**把缺失记录留在 registry |
| `存在但未登记: ...pdf` | 有 PDF 未登记 | 登记或删除文件；未登记 PDF 会阻塞对账 |
| 未登记 `pptx/docx/md` 只出现在 unmanaged 列表 | 设计如此（`registry.py:181-185`） | 无需处理，但**不要**因此认为它们已入库 |

---

## 3. 解析与切块（`pdf-chunks-v3`）

### 3.1 解析：`parse_pdf`

入口：`src/accelerator_rag/corpus/pdf_parser.py:183` `parse_pdf(path, *, source_path=None)`。`source_path` 是**逻辑标识**（registry 里的相对路径），不会被推断成本机绝对路径；不传时默认文件名。

输出结构：

```text
ParsedPdfDocument(source_path, file_name, page_count, metadata, pages, warnings)
  └─ PdfPage(page_number, width, height, text, char_count, blocks, image_count, warnings)
       └─ PdfTextBlock(block_number, block_type, bbox, text)
```

- `page_number` 从 1 开始，是 **PDF 物理页**，不是印刷页码（`pdf_parser.py:171-172`）。
- `bbox` 单位是 PDF 点（1/72 英寸），保留给清洗阶段做版面判断。
- 空文本 block 被丢弃（`pdf_parser.py:53-56`）。

校验点（页级 warning，`pdf_parser.py:126-152`）：

| warning | 触发条件 | 含义 |
| --- | --- | --- |
| `empty_text` | 页文本为空 | 可能是扫描件或矢量页 |
| `possible_scanned_page` | 文本 < 50 字符且含图片 | 需要 OCR（未实现） |
| `possible_two_column` | 左右栏各 ≥ 2 个中等宽度长 block | 版面启发式命中 |
| `possible_garbled_text` | 含 `U+FFFD` 或 `\x00` | 编码/字体问题 |
| `private_use_characters` | 含 PUA 字符（U+E000–U+F8FF） | 自定义字形，可能不可读 |

文档级 warning：`empty_document`（无页）、`no_extractable_text`（全部页 `char_count == 0`）。

```bash
# GPU 主机：单篇解析自检（只读，不写索引）
cd /opt/accelerator-rag && PYTHONPATH=src python - <<'PY'
from accelerator_rag.corpus.pdf_parser import parse_pdf
p = parse_pdf("data/l0_raw/Hard_XFEL_SHINE/The_Cryogenic_Control_System_of_SHINE_2021.pdf",
              source_path="data/l0_raw/Hard_XFEL_SHINE/The_Cryogenic_Control_System_of_SHINE_2021.pdf")
print("pages:", p.page_count, "warnings:", p.warnings)
print("page 6 chars:", p.pages[5].char_count, "blocks:", len(p.pages[5].blocks))
PY
# 期望：pages: 8 warnings: []（以实际 PDF 为准）；用于确认语料完整、可抽文本
```

### 3.2 清洗：`clean_page_texts`

入口：`src/accelerator_rag/corpus/cleaning.py:109`。只改“检索用文本”，**不改** `ParsedPdfDocument`，原始证据始终可回溯。

规则（启发式，不是完整版面重建）：

1. **页边带**：`TOP_MARGIN=0.065`、`BOTTOM_MARGIN=0.93`、`SIDE_MARGIN=0.10`（`cleaning.py:14-16`）。落在页边带且满足下列任一条件的 block 丢弃：文档内重复签名（出现 ≥2 次）、`ISBN/ISSN`、版权/许可声明、纯页码、running code。
2. **跨页重复页眉/页脚**：同签名在页面高度 `y<18%` 或 `y>82%`、文本 ≤110 字符、稳定位置出现 ≥ `max(6, 页数×10%)` 页（`cleaning.py:124-139`）。这条比“页边带”更宽，能捕获内嵌书页边距。
3. **首页前置内容**：若“Abstract/摘要”标题的 y 坐标位于页面上部 35% 以内（`bbox[1] < 页面高度×0.35`）且它之前的 block 都 <500 字符，则丢弃它之前的内容（`cleaning.py:149-157`）。
4. **末页参考文献**：“References/Bibliography/参考文献”标题之后有 ≥2 条编号引文时，标题及其后全部丢弃（`cleaning.py:158-169`）。
5. **双栏排序**：跨栏 block 作为垂直分隔，区域内先左后右，页边注音放到最后（`order_body_blocks`，`cleaning.py:179-209`）。
6. **断词修复**：仅当文档其他位置存在完整拼写、且不存在完整连字符拼写时，合并 `head-\ntail`；否则保留连字符（`normalize_text`，`cleaning.py:27-51`）。
7. **空白规范化**：`\x00` 删除、`\r\n`→`\n`、行内连续空白折叠为单空格、段落间保留空行。

已知误判：与正文合并的页眉可能漏过滤；摘要/参考文献边界是位置启发式，特殊版面可能误截。原始文本保留，所以可复查。

### 3.3 切块：`chunk_pdf` + `ChunkingConfig`

入口：`src/accelerator_rag/corpus/chunking.py:56`。参数（`chunking.py:15-28`）：

| 参数 | 默认 | 约束 | 语义 |
| --- | --- | --- | --- |
| `max_chars` | 1200 | 正整数 | **硬上限**，任何切分结果不得超过 |
| `min_chars` | 300 | `0 < min_chars ≤ max_chars/2` | **软下限**（短页/尾块可低于它） |

规则：

- 以**清洗后的页**为单位，**不跨页、不重叠**；空页不产生 chunk，也不影响后续物理页号。
- 超长页循环切分：优先 `\n\n`（段落），其次句末 `[.!?。！？]`，再次空白，最后才硬切；切点离页尾不足 `min_chars` 时提前切，避免留下超短尾块（`chunking.py:31-53`）。
- 每块保留 `page_start == page_end`（物理页）、`document_id/title/version/language/category/topic/source_path`。

### 3.4 `chunk_id` 的计算

对每个（页号, 页内序号, 块文本）计算（`chunking.py:71-87`）：

$$
\text{chunk\_id} = \text{doc\_id} \;\Vert\; \text{":"} \;\Vert\; \operatorname{SHA256}\!\left(
\operatorname{JSON}_{\text{canonical}}\!\left[
\texttt{"pdf-chunks-v3"},\;
\operatorname{asdict}(\text{ChunkingConfig}),\;
\text{doc\_id},\;
\text{version},\;
\text{page\_number},\;
\text{ordinal},\;
\text{piece}
\right]
\right)
$$

其中 `JSON_canonical` 为 `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`。含义：

- 同一文档、同一版本、同一配置、同一文本 → **确定性同一 ID**；不依赖 Python `hash()`、随机数、本机路径。
- 改动 `max_chars/min_chars`、文档 `version`、清洗逻辑或切块逻辑 → 全部相关 ID 变化，必须同步改算法版本号（`CHUNKING_ALGORITHM`，`chunking.py:12`），否则新旧块无法区分。
- 向量库 point ID 由 chunk/passage ID 再派生：`uuid5(NAMESPACE_URL, "accelerator-rag:{id}")`（`storage/qdrant_collection.py:41-43`），所以“稳定 ID”同时保证 upsert 幂等，重跑不累积重复点。

实测样例【实测】（自造 3 页 PDF，其中第 2 页为空）：

```text
parse_pdf -> page_count=3, warnings=[]
chunk_pdf -> 2 chunks, algorithm=pdf-chunks-v3
  page_start=1 chars=87 chunk_id=demo-pdf:b825f8bb46cbcc6ac2c13d5af1b6340e02e8b84e16153f144f092ef67756baae
  page_start=3 chars=53 chunk_id=demo-pdf:2d7f4135543b991fe6ada8d588126d90a7c184679ec2d7489dfe9a076bf6f436
```

校验点：同一输入重复切块，`chunk_id` 列表必须完全一致；空页不产生块且第 3 页仍为 `page_start=3`。

### 3.5 检索资格（eligibility，独立于切块）

入口：`src/accelerator_rag/corpus/eligibility.py:30` `assess_retrieval_eligibility`。它**不修改也不删除 Chunk**，只给索引策略提供“可进索引/不进索引”的判定。参数（`eligibility.py:9-18`）：

- `replacement_ratio = 0.20`：非空白字符中 `U+FFFD` 的比例阈值；
- `minimum_replacements = 8`：替换字符个数下限；
- 两条同时满足才判 `mostly_replacement_chars`。

排除原因（`eligibility.py:40-67`）：

| reason | 条件 |
| --- | --- |
| `boilerplate_only` | 归一化后仅为“谢谢/致谢/thanks/acknowledgements”等 |
| `number_or_running_code_only` | 全文匹配 `\d+` 或 `[A-Z]{1,8}\d{1,8}` |
| `document_title_only` | 与文档标题相同、token ≥3、且不含数字 |
| `too_little_semantic_content` | 无任何字母/数字/汉字 |
| `mostly_replacement_chars` | ≥8 个 `U+FFFD` 且占比 ≥20% |

语义边界：20% 是“语料损坏审查 + 边界测试”定的保守起点，**不是模型质量最优阈值**，也不是检索分数阈值（`docs/runbooks/corpus-baseline.md:50,80`）。U+FFFD 与 PUA 原样保留，不做公式恢复或 OCR。

### 3.6 全量审计入口

```bash
# GPU 主机（需要 13 份 PDF + 本地模型缓存；只读原始语料，写独立实验集合）
cd /opt/accelerator-rag && \
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONPATH=src python -m accelerator_rag.retrieval.corpus_baseline \
  --project-root . --collection knowledge_stage25 --qdrant-path tmp/stage-two-five-qdrant --batch-size 32
```

输出 `reports/rag-stage-two-five-corpus-audit.{json,md}` 与 `…-retrieval-baseline.{json,md}`（`docs/runbooks/corpus-baseline.md:35-41`）。【仓库记录】本次未重跑。

失败处理：解析/切块/资格阶段报错时**不要**跳过该文档继续，`IngestionService` 的批量入口是 fail-fast（`ingestion.py:59-65` 逐文档构造，异常即中断）；先按 3.1–3.3 定位单篇，再重跑。

---

## 4. 嵌入与索引（E5 + Qwen3 双路）

### 4.1 双路模型与输入契约

| 通道 | 模型 | 查询侧输入 | 文档侧前缀 | 维度 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 1 | `intfloat/multilingual-e5-base` | `query: {query}` | `passage: ` | 768（模型卡；本机无权重未复算） | 生产 `config/rag-production.json` 固定顺序第一 |
| 2 | `Qwen/Qwen3-Embedding-0.6B` | `Instruct: …\nQuery:{query}` | 无 | 由模型给出 | last-token pooling，只有查询加 instruction |

契约写死在 `src/accelerator_rag/embedding.py:38-50`，未登记的模型名直接 `ValueError("unverified retrieval encoding contract")`——**换模型必须改代码并新建索引**，不能只改配置。

文档侧实际输入统一为：

$$
\text{embed\_input} = \text{document\_title} \;\Vert\; \texttt{"\textbackslash n"} \;\Vert\; \text{passage.text}
$$

（`DenseIndexContract.document_template`，`retrieval/index_contract.py:35`；E5 的 `passage: ` 前缀由 `document_prefix` 施加。）

### 4.2 passage 表示：`dense-passages-v1`

父块（`KnowledgeChunk`）是引用单元，向量不直接挂在父块上：超长父块按 token 拆成 passage，检索后按父块去重取最大分（`docs/runbooks/dense-passages.md:36-54`）。参数（`retrieval/passages.py:15-21`）：

| 参数 | 默认 | 语义 |
| --- | --- | --- |
| `max_tokens` | `None` → 用模型 `max_seq_length` | 单个 passage 的完整输入 token 上限 |
| `guard_tokens` | 16 | 拆窗时为标题/模板/special tokens 预留 |
| `overlap_tokens` | 32 | 相邻窗口重叠的原始 token 数 |

硬约束（`passages.py:48-72`、`embedding.py` 的 `embed_token_safe_documents`）：

- 已适配模型上限的父输入 → 保留 1 条与父文本完全相同的 passage（**不做无谓拆分**）。
- 超限才拆；每个窗口重新计算完整输入长度，超过上限立即失败，**不允许静默截断**。
- `passage.text` 必须是父文本的精确子串（`passages.py:64-70`），保证引用可回到原文。
- passage ID 也是 SHA-256：算法版本 + 模型/tokenizer contract + passage 配置 + 父 ID + 序号 + 标题 + 正文 + 字符范围。

实测间接印证：E5 索引 `4746` points、Qwen3 索引 `4532` points，而 eligible 父块是 `4532`——说明 E5 侧存在拆分（同一父块 → 多条 passage），Qwen3 侧每个父块 1 条 passage。具体拆分阈值由各模型 `max_seq_length` 决定，本机无权重无法复算【实测：仅核对点数与契约 ID 长度；阈值复算未验证】。

### 4.3 四个版本标签，别混

| 标签 | 定义位置 | 是什么 | 变了要做什么 |
| --- | --- | --- | --- |
| `pdf-chunks-v3` | `corpus/chunking.py:12` | **切块算法版本**，进 chunk ID 身份 | 改清洗/切块逻辑时改版本号；相关索引全部重建 |
| `dense-passages-v1` | `retrieval/passages.py:13` | **passage 拆分算法版本**，进 passage 契约 | 改拆窗/预算时改版本号并新建索引 |
| `evidence-contract-v2` | `data/evaluation/retrieval_baseline.json:3` | **评测标注/判定 revision**（schema_version=2），与向量无关；加载器只校验 `schema_version==2` 且 `judgment_revision` 非空（`evaluation/retrieval.py:65-77`），阶段脚本另行断言等于 `evidence-contract-v2`（`multilingual_baseline.py:118`） | 改标注/证据组语义时升 revision；不要写到索引契约里 |
| `dense_index_contract_id` | `config/rag-production.json` 每个 index 一项 | **索引身份哈希**（64 hex），把模型指纹 + passage 契约钉死 | 任何一侧变化都必须新集合/新索引，旧索引只读保留 |

### 4.4 `dense_index_contract_id` 的语义与计算

`DenseIndexContract`（`retrieval/index_contract.py:20-86`）字段：`requested_model_name`、`weights_manifest_sha256`、`model_config_sha256`、`encoding_config_sha256`、`tokenizer_sha256`、`query_template`、`document_prefix`、`dimension`、`max_seq_length`、`passage_contract_id`、`passage_algorithm`，以及固定默认 `normalize_embeddings=True`、`distance="cosine"`、`document_template='document_title + "\n" + passage.text'`。

$$
\text{dense\_index\_contract\_id} = \operatorname{SHA256}\!\left(\operatorname{JSON}_{\text{canonical}}\!\left(\operatorname{asdict}(\text{DenseIndexContract})\right)\right)
$$

- `JSON_canonical`：`sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False`（`index_contract.py:8-17`）。
- `encoding_config_sha256 = canonical_sha256(identity["config_files"])`（`index_contract.py:73`）——注意是对 `config_files` 映射再取一次 canonical 哈希，不是单个文件哈希。
- `passage_contract_id = SHA256(json.dumps(passage_contract, sort_keys=True))`（`index_contract.py:84-86`）——**默认分隔符**（含空格），与 `JSON_canonical` 不同算法，为了保留 `dense-passages-v1` 的历史身份。实测两者对同一对象给出不同摘要【实测，见 verification.md P6】。
- 路径、batch、线程、耗时**不参与**身份（`docs/runbooks/evidence-audit.md:40`），所以同模型换机器/换目录不会导致契约不符。

校验语义：索引中每个 point 的 payload 必须同时满足三个字段（`storage/qdrant_passages.py:33-58`）：

```text
payload.dense_index_contract_id == contract.contract_id       # 索引级
payload.contract_id              == contract.passage_contract_id  # passage 级
payload.payload_type             == "dense-passages-v1"       # owner/type
```

任一不符 → `ValueError("Dense index contract mismatch or unsigned payload; use a new collection or rebuild the full collection")`。**不要给未知索引补签、不要混用新旧 passage 策略**；同一 768 维但不同模型也必须失败。

实测（本机，用伪指纹实算，验证公式与敏感性）【实测】：

```text
canonical_sha256({b:1,a:[2,3]}) = 2aae3bfa906be39530e7d7a4aa90a7e6d4f29c33e3ac80e1c3b05598c5953c04
canonical_passage_id({algorithm,guard_tokens,overlap_tokens}) = 2be63c66d58f4edbdd919e8db9330a56ffd832a5c30243a339e781d308b2a4de
DenseIndexContract.from_fingerprint(伪指纹).contract_id = f8b3f058397307a14f6ed696055c2a517cd480d16c27c37bf2c2c794f6c4e5e0
  有 64 hex / 维度 768→1024 时 contract_id 变化
生产：E5 ccd4601d1698d3bff5b46589f11fc036e035ca57c1d8d179cd56b6b2d50e16f4（4746 points）
      Qwen3 6698d5531a29685c9a4002123d183e4cfa38f0e491fbeb3086448e2f0e6aa823（4532 points）
```

### 4.5 索引构建（GPU 主机，离线）

生产索引不是“运行时入库”的产物，而是**离线实验阶段冻结**后拷贝到 `/workspace/tmp/stage-two-eight/` 的签名目录。构建入口：`src/accelerator_rag/retrieval/multilingual_baseline.py`（Stage 2.8）。前置：

- 13 份 PDF 位于 `data/l0_raw`（即 `/workspace/data/l0_raw`）；
- 模型权重已下载到 `tmp/stage-two-eight/models/<org>--<name>`，且带 `weights-download-provenance.json` 与下载 receipt（脚本逐项校验，`multilingual_baseline.py:162-165`）；
- `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`，不联网、不下载。

```bash
# GPU 主机（会新建独立实验索引，不能指向生产路径）
cd /opt/accelerator-rag && \
OMP_NUM_THREADS=6 MKL_NUM_THREADS=6 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
PYTHONPATH=src python -m accelerator_rag.retrieval.multilingual_baseline
```

关键校验（脚本内断言，任一失败即停）：

```text
assert len(docs) == 13 and len(eligible) == 4532           # multilingual_baseline.py:117
assert judgment_revision == "evidence-contract-v2"         # :118
assert sources == history["metadata"]["source_sha256"]     # :122
assert parent_hash == history["metadata"]["canonical_parent_sha256"]  # :124
```

产物：`tmp/stage-two-eight/qwen3_embedding_0_6b_fp32/qdrant`（Qwen3）、`model-identity.json`（指纹 + passage 契约）、报告 `reports/rag-stage-two-eight-multilingual-retrieval.{json,md}`。E5 生产索引 `tmp/stage-two-eight/e5_reused_signed_index` 是 Stage 2.7 测量索引（`reports/rag-stage-two-seven-embedding-comparison.json` 记录的 `index_path`）的**逐点复制**（`scripts/stage28_multi_query.py:84-100,140-145` 的 clone 逻辑，复制后逐点比对 payload/vector 摘要），不重新编码。

**本机不能执行此步**：无 PDF、无模型、无 GPU、无 `/workspace`【实测】。

### 4.6 生产固化

1. 把验证过的实验索引目录复制到 `config/rag-production.json` 中 `index_path` 指定的位置（当前 `/workspace/tmp/stage-two-eight/…`）。
2. 用实算值更新 `dense_index_contract_id` 与 `point_count`；两者必须与目录内容一致，runtime 会逐个核对（第 5.2 节）。
3. 旧的索引目录**保留只读**，不要删除、不要原地覆盖。

### 4.7 校验点与失败处理

| 校验点 | 通过标准 |
| --- | --- |
| 模型顺序 | `config.indexes` 第 1 项必须是 E5、第 2 项必须是 Qwen3（`runtime.py:88-94`） |
| 契约 ID | 运行时算出的 `contract.contract_id` 与 config 值相等（`runtime.py:103-109`） |
| 目录存在 | `index_path/meta.json` 是文件（`runtime.py:111-113`） |
| 集合存在 | 本地 Qdrant 中 `collection` 存在（`runtime.py:117-118`） |
| 点数 | `store.point_count()` == config `point_count`（`runtime.py:131-132`） |
| 向量质量 | 写入时校验 `float32`、维度、有限值、非零范数（`qdrant_passages.py:114-128`） |

| 报错 | 处理 |
| --- | --- |
| `frozen dual-dense model order mismatch` | 不要调换 config 顺序；按 E5→Qwen3 恢复 |
| `model or passage contract differs from frozen index` | 模型/权重/tokenizer/passage 配置变了：恢复原模型，或新建索引并在新集合使用新 contract（禁止混合） |
| `existing local Qdrant index required` | 索引路径错误或被删：从备份恢复，绝不“顺手重建”到生产路径 |
| `existing signed collection required` | 集合名写错或索引目录不完整：核对 config 与备份 |
| `frozen index point count mismatch` | 索引被部分写入/删除：停止启动，按第 7.6 节回滚索引 |
| `Dense index contract mismatch or unsigned payload` | 索引混入旧/未签名数据：保留现场，恢复备份，禁止补签 |

---

## 5. 索引校验与启动核验

### 5.1 启动

在 **GPU 主机**执行（`docs/runbooks/rag-production.md:30-38`）：

```bash
RAG_ENV_FILE=/opt/rag-production.env bash /opt/accelerator-rag/deploy/rag-start.sh
curl -fsS http://127.0.0.1:8003/health
# 期望：{"status":"ok"}
```

`rag-start.sh` 的行为：若同名容器存在 → 校验 `/workspace` 挂载源必须等于 `$workspace` → `docker stop` + `docker rm` → `docker run` 新容器；只管理 `accelerator-rag` 这一个容器，不动模型服务与其它业务容器。首次加载要等模型与索引核验完成（健康检查 `--health-start-period=120s`）。

### 5.2 启动核验顺序（`RagRuntime.__init__`，`rag/runtime.py:61-162`）

| 步骤 | 检查 | 代码 |
| --- | --- | --- |
| 1 | 读 `config/rag-production.json`；解析模型地址/名字/凭据；地址 host 白名单 | `:65-83` |
| 2 | 双路按固定顺序加载：E5 → Qwen3 | `:88-94` |
| 3 | 用已加载模型算指纹 → `DenseIndexContract` → 与 config `dense_index_contract_id` 比对 | `:102-109` |
| 4 | `index_path/meta.json` 必须存在（拒绝空目录） | `:111-113` |
| 5 | 打开本地 Qdrant，集合必须已存在（runtime 不会为你建集合） | `:114-118` |
| 6 | `store.freeze_read_only()` → `verify_contract()` 全量扫描 payload 三字段 | `:119-120`、`qdrant_passages.py:28-58` |
| 7 | `all_passages()` 逐点重建 canonical 父块：point ID 必须匹配、跨索引同一 chunk 必须完全一致；只有 `.pdf` 来源进入 `documents`/`catalog` | `runtime.py:121-130`、`qdrant_passages.py:163-181` |
| 8 | 点数与 config 一致；构建 reranker、生成模型 provider、`RagService` | `:131-159` |
| 9 | （可选，`__main__`）`check_generation_service()` 校验 `/v1/models` 含配置模型名 | `:164-177` |

启动失败即 `resources.close()` 回滚已打开资源并退出（`:160-162`），不会半启动服务。

### 5.3 “只核验一次”与只读

- 启动阶段每个索引各有**两次完整读取**：一次契约扫描（`verify_contract()`，只取 payload 三字段做比对）+ 一次 canonical 父块重建（`all_passages()`，取全 payload，并校验 point ID 与跨索引一致性）。**契约校验只做一次**：`freeze_read_only()` 之后所有 `verify_contract()` 立即返回（`qdrant_passages.py:28-36`），不会因为每次查询重新扫描 4,746/4,532 个点。
- 只读后 `upsert_passages`、`prune_document` 直接抛 `ValueError("runtime index is immutable")`（`qdrant_passages.py:60-64,114-116`）。
- 运行期不重算向量、不重建 BM25（BM25 从已加载的规范父块在内存构建，`docs/architecture/rag-evidence-workflow.md:21`）。
- 启动日志里每个索引应恰好出现**一次契约核验**（不应反复契约扫描）；若观察到重复启动/反复扫描 → 有第二个进程或重复启动，按 5.4 处理。

### 5.4 单进程独占

本地 Qdrant 是嵌入式存储（`QdrantClient(path=...)`），**同一索引目录不能被两个进程同时持有**。运维纪律（`docs/runbooks/rag-production.md:40`）：

- 不要 `docker start` 已存在的容器再额外 `docker run` 一个；
- 不要在同一台机器上并行跑“生产容器 + 索引实验脚本”指向同一 `index_path`；
- 重建/实验一律用**新目录、新集合名**，不要指向生产路径。

判断是否重复：`docker ps --filter name=accelerator-rag` 只应有一个；`lsof`/`fuser` 查索引目录被谁打开（宿主视角）。

### 5.5 校验点（启动后，只读）

```bash
# 开发机（通过既有 SSH 转发）
curl --noproxy '*' -fsS http://127.0.0.1:18003/health
curl --noproxy '*' -sS http://127.0.0.1:18003/v1/rag/documents | head -c 200
```

判定标准：

| 检查 | 通过标准 | 依据 |
| --- | --- | --- |
| 健康 | HTTP 200，`{"status":"ok"}` | 【实测】2026-10-29 |
| 文档目录 | `document_count=13`、`indexed_section_count=4532` | 【实测】与 Qwen3 point_count 一致 |
| 逐文档 | 13 条均 `original_available: true`，`page_count` 合计 2178 | 【实测】 |
| 无静默降级 | 容器日志无 `contract mismatch`/`unsigned payload`/`point count mismatch` | `docker logs accelerator-rag`（需主机权限） |

### 5.6 失败处理（启动阶段）

| 现象 | 首查 | 处理 |
| --- | --- | --- |
| 容器不断重启 | `docker ps -a`、`docker logs accelerator-rag --tail 100` | 按日志报错对照 4.7；不要反复重启掩盖问题 |
| `existing signed collection required` | config `collection` 与索引目录 | 恢复备份或修 config；不要 `create_collection` |
| `model or passage contract differs` | 模型目录是否被替换/补下载 | 恢复原模型目录；确认 `model-identity.json` 指纹 |
| `point count mismatch` | 索引目录完整性（备份对比） | 停服务，按 7.6 恢复索引 |
| 模型 401 | 仓库外凭据与模型服务配置 | 修 `/opt/rag-production.env`（600）；**不要打印密钥** |
| 模型未就绪 | `curl http://127.0.0.1:8000/v1/models`（GPU 主机） | 等模型服务；不要据旧报告推断状态 |
| 健康检查超时 | 首次加载是否仍在进行（大模型 + 全量核验） | 等待；持续超时按上面逐项排查 |

---

## 6. 检索 / 回答验证

### 6.1 三层验证，状态标签 ≠ 正确性

| 层 | 回答什么问题 | 工具 | 不能证明什么 |
| --- | --- | --- | --- |
| 接口层 | 服务活着、请求能返回 200、响应结构合法 | `scripts/rag_framework_check.py`、`/health`、`/v1/rag/documents` | 不能证明内容对 |
| 证据层 | 选中的父块/引文是否完整包含冻结目标；引用 ID、版本、物理页是否真实 | `scripts/rag_framework_review.py` + `scripts/rag_framework_metrics.py` | 不能证明语义蕴含 |
| 语义层 | 结论是否被证据支持、是否答全 | 人工复核（`data/evaluation/README.md` 口径） | 不能外推为总体正确率 |

状态语义（`docs/architecture/rag-evidence-workflow.md:65-73`）：`answered` = 所有子需求被最终核查判定完整；`partial` = 仍有缺项但有已核查事实；`insufficient` = 没有可展示的已核查事实。`status` 是**模型自报**，`answered` 不等于正确（`reports/rag-framework-20261028.md` 的验收说明同此口径）。

### 6.2 接口回归：`rag_framework_check.py`

```bash
# 开发机（经 SSH 转发；也可以直接在 GPU 主机跑）
cd /home/whloong/projects/accelerator-rag-prab
python scripts/rag_framework_check.py \
  --base-url http://127.0.0.1:18003 \
  --output reports/rag-framework-http.json
```

参数与行为（`scripts/rag_framework_check.py`）：

- `--questions` 默认 `data/evaluation/retrieval_baseline.json`（21 可答 + 11 负例），再追加 4 道固定附加题（cryo 原问题/改写/缺项、XFEL 跨年份）；每题的标签只留在客户端，**实际请求只发送 `{"query": ...}`**。
- `--workers` 只允许 1–2（`:24-25`）；`--base-url` host 只允许 `localhost/127.0.0.1/10.101.9.190`（`:26-27`）。不允许指向其它主机。
- 每完成一题就重写 `--output`，中断也能保留部分结果（`:107-127`）。
- 每题记录 `http_status`、完整 `response`、`wall_seconds`；200 时计算 `status_consistent`（answered⇒所有 requirement supported；partial⇒有引用；insufficient⇒无引用）。
- `--trace-dir` 指向服务端 `trace_dir`（默认 `tmp/rag-request-traces`，容器内 `/workspace/tmp/rag-request-traces`，**只在 GPU 主机可见**）。给了才解析 trace，记录 `rounds`、`selected_round`、`calls`、`budgets_respected`（每轮 `context_tokens ≤ token_budget` 且 `len(selected_sources) ≤ max_sources`）、`supplemented`。

校验点：`http_errors == 0`、`client_errors == 0`；`status_consistent` 全为 true；给了 trace 时 `budgets_respected` 全为 true。**这些通过仍不代表答案正确。**

### 6.3 独立证据核对：`rag_framework_review.py`

```bash
# 必须在有原始语料的机器（GPU 主机）上、项目根执行
cd /opt/accelerator-rag && PYTHONPATH=src python scripts/rag_framework_review.py \
  --directory reports/rag-framework-20261028
```

前置：该目录下有 `http-results.json`、`request-traces.json.gz`；`data/l0_raw` 下原始 PDF 可用（脚本用 `pymupdf` 打开 registry 的 `source_path` 回查引文）。

检查项（`scripts/rag_framework_review.py`）：

1. 每题 `request_id` 存在、`trace.query == row.query`、`trace.response == response`（防“响应/记录不一致”）；
2. 每条引用的 `quote` 必须是所选 canonical 父块正文的逐字子串（`normalize_evidence` 归一化后比较），且 `page_start/page_end` 落在该 PDF 的真实页数范围内（脚本打开 PDF 只取页数，不比对 PDF 文字层）；
3. 引用的 chunk 必须是本次请求真实候选、版本与物理页匹配；
4. 冻结目标包含关系：所选父块 / 逐字引用分别覆盖了多少个 evidence group；
5. `invalid` 列表必须为空（不存在的证据 ID、无法核验的模型输出、把新事实写成完整等）。

本机实测【实测】：退出码 1，`pymupdf.FileNotFoundError: no such file: 'data/l0_raw/EPICS/EPICS_Documentation_latest.pdf'` → **该步骤只能在 GPU 主机做**。

### 6.4 召回指标：`rag_framework_metrics.py`

```bash
# 开发机可跑（只读已保存的 http-results + trace 归档，不碰 PDF/网络）
cd /home/whloong/projects/accelerator-rag-prab && PYTHONPATH=src python scripts/rag_framework_metrics.py
```

口径（`scripts/rag_framework_metrics.py`）：只统计 21 条可回答问题；`first_round` 的 Top-1/3/5/10/20 统计“证据组覆盖数”（micro/macro group recall）与“完整问题数”；另算 `selected_subset`、`quoted`、`all_round_candidates`；历史基线 `reports/rag-stage-two-eight-two-reranking.json` 同基准校验。Hit@K 与 MRR@5 定义见 `data/evaluation/README.md:15`：

$$
\text{Hit@}K = \frac{\#\{\text{可回答问题：Top-}K\text{ 至少命中一个接受证据}\}}{\#\text{可回答问题}},
\qquad
\text{MRR@}5 = \frac{1}{N}\sum_{i=1}^{N}\frac{1}{\text{first\_complete\_rank}_i}
$$

（深度外记 0；`all` 模式要求全部证据组；组内 OR、组间 AND。）

本机实测【实测】退出码 0，关键数字：`21` 题、`35` 个证据组；`first_round` 完整问题数 K=1/3/5/10/20 分别为 8/16/19/20/21（证据组 14/29/33/34/35）；`selected_subset` 与 `all_round_candidates` 均 35/35 组、21/21 题；`quoted` 30/35 组（micro 0.857、macro 0.838）、17/21 题；`mrr_first_relevant_at_5=0.7254`、`mrr_complete_at_5=0.5706`。全部标注 `diagnostic only`，且报告自注 `code_scope` 为“最终修复前的 36 题运行，不是最终代码的完整重跑”。

**坑**：`metrics.py` 的根目录写死为 `reports/rag-framework-20261028`（`root = Path("reports/rag-framework-20261028")`），并对 `data/evaluation/retrieval_baseline.json` 做相等断言。跑新一批回归时，要么把产物写回该目录（先备份旧文件），要么复制脚本改路径（属于代码变更，需评审）。不要用旧指标冒充新代码结果。

### 6.5 人工抽查（不可省）

1. 从响应中取 3–5 条 `citations`，逐条在 PDF 对应物理页核对 `quote`（用 `/v1/rag/documents/{doc_id}/view#page=N` 打开）。
2. 对“精确数值/版本边界/清单/接线表”类结论，逐一核对原文的**比较符与版本范围**；不同年份/版本分别标注口径。
3. 对 `insufficient`/`partial` 检查 `requirements[].missing` 是否说了真话；对 `answered` 至少抽 1 题验证没有“以完整自报掩盖缺项”。

```bash
# 开发机：单个文档的物理页查看（只读）
curl --noproxy '*' -fsS -o /tmp/x.pdf \
  http://127.0.0.1:18003/v1/rag/documents/shine-cryogenic-control-system-2021
# 浏览器打开（需 SSH 转发）：
#   http://127.0.0.1:18003/v1/rag/documents/shine-cryogenic-control-system-2021/view#page=6
```

### 6.6 判定标准（照抄证据闭环验收要求，按 RAG 入库场景裁剪）

- 接口层：0 HTTP 错误、0 客户端错误、`status_consistent` 全 true。
- 证据层：`invalid` 为空；`selected_parent_frozen_target_complete` 与 `quoted_frozen_target_complete` 分别记录，不得把前者当后者；预算（≤5 父块、≤6000 token/轮、≤2 轮、≤3 补检索）全程满足。
- 语义层：人工抽查通过；明确记录样本量、是否 holdout、哪些结论不可外推。
- **禁止**用单一指标（Hit@5、`answered` 比例）宣称质量提升；跨版本/跨环境结果不可直接比较。

### 6.7 失败处理

| 现象 | 首查 | 处理 |
| --- | --- | --- |
| 502 / 模型输出无法核验 | 服务端 trace（`request_id`）、模型服务健康 | 按 5.6；不要重试掩盖 |
| 引用 404 | 文档是否登记、`data/l0_raw` 原文件是否完整 | 修复语料；不要改引用路径 |
| 大量 `insufficient` | 索引是否加载（5.5）、负例判定 | 先确认 catalog/点数，再按第 6.3 节核对 |
| `review` 报 invalid | 引文是否真是所选父块的逐字子串、物理页范围是否越界、预算/冲突是否被违反 | 停用该结论；修复后重跑，不改判定口径 |
| `metrics` 断言失败 | 基准文件被改/报告缺失 | 恢复 `data/evaluation/retrieval_baseline.json`；不要放宽断言 |

---

## 7. 回滚

### 7.1 回滚对象与优先级

| 对象 | 位置 | 是否影响服务 | 回滚优先级 |
| --- | --- | --- | --- |
| 运行时源码（11 个 `rag/*.py`） | `/opt/accelerator-rag/src/accelerator_rag/rag/` | 是（重启生效） | 高 |
| 运行配置 `config/rag-production.json` | `/opt/accelerator-rag/config/` | 是（重启生效） | 高 |
| 依赖清单 `deploy/rag-requirements.txt` | 同左 | 是（换镜像才生效） | 中 |
| 文档（2 份） | `/opt/accelerator-rag/docs/` | 否 | 低 |
| 本地 Qdrant 索引 | `/opt/accelerator-rag/tmp/stage-two-eight/…` | 是（启动核验） | 高（仅索引损坏时） |
| 模型权重 | `/opt/accelerator-rag/tmp/stage-two-eight/models/` | 是（指纹校验） | 高（仅模型被替换时） |
| 请求 trace | `/opt/accelerator-rag/tmp/rag-request-traces/` | 否（仅保留最近 100 份） | 低 |

### 7.2 备份位置与清单

原始备份在 GPU 主机：`/opt/accelerator-rag/tmp/rag-framework-backup-20261028`，内含 `manifest.json`；后续修订各自保留专用备份与部署哈希清单（`reports/rag-framework-20261028.md:109`、【仓库记录】）。

```bash
# GPU 主机：先看清备份，再动手（只读）
ls -la /opt/accelerator-rag/tmp/rag-framework-backup-20261028/
cat /opt/accelerator-rag/tmp/rag-framework-backup-20261028/manifest.json
```

manifest 至少应给出“文件相对路径 + SHA-256”。若字段名不同，先在纸上核对含义，**不要**写脚本猜格式。仓库内的 `deployment-verification.json` 可作为**期望哈希的交叉参考**（15 个文件），但它不是备份清单本身。

【未验证】本机无法读取该备份内容（无 GPU 主机登录权限）。执行回滚前，必须先完成 7.3 的 manifest 核对；若备份缺失或 manifest 不全，**停止回滚**，按 7.8 上报。

### 7.3 回滚前检查（不通过就不回滚）

1. **备份完整性**：manifest 中每个文件存在、`sha256sum` 与 manifest 一致；不一致的文件不得用于恢复。
2. **当前状态快照**：记录 `git rev-parse HEAD`、当前 15 个文件的哈希（比对 `deployment-verification.json`）、`docker inspect accelerator-rag` 的镜像/挂载/创建时间。
3. **范围确认**：本次回滚只动第 7.1 节列出的文件；**不重建、不覆盖索引**（索引回滚另有 7.6）。
4. **变更记录**：把“为什么回滚、回滚到哪个备份、责任人、时间窗”写进操作记录（谁执行谁记录）。

```bash
# GPU 主机：当前状态快照
cd /opt/accelerator-rag && git rev-parse HEAD 2>/dev/null || echo "not a git checkout"
docker inspect accelerator-rag --format '{{.Created}} {{.Config.Image}} {{range .Mounts}}{{.Source}}->{{.Destination}}:{{.RW}} {{end}}'
sha256sum config/rag-production.json deploy/rag-requirements.txt
```

### 7.4 逐文件恢复 + 重启（手工，逐步执行）

```bash
# GPU 主机，root 或有写权限的账号；示例以备份目录变量化
BK=/opt/accelerator-rag/tmp/rag-framework-backup-20261028
cd /opt/accelerator-rag

# 1) 逐文件恢复（不要整目录 cp -r：会覆盖 tmp/ 索引与 traces）
#    下面的路径列表必须来自 manifest，不要手抄
for rel in src/accelerator_rag/rag/__init__.py src/accelerator_rag/rag/context.py \
           src/accelerator_rag/rag/retrieval.py src/accelerator_rag/rag/service.py \
           src/accelerator_rag/rag/workflow.py src/accelerator_rag/rag/catalog.py \
           src/accelerator_rag/rag/evidence.py src/accelerator_rag/rag/__main__.py \
           src/accelerator_rag/rag/api.py src/accelerator_rag/rag/answer.py \
           src/accelerator_rag/rag/runtime.py config/rag-production.json \
           deploy/rag-requirements.txt docs/architecture/rag-evidence-workflow.md \
           docs/runbooks/rag-production.md; do
  test -f "$BK/$rel" || { echo "MISSING $rel"; exit 1; }
  cp -p "$BK/$rel" "$rel"
done

# 2) 逐文件核对哈希（用 manifest 或 deployment-verification.json 的 expected 值）
sha256sum src/accelerator_rag/rag/*.py config/rag-production.json deploy/rag-requirements.txt
```

重启（只重启独立 RAG 容器，不动模型服务与其它业务容器）：

```bash
RAG_ENV_FILE=/opt/rag-production.env bash /opt/accelerator-rag/deploy/rag-start.sh
curl -fsS http://127.0.0.1:8003/health
```

注意：`rag-start.sh` 会 `docker stop` + `docker rm` + `docker run`，**有短暂服务中断**；若容器名被改过，脚本只按名字 `accelerator-rag` 管理，需要先人工确认。

### 7.5 回滚后验证（缺一不可）

```bash
# 开发机（经转发）
curl --noproxy '*' -fsS http://127.0.0.1:18003/health
curl --noproxy '*' -sS http://127.0.0.1:18003/v1/rag/documents \
  | python -c "import json,sys; d=json.load(sys.stdin); print(d['document_count'], d['indexed_section_count'])"
# 期望：13 4532
```

```bash
# 开发机：重新比对 15 个部署文件哈希（脚本见 1.4 节），期望 14/15 或 15/15
# 若恢复到了部署快照，rag-production.md 会变成 90f617bf…（与仓库当前 HEAD 的 7588fae2… 不同）——这是预期的。
```

```bash
# 定向回归（6 题，避免跑全量 36 题）
# 说明：check 脚本固定追加 4 道附加题（cryo-original / cryo-paraphrase /
# cryo-missing-details / xfel-version-scopes，见 rag_framework_check.py:33-50），
# 所以子集文件只需给 2 条冻结基准题，合计 6 题。
cd /home/whloong/projects/accelerator-rag-prab
python - <<'PY'
import json
ids = {"xfel-normal-energy", "no-answer-hard-live-beam-energy"}   # 基准内真实存在的 2 条
q = json.load(open("data/evaluation/retrieval_baseline.json"))["queries"]
keep = [{"id": x["id"], "query": x["query"], "answerable": x["answerable"]} for x in q if x["id"] in ids]
assert len(keep) == 2, [x["id"] for x in q]
json.dump({"queries": keep}, open("/tmp/rollback-subset.json", "w"), ensure_ascii=False, indent=2)
print(len(keep))          # 2；脚本再追加 4 题 = 6
PY
python scripts/rag_framework_check.py --base-url http://127.0.0.1:18003 \
  --questions /tmp/rollback-subset.json --output /tmp/rollback-check.json
```

判定：health 200、catalog 13/4532、6 题 HTTP 全 200、`status_consistent` 全 true、抽查引用可回到原 PDF。若任一失败 → 保留现场（不要二次重启），按 7.8 上报。

### 7.6 索引回滚（仅在索引损坏/被误写时）

1. 停容器：`docker stop accelerator-rag`（**不要** `docker rm` 之前先看清挂载）。
2. 备份当前损坏索引目录到 `tmp/incident-<日期>-<简述>/`（保留证据，禁止删除）。
3. 从备份恢复 `tmp/stage-two-eight/<index>` 整个目录，**不要在恢复中改 payload、不要补签**。
4. 核对 `meta.json`、`model-identity.json`、collection 名、`point_count` 与 `config/rag-production.json` 一致。
5. 按 7.4 重启，观察启动核验是否通过（第 5.2 节），再做 7.5 验证。

重建索引不是回滚：需要 13 份 PDF + 模型权重，走第 4.5 节，且会得到新的 `contract_id`/点位数，必须同步 config 并重新验证。**未经项目负责人裁决不得重建生产索引。**

### 7.7 未实现：自动回滚（与手工流程分开标注）

现状：仓库内没有回滚脚本（`deploy/` 只有 `rag-start.sh`、`rag-requirements.txt`、systemd tunnel 单元），没有备份脚本，没有自动 manifest 生成/校验工具。当前所有回滚动作都是**手工 + 人工核对**。

最小改造方案（若要实现，建议范围）：

1. `deploy/rag-backup.sh <tag>`：按固定文件清单（与 `deployment-verification.json` 同一份列表）生成 `manifest.json`（path+sha256），复制到 `tmp/<tag>-backup/`；
2. `deploy/rag-restore.sh <tag> --dry-run|--apply`：`--dry-run` 只校验 manifest，`--apply` 逐文件恢复并输出哈希对照；
3. `deploy/rag-verify.sh`：重算 15 文件哈希 + `/health` + `/v1/rag/documents`（13/4532），输出 PASS/FAIL；
4. 评审约束：备份与恢复脚本本身必须可 dry-run，禁止默认重启容器（仓库当前没有 CI 配置，靠流程约束）。

以上属于新功能，需要裁决（谁维护、是否允许脚本动容器、备份保留策略）。**在本节落地前，不要对外宣称“支持一键回滚”。**

### 7.8 回滚边界与风险

- 本机无 GPU 主机登录权限 → 无法远程执行回滚；必须由具备权限的运维在场。
- 备份内容本次未核验（7.2）→ 回滚前必须核对 manifest，否则可能恢复出更坏的版本。
- 重启有中断（秒级到模型加载分钟级）；模型服务、其它容器、索引本身不在回滚动作内。
- `docs/runbooks/rag-production.md` 的部署态内容（`90f617bf…`）不在 git 历史中；回滚后它与仓库 HEAD 不一致属于预期，**应记录而不是立即再改**。
- 回滚不修复数据问题：如果坏的是语料/索引内容，代码回滚不会让答案变对，需按 7.6 或重新入库处理。

---

## 8. 已知边界与限制

### 8.1 环境边界

| 事实 | 影响 |
| --- | --- |
| 本机没有 `data/l0_raw` | 无法做语料对账、解析、切块、资格、审计、`review`（第 2–3、6.3 节只能在 GPU 主机做） |
| 本机没有 `tmp/`（模型与索引） | 无法复算 `dense_index_contract_id`、无法跑 dense/passage 构建 |
| conda editable 指向兄弟目录 | 不加 `PYTHONPATH=src` 会测到另一份代码（1.5 节） |
| 只有到 `8003` 的端口转发 | 能只读查询生产接口，不能执行服务器运维（第 5、7 节） |
| 生产索引是**冻结的签名索引** | “入库”实际是“离线构建新索引 + 换 config + 重启”，不存在运行期增量入库路径（`docs/runbooks/knowledge-retrieval.md:112` 亦声明未实现增量 ingestion） |

### 8.2 未实现能力清单（与已实现流程分开）

| 能力 | 状态 | 证据 |
| --- | --- | --- |
| Markdown 解析入库 | **已实现（工作区），生产未部署** | 第 8.3 节；`corpus/markdown_parser.py` |
| TXT / HTML / DOCX / PPTX 解析 | 未实现（`registry` 可登记，`IngestionService` 显式拒绝） | `ingestion.py` `SUPPORTED_INGESTION_TYPES` |
| PPTX / DOCX 解析 | 未实现 | `ingestion.py:55-56`；未登记的非 PDF 只报 unmanaged（`registry.py:181-185`） |
| OCR / 扫描件 | 未实现 | 只有 `possible_scanned_page` 告警（`pdf_parser.py:140-141`） |
| 公式/表格结构识别 | 未实现；U+FFFD 原样保留 | `docs/runbooks/corpus-baseline.md:52` |
| 增量 ingestion / 单文档热更新 | 未实现 | 生产索引只读（`qdrant_passages.py:28-31`） |
| 完整索引 manifest 校验工具 | 未实现 | `docs/runbooks/knowledge-retrieval.md:112`；回滚清单靠部署记录（7.2） |
| 自动备份 / 自动回滚 | 未实现 | 7.7 |
| 混合检索（Hybrid）默认路径 / 分数阈值 | 未实现 | `knowledge-retrieval.md:91-95,112` |
| Markdown 页码视图 | 未实现（用纯文本回退） | `/view` 对非 PDF 返回 `text/plain`（`api.py:54-66`）；PDF.js 不适用 |

### 8.3 Markdown 入库：已实现（工作区代码），生产尚未部署

**状态（2026-10-29 14:40 更新）**：采用 8.3.1 里的**方案 A**，代码已实现并跑通本地全链路
（登记 → 解析 → 切块 → 资格 → 干跑报告）；**生产实例仍是纯 PDF 语料**，Markdown 尚未进索引，
也**未部署、未重启**。所以 `docs/waveform/*.md` 现在的状态是“已保存、可解析、可切块、（在 GPU
主机上）可入库”，**不是“生产可检索”**。

| 环节 | 实现 | 位置 |
| --- | --- | --- |
| 解析 | `parse_markdown`：front-matter 原样保留为证据、按标题级别切节、代码围栏内不切 | `corpus/markdown_parser.py` |
| 切块 | `chunk_markdown`，算法标签 `md-chunks-v1`；PDF 仍 `pdf-chunks-v3` | `corpus/chunking.py` |
| 入库 | `IngestionService` 支持 `pdf`+`md`；`ingest_all_registered()` 遍历受支持类型；`ingest_all_registered_pdfs()` 保持 PDF-only 以复现冻结基线 | `ingestion.py` |
| 语料快照 | 把 `docs/<sub>/*.md` 复制到 `data/l0_raw/<sub>/`，记录双向 sha256；`--check` 查漂移 | `scripts/snapshot_markdown_docs.py` |
| 登记 | 独立 `data/documents/registry-md.json`（**不动**冻结的 `registry.json`，13 份 PDF 基线不变） | 同路径 |
| 干跑 | 4 份文档 → 40 节 → 151 chunks，全部 eligible | `scripts/md_corpus_report.py` |
| 建索引 | `--dry-run` 本地可跑；`--apply` 需 GPU 主机与索引目录 | `scripts/build_markdown_index.py` |
| 服务 | catalog 增 `document_format`，md 不读 PDF 页数；`/documents` 返回 `text/markdown`；`/view` 对非 PDF 返回纯文本 | `rag/catalog.py`、`rag/runtime.py:126-133`、`rag/api.py:54-84` |
| 测试 | `tests/corpus/test_markdown_ingestion.py` 7 项；全套 269 项通过 | — |

**必须记住的语义约定**

- Markdown 的 `page_start` / `page_end` 是 **1-based 章节序号**，不是 PDF 物理页；前端“物理页”标注对它不适用。
- `dense_index_contract_id` **不因加文档而改变**（只依赖模型 + passage 契约），但两个 collection 的
  `point_count` 会变 → `config/rag-production.json` 必须同步，否则启动核验失败。
- 旧 PDF 的 `chunk_id` 逐字节不变：`CHUNKING_ALGORITHM` 仍是 `pdf-chunks-v3`，md 用独立标签，
  所以**不需要重建 PDF 索引**（这点与 8.3.1 方案 A 的版本策略 a 一致）。

**生产入库仍需执行（需授权，本次未做）**

1. GPU 主机备份两个索引目录与 `config/rag-production.json`；
2. `python scripts/snapshot_markdown_docs.py`（在 GPU 主机同一工作区）；
3. `python scripts/md_corpus_report.py --output tmp/md-ingestion-report.json`；
4. `python scripts/build_markdown_index.py --apply --config config/rag-production.json`（逐文档 `index_document`）；
5. 用第 4 步打印的 `points_after` 更新 config 的 `point_count`；`dense_index_contract_id` 必须保持不变；
6. 重启独立 RAG 容器 → `/health` → `/v1/rag/documents` 应为 **17 份**（13 PDF + 4 md）→ 定向问一个
   md 内容问题，核对引用能打开原始 md；
7. 失败则按第 7 节回滚（逐文件恢复 + 重启 + 6 题定向回归）。

**未验证**：`--apply` 未在 GPU 主机执行；索引未重建；生产未重启；md 引用的前端页码语义（章节号）
尚未在 UI 上标注。

#### 8.3.1（历史记录）实现前的阻塞分析

以下是实现前（2026-10-29 13:12–13:30）的核验结论，保留作为变更依据。其中的“结论：阻塞”指当时状态，
现在只对 TXT/HTML/DOCX 成立。当时的状态以核验时刻为准：本手册开始核验时工作区没有 `docs/waveform/`；
成稿前（13:22/13:28）并行任务已创建 2 份 Markdown。当时存在**两个彼此独立的阻塞点**：

- 阻塞点 1（位置）：`source_path` 必须位于 `data/l0_raw/` 下（`registry.py:76-77`），`docs/waveform/*.md` 原地登记直接被拒（实测：`source_path 必须位于 data/l0_raw 下`）；必须先复制到 `data/l0_raw/waveform/`。
- 阻塞点 2（格式）：即使复制并登记成功，也只会到达“登记合法”，随后被 `IngestionService` 拒绝（见下）。

**代码级证据**（完整表格见 `reports/phase1-m0-20261029/ingestion-path/verification.md` 第 4 节）：

1. `registry.py:12` 允许 `document_type` 取 `md`，`topic=waveform` 也已存在 → **登记层放行**，容易误判“已支持”；但 `docs/waveform/*.md` 的原地登记仍被路径规则拒绝（见上）。
2. `ingestion.py:55-56`：`if record.document_type != "pdf": raise ValueError("only PDF ingestion is supported")` → 单文档入口**显式拒绝**。
3. `ingestion.py:59-65`：批量入口按 `document_type == "pdf"` 过滤 → Markdown **静默返回 0 个 chunk**，不报错（更危险）。
4. `pdf_parser.py:192-193`：`if pdf_path.suffix.lower() != ".pdf": raise ValueError("Expected a PDF file")`；全仓库**只有**这个文件能构造 `ParsedPdfDocument`（已扫描 `src/`）。
5. `cleaning.py:127`：`b.bbox[1] / page.height` → 自造适配器若给出 `height=0` 的合成页，会 `ZeroDivisionError`（实测）。
6. `runtime.py:126-130`：即使索引里有 Markdown chunk，`source.suffix == ".pdf"` 之外不进 `documents`/`catalog` → `/v1/rag/documents` 不展示、PDF 查看器打不开。

**实测（本机，隔离在报告目录内）**：用 162 字节的最小 Markdown 建临时项目根 + 临时 registry，`IngestionService.ingest_document()` 抛 `ValueError: only PDF ingestion is supported`；`ingest_all_registered_pdfs()` 返回 `0` 个文档、0 个 chunk、无异常；`parse_pdf(<.md>)` 抛 `Expected a PDF file`。绕过解析器手工构造带 `PdfTextBlock` 的 `ParsedPdfDocument` 后，`chunk_pdf` 能切出 1 个 chunk（`chunk_id` 前缀仍是 `pdf-chunks-v3`）——证明**缺的是一个解析适配器 + 几个白名单/版本决策，而不是整条链路不支持文本**。

**最小改造方案（两条路，必须二选一裁决）**

- **方案 B（零代码，最省）**：在 GPU 主机把 `docs/waveform/*.md` 离线导出为 PDF（pandoc/其他已装工具），走现有 PDF 入库流程。优点：0 行 `src/` 变更、复用全部校验；缺点：多一道手工步骤、版面/页码是合成值、Markdown 更新要重新导出、diff 噪声大。适配“文档数量少、更新不频繁”的现状。
- **方案 A（代码适配器，需评审）**：
  1. 新增 `src/accelerator_rag/corpus/markdown_parser.py`：`parse_markdown(path, *, source_path) -> ParsedPdfDocument`，按标题分页（每 H1/二级标题一页或整文件一页），每段一个 `PdfTextBlock`，给**非零合成** `page.width/height`（如 612×792）与递增 `bbox`，避免 `cleaning.py:127` 除零和页边误删；
  2. 把 `IngestionService` 的硬编码改成“`document_type` → 解析器”映射，批量入口按映射遍历；保留 PDF 行为不变；
  3. 版本语义二选一并写入评审结论：a) 新增 `markdown-chunks-v1` 只用于 md（PDF 的 chunk ID 不变）；b) 统一升 `CHUNKING_ALGORITHM`（PDF chunk ID 全变 → 4532 父块需重新嵌入、双路索引重建，成本最高）。推荐 a；
  4. `rag/runtime.py` 的 catalog 分支允许注册的 Markdown 来源（`original_available` 语义要重新定义），并为 `api.py` 增加文本/预览端点（前端 PDF.js 分支不能直接打开 md）；
  5. 补测试：md 解析/切块/入库、混合格式目录、`cleaning` 边界（标题页、代码块、表格、参考文献段落）。
  6. 仍需重建索引（新文档 = 新语料），并同步 `multilingual_baseline.py:117` 的 `13 / 4532` 硬断言与契约/点数。

**必须裁决的问题（写给项目负责人）**

1. 走方案 A 还是方案 B？（默认建议 B，除非 Waveform 文档需要频繁更新/结构化引用）
2. 若走 A：`chunk_id` 版本策略选 a 还是 b？是否接受 PDF 索引重建窗口？
3. 生产索引重建需要 GPU 主机时间窗与回滚预案，由谁排期、谁授权？
4. Markdown 文档的引用展示形态（物理“页”语义是合成的，引用页码如何标注）？
5. 这些文档是否属于生产语料（影响答案口径）还是仅内部知识？（影响是否必须进同一索引）

**在此之前，任何“Waveform 文档已入库/已可检索”的说法都不成立。**

### 8.4 与 `alignment_algo_hash` 的关系

本手册不适用该字段，原因：RAG 入库路径只处理语料（PDF/Markdown）、切块、向量与证据判定，不计算也不消费 Waveform 对齐算法；语料内容里如果提到对齐算法，也只是普通文本。当前 `docs/waveform/alignment-semantics-and-diagnostics.md` 自己带有 `alignment_algo_hash: "未定义（系统未实现，见正文“字段来源说明”）"`，那是**Waveform 文档的字段**，与本手册（RAG 入库手册）无关；一旦该文档入库，应按下面规则与本手册重新绑定。

未来触发绑定的条件（写清楚，避免“以后再说”）：当 Waveform 文档要**作为算法实现的权威说明**进入 RAG，且回答需要按算法版本区分正确性时，必须：

1. 在 `registry.json` 增加（或约定 front-matter 携带）该文档对应的 `alignment_algo_hash`，并在入库时校验非空；
2. 将该哈希写入审计报告与引用元数据，回答时按哈希区分版本，不同哈希的结论不得混写；
3. 更新本手册与 `applicable_system_version` 的绑定关系（届时该字段不再写“不适用”）。

### 8.5 变更记录

| 日期 | 变更 | 依据 |
| --- | --- | --- |
| 2026-10-29 | 初稿：登记→解析→切块→嵌入→索引契约→启动核验→HTTP 验证→回滚；记录 Markdown 入库阻塞与实测证据 | 本机实测 + 仓库记录；证据见 `reports/phase1-m0-20261029/ingestion-path/verification.md` |
