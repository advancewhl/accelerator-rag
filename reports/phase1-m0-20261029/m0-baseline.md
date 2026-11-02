# M0 系统基线冻结记录（2026-10-29）

本记录冻结 Phase 1 的评测对象与配置事实。冻结动作**只新建本目录下的文件**，没有修改、清理、提交或部署任何既有内容。所有结论均标注了可复核的证据位置；未能复核的项目在“限制与缺口”中列出，不填补。

## 1. 冻结对象定义

**M0 = 以下四项的集合**：

1. **代码**：Git 提交 `0b62844`（branch `whloong/rag-prab-constraint-grounded`，worktree `/home/whloong/projects/accelerator-rag-prab`）中的 14 个运行文件（`src/accelerator_rag/rag/*`、`config/rag-production.json`、`scripts/rag_framework_*.py` 等，见部署清单）。
2. **运行实例**：GPU 主机 `10.101.9.190:8003` 上的独立 `accelerator-rag` 容器，经本机 systemd 隧道 `127.0.0.1:18003` 访问。
3. **知识快照**：13 份 PDF / 2178 物理页 / 4537 规范父块（4532 eligible），`pdf-chunks-v3` + `evidence-contract-v2`。
4. **模型**：生成 `ds-1017`；嵌入 E5 + Qwen3-Embedding-0.6B；重排 Qwen3-Reranker-0.6B。

## 2. Git 状态

| 项 | 值 | 证据 |
| --- | --- | --- |
| 工作区 | `/home/whloong/projects/accelerator-rag-prab` | `pwd` |
| 仓库形式 | `git worktree`，主检出 `/home/whloong/projects/accelerator-rag` | `.git` 内容为 `gitdir: .../worktrees/accelerator-rag-prab` |
| 分支 | `whloong/rag-prab-constraint-grounded` | `git rev-parse --abbrev-ref HEAD` |
| HEAD | `0b628447c2a50a848d7f5ce7f6b74d5e46fe57cd`（2026-10-28 15:59:06 +0800） | `git rev-parse HEAD` / `git show -s` |
| 同名提交分支 | `whloong/agent-platform` 亦指向 `0b62844` | `git branch -a` |
| 远端 | `origin/whloong/agent-platform` 同 `0b62844`；**未 push 本分支** | `git branch -a` |

**未提交改动（冻结时原样保留，未清理）**：9 个修改（README.md、docs/architecture/README.md、docs/decisions/*.md、docs/rag/README.md、docs/roadmap/CURRENT.md、papers/*/README.md）、1 个删除（`docs/AGENT_MASTER_PLAN.md`）、2 个未跟踪（`PRAB_PLAN.md`、本报告目录）。

**关键判定：`src/` 与 `config/` 无未提交改动** —— 即工作区运行代码与该提交一致（`git status --porcelain src config` 为空）。

## 3. 实际运行代码与工作区代码的一致性

可用证据链（逐条列出，不合并表述）：

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 2026-10-28 部署时的三方哈希 | 15 个文件的 expected / local / remote SHA-256 **全部相等**，`matches=true` | `reports/rag-framework-20261028/deployment-verification.json` |
| 今日重算工作区哈希 vs 部署记录 | **14/15 一致**；唯一不一致为 `docs/runbooks/rag-production.md`（部署时 `90f617bf…`，现 `7588fae2…`） | 本次复核脚本，见 §7 |
| 该文档差异的解释 | 部署后被编辑并在 `0b62844` 中提交，服务器上的副本未随之更新；属**文档副本滞后**，不影响运行代码 | `git log --all -- docs/runbooks/rag-production.md` 仅有 `0b62844`；`git show HEAD:…md` 哈希 = 当前工作区哈希 |
| 部署后代码是否再变 | `src/`、`config/` 无未提交改动，且无新提交 → 运行代码文件自部署后未变 | `git status --porcelain`、`git log` |
| 远程字节可否重新核验 | **否**。本机无法 SSH 登录 `10.101.9.190`（`Permission denied (publickey)`）；跳板 `waveform-zyf-oneclick` 上无 `docker` 命令 | 本次 `ssh`/`docker` 探测输出，见 §7 |
| 行为探测 | `/health` 返回 `{"status":"ok"}`；36 题回归中跨年份版本题（`xfel-version-scopes`）与低温缺项题（`cryo-missing-details`）表现与 2026-10-28 修复后记录一致 | `reports/phase1-m0-20261029/regression-36-http.json` |

**结论（分级表述）**：

- 已证实：工作区 14 个运行文件与部署记录逐字节一致，且部署后未再改动 → **工作区代码 = 2026-10-28 部署代码**。
- 已证实：服务器当前实例在行为上具备修复后特征（版本分口径、缺项诚实）。
- 待核实：服务器上这 14 个文件的**当前字节**未重新读取（无权限），只能依据 2026-10-28 记录 + 行为一致推断未被替换。
- 已证实：服务器上的 `docs/runbooks/rag-production.md` 是部署时旧版（相对工作区落后一版）。

## 4. 模型与配置

来源：`config/rag-production.json`（哈希 `ba35ed18…`，三方一致）。

| 角色 | 模型 / 路径 | 关键参数 |
| --- | --- | --- |
| 生成 | `ds-1017`，`http://127.0.0.1:8000/v1` | `generation_max_tokens=4096`（上限 4096，`rag/runtime.py:27-29`） |
| 嵌入 1 | `intfloat/multilingual-e5-base` | collection `knowledge_stage27_intfloat__multilingual_e5_base`，4746 points，contract `ccd4601d…`，cuda:0 float32 |
| 嵌入 2 | `Qwen/Qwen3-Embedding-0.6B` | collection `knowledge_stage28_qwen3_embedding_0_6b_fp32`，4532 points，contract `6698d553…`，cuda:0 float32 |
| 重排 | `Qwen/Qwen3-Reranker-0.6B` | cuda:0，dtype auto，batch_size 4 |
| 语料根 | `/workspace/data/l0_raw`（GPU 主机） | 本机**不存在**该目录 |
| 请求记录 | `tmp/rag-request-traces` | 权限 600，仅保留最近 100 份（`rag/service.py:104-122`） |

注意：双路嵌入的 point_count 不同（4746 vs 4532）——E5 索引来自 Stage 2.7 复用签名索引，Qwen3 索引是 Stage 2.8 的 4532 eligible 父块。两者**不是同一索引规模**，不可互相替代比较。

## 5. 语料、索引与检索预算

| 项 | 值 | 证据 |
| --- | --- | --- |
| 登记语料 | 13 份，`document_type` 全为 `pdf`；11 `reference` + 2 `active` | `data/documents/registry.json` |
| 语料规模 | 2178 物理页、4537 规范父块、4532 eligible | `docs/roadmap/CURRENT.md:43` |
| 解析契约 | `pdf-chunks-v3` | 同上 |
| 证据契约 | `evidence-contract-v2` | 同上；`data/evaluation/retrieval_baseline.json:judgment_revision` |
| 冻结评测基线 | 32 题（21 可答 + 11 负例），SHA-256 `f5578371bca4589e8b2011ac4fbea2c17dbef57ab24b811f9247d92954f3ac65` | 本次计算，见 §7 |
| 检索轮数 | `max_rounds=2` | `rag/workflow.py:68` |
| 候选父块 | 每轮最多 20 | `rag/workflow.py:93-96` |
| 候选上下文上限 | 18000 tokens（超出则逐条裁剪，仍超则报错） | `rag/workflow.py:98-104` |
| 最终证据预算 | `token_budget=6000`，`max_sources=5` | `rag/workflow.py:69`、`rag/evidence.py:11`；server 配置未覆盖 |
| 子需求数 | 1–6 | `rag/answer.py:34` |
| 补检索查询 | 每次最多 3 条 | `rag/workflow.py:29` |
| 请求长度 | 1–8000 字符 | `rag/api.py:18`、`rag/service.py:37-38` |
| 并发 | 服务端 GPU 检索加锁串行；HTTP 测试工作线程 1–2 | `rag/service.py:34`、`scripts/rag_framework_check.py:26-27` |

`max_sources` 在 `EvidenceContextBuilder` 默认 5、在 workflow 中显式用 20 构建候选上下文——两者不是同一预算：**20 是候选池，5 是最终证据**。

## 6. 运行环境与回归命令

| 项 | 值 |
| --- | --- |
| 本机 Python | `/home/whloong/miniconda3/envs/accelerator-rag/bin/python`，3.11.15，httpx 0.28.1，pytest 8.4.2 |
| 服务入口 | `http://127.0.0.1:18003`（systemd user 单元 `accelerator-rag-tunnel.service`，2026-10-28 14:46 启动，冻结时运行 22h） |
| 远端服务 | `http://10.101.9.190:8003/`，容器 `accelerator-rag`，镜像 `accelerator-rag-runtime:20261026`（据运行手册，未独立核验） |
| 健康检查 | `curl --noproxy '*' -fsS http://127.0.0.1:18003/health` → `{"status":"ok"}`（2026-10-29 13:09） |

本次 36 题回归命令（实际执行）：

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/rag_framework_check.py \
  --base-url http://127.0.0.1:18003 \
  --output reports/phase1-m0-20261029/regression-36-http.json \
  --workers 2
```

题面集合 = `data/evaluation/retrieval_baseline.json` 的 32 题 + 脚本内 4 道附加题（`cryo-original`、`cryo-paraphrase`、`cryo-missing-details`、`xfel-version-scopes`），共 36 题。请求只发送 `query`，标签留在客户端。

**复现坑（必须记录）**：conda 环境 `accelerator-rag` 是 editable 安装，`import accelerator_rag` 默认解析到兄弟 checkout `/home/whloong/projects/accelerator-rag/src`，**不是本工作区**。复现本目录的脚本时必须加 `PYTHONPATH=src` 或在脚本内显式插入 `src`（`analyze_regression.py` 已这样做）。`scripts/rag_framework_check.py` 只依赖 httpx，不受影响。两个 checkout 中与 RAG 入库/检索相关的 10 个文件经逐字节比对相同（证据：`reports/phase1-m0-20261029/ingestion-path/verification.md` §1）。

**限制**：本次运行**没有** `--trace-dir`，因为 trace 目录在 GPU 主机 `/opt/accelerator-rag/tmp/rag-request-traces` 上，本机无访问权限。因此本次 36 题可以做状态/引用/耗时分析，**不能**做轮次、子集预算、补检索的内部过程分析；后者只存在于 2026-10-28 的历史归档（`reports/rag-framework-20261028/request-traces.json.gz`）。

## 7. 本次复核执行的命令（可复现）

```bash
# 哈希与部署一致
python3 - <<'EOF'
import json, hashlib
m = json.load(open('reports/rag-framework-20261028/deployment-verification.json'))
bad = [(e['path'], hashlib.sha256(open(e['path'],'rb').read()).hexdigest() != e['local_sha256']) for e in m]
print([p for p, differs in bad if differs])
EOF
# → ['docs/runbooks/rag-production.md']

# 评测基线哈希
sha256sum data/evaluation/retrieval_baseline.json
# → f5578371bca4589e8b2011ac4fbea2c17dbef57ab24b811f9247d92954f3ac65

# 服务健康
curl --noproxy '*' -fsS http://127.0.0.1:18003/health
```

## 8. 限制与缺口（不得当作已完成）

1. **远程字节无法重新核验**：无 `10.101.9.190` 的 SSH 权限；`/opt/accelerator-rag` 内容、容器镜像 ID、`docker ps` 均未独立核验。需要 GPU 主机的只读访问（或运维提供的哈希清单）才能把“部署未变”从推断升为证实。
2. **服务器文档副本滞后**：`docs/runbooks/rag-production.md` 服务器版本落后工作区一版。是否需要在下次部署时同步，由运维裁决；本次未改动服务器。
3. **无内部过程记录**：本次回归无 trace，轮次/预算/补检索只能引用 2026-10-28 历史归档，不能宣称当前实例的内部行为。
4. **本机无原始语料**：`data/l0_raw` 不存在，无法在本机重放解析/切块/嵌入；语料统计只能引用冻结记录的数值，不能重新计算。
5. **生成模型服务的模型名与版本**：仅从配置读到 `ds-1017`，未向 `/v1/models` 查询（需要凭据，且不应写入报告）。
6. **未核验的部分均未使用“已确认/已完成”措辞**。

## 9. 冻结边界声明

- 本次**没有**修改 `src/`、`config/`、`data/documents/registry.json`、任何索引或服务。
- 本次**没有** git commit / push / 部署 / 重启。
- 本次**没有**清理工作区既有改动。
- 本目录新增文件仅用于记录本阶段证据。
