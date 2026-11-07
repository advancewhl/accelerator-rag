# kb-2.0.0-rc.3 基线冻结记录

日期：2026-11-07（冻结时刻 2026-11-07T18:53:00+11:00）。
机器可读版本：[`data/evaluation/research-benchmark-300-v1/baseline/baseline-freeze.json`](../../../data/evaluation/research-benchmark-300-v1/baseline/baseline-freeze.json)。
本记录只做只读核对：未修改生产配置，未在 GPU 主机写文件，未重启或停止容器，未改动代码，未提交 Git。

## 1. 基线口径

冻结对象是生产中的 `kb-2.0.0-rc.3` 发布及其完整问答链路，用作论文阶段一的对照强基线。基线由五部分组成，缺一不可：

1. 发布目录 `/opt/accelerator-rag-releases/kb-2.0.0-rc.3`（源码、配置、构建产物与报告快照）。
2. 冻结语料 `kb2-prod-20261105-v3`：222 个修订、10,793 个父块、10,654 个可索引父块、6,989 条表格行、3,086 个媒体文件。
3. 两路密集索引（E5 13,766 points；Qwen3 10,654 points）与各自 `dense_index_contract_id`。
4. 生成模型 `ds-1017`、嵌入模型、重排模型及其运行参数。
5. 提示词与核验规则（以 `prompt_fingerprint` 和文件 sha256 标识）。

口径边界：这是**工程回归基线**，不是语义准确率基线。rc.3 的 97/100 HTTP 成功、74/100 状态匹配只说明服务可用性和状态一致度，不说明回答正确率；人工语义评分尚未完成（manifest `incomplete_reasons`）。

## 2. 发布身份

| 字段 | 值 | 来源 |
| --- | --- | --- |
| release_id | `kb-2.0.0-rc.3` | `reports/kb-2.0.0-rc.3-20261105/release-manifest.json` |
| build_id | `kb2-prod-20261105-v3` | 同上；服务器构建目录存在同名目录 |
| status | `live` | 同上（但见 §7 校验失败） |
| created_at | `2026-11-05` | 同上 |
| previous_release | `kb-2.0.0-rc.2` | 同上；服务器存在 rc.2 目录与 manifest（build_id `kb2-prod-20261102-v2`） |
| release 目录 | `/opt/accelerator-rag-releases/kb-2.0.0-rc.3` | manifest `release_dir`；服务器 `ls` 核对 |
| snapshot/build 目录 | `/workspace/data/knowledge-builds/kb2-prod-20261105-v3`（宿主映射到 release 目录 `data/knowledge-builds/…`） | manifest `snapshot_dir`；服务器目录存在 |
| registry | `data/documents/v2/registry-v2.json` | manifest；服务器 `sha256sum` |
| registry sha256 | `f3bd43062ec321fb98b49efefe5a5eb4233d8156c825ced399079989dc2103e7` | manifest；服务器复算一致 |
| 发布清单 sha256 | `537c209f4520ca6f22262ffde7159d43a52dd36f2502b563c7a1093f7ab69fcf` | 仓库文件与服务器文件逐一比对一致 |
| code.git_commit | `5717746c0cf92d0f0c193fd1c2fc9003ec235ea4` | manifest；本地 Git 对象存在，但不在当前 HEAD 历史（历史重写，旧 SHA 失效） |
| code.source_sha256 | `c320e6b6335a461c0f8bd39ad3170501e3f78262c9f92a3a6fee7581cee7a7d4` | 已确认等于 `sha256(release-source.tar.gz)`（服务器复算） |
| code.worktree_dirty | `true` | manifest；用发布源码与 commit `5717746…` 对比，answer.py、evidence.py、workflow.py、retrieval.py、api.py 确有差异，context.py、runtime.py、service.py、scope.py 相同，支持“构建时工作树为脏” |

生产容器实际读取的配置是 `/opt/accelerator-rag-releases/kb-2.0.0-rc.3/config/rag-production.json`（sha256 `f089b051…`），其中 `release_id=kb-2.0.0-rc.3`、`model_name=ds-1017`、`generation_max_tokens=4096`。仓库内的 `config/rag-production.json`（sha256 `a542db2e…`）使用不同的索引路径、集合名与 point_count（4,803/4,572），不是 rc.3 生产配置，**不能**用来描述基线。

在线服务 `/v1/rag/releases/current` 返回：`release_id=kb-2.0.0-rc.3`、222 文档、102 族、10,654 索引段、`build_id=unknown`。`build_id` 为 unknown 是代码设计（`src/accelerator_rag/rag/release.py` 只从配置读 release_id），不代表发布缺构建号。

## 3. 语料签名

来源：manifest `corpus` 段；本地 `python3 scripts/research/build_rc3_inventory.py` 复算；服务器发布目录复算。

| 指标 | 值 | 复核方式 |
| --- | --- | --- |
| 构建修订数 | 222 | 本地汇总 `tmp/research-rc3/chunk-report.json`；manifest |
| 登记修订数 | 225 | `data/documents/v2/registry-v2.json` |
| 排除的 restricted 修订 | 3 | registry `access_scope=restricted` |
| 文档族（构建） | 102 | `tmp/research-rc3/inventory/families.json` |
| 文档族（登记） | 104 | registry |
| 父块总数 | 10,793 | chunk-report 汇总；本地/服务器一致 |
| eligible 父块 | 10,785 | manifest；本地汇总 |
| 可索引父块 | 10,654 | chunk-report 汇总；manifest |
| 短块过滤 / 保留 | 131 / 173 | manifest |
| 不合格块 | 8 | manifest |
| 表格行记录 | 6,989 | `records/*.json` 汇总；`row-record-integrity.json` 0 错位 |
| 媒体文件 | 3,086（631,338,198 字节） | `parse-report.json` 汇总；`media-manifest.json` 3,086 条 |
| 媒体清单 sha256 | `7db7a8b1a0508498aa2be0a9e50d8b50cfc31c04ccf10aad6568bbf841046efa` | manifest；服务器文件复算一致 |
| parse 状态 | `parsed: 222` | parse-report |
| 表格行完整性 | `ok=true`, `missing_chunk=0`, `row_not_in_chunk=0` | release `reports/benchmark-100-20261105/row-record-integrity.json` |
| **chunks_sha256_concat** | `4d935fd08fc55249fef645c36b67d3a38df8fcc41ed19844b7f1b5924ef1c321` | 本地 inventory 复跑；服务器按文件排序逐文件 sha256 复算，值相同 |
| revision_chunk_counts_sha256 | `87965b0ca9ac419f5bcf80c15832042ae8e0c580d877d5e84e592afe825c7181` | 本地 `corpus-digest.json` |
| 本地快照报告一致性 | chunk/quality/parse 三份报告 sha256 与发布目录逐一相同 | `sha256sum` 对比 |

角色分布口径提醒：研究计划第 2 节的“59 个设计目标、19 个规范要求、18 个测试结果、10 个验收结论”是 **225 条登记修订**口径；rc.3 实际构建的 222 条中设计目标为 57 条（3 条 restricted 修订里 2 条是 design_target，已被排除）。引用时不能把 59 当作构建内数量。

## 4. 索引签名

来源：manifest `indexes`、发布配置、index-report；点数和父块数已在服务器磁盘上直接统计。

| 项目 | E5 | Qwen3 |
| --- | --- | --- |
| model_name | `intfloat/multilingual-e5-base` | `Qwen/Qwen3-Embedding-0.6B` |
| model_path | `/workspace/tmp/stage-two-seven/models/intfloat--multilingual-e5-base` | `/workspace/tmp/stage-two-eight/models/Qwen--Qwen3-Embedding-0.6B` |
| index_path | `/workspace/tmp/kb2-indexes/kb2-prod-20261105-v3/e5/qdrant` | `/workspace/tmp/kb2-indexes/kb2-prod-20261105-v3/qwen3/qdrant` |
| collection | `knowledge_kb2_prod_20261105_v3_e5` | `knowledge_kb2_prod_20261105_v3_qwen3` |
| dense_index_contract_id | `ccd4601d1698d3bff5b46589f11fc036e035ca57c1d8d179cd56b6b2d50e16f4` | `6698d5531a29685c9a4002123d183e4cfa38f0e491fbeb3086448e2f0e6aa823` |
| passage_contract_id | `dba19095d5a1360bcdd72e7fbceddf594a23c364cbd423ebe3049dbd2975a0fb` | `7ea2c062c7ac7baa3b9023363f0e201558c87335010cd397914b8787d2798348` |
| point_count | 13,766 | 10,654 |
| parent_count | 10,654 | 10,654 |
| device / dtype | `cuda:0` / `float32` | `cuda:0` / `float32` |
| 构建 batch_size | 8 | 2（README：首轮 batch 8 OOM，改 batch 2 续建） |
| 向量维度 / 最大长度 | 768 / 512 | 1,024 / 32,768 |
| weights_manifest_sha256 | `923e74dc0f652fc6c0fbcdb3a76305e78a13f96c4b7a776e35c821da84bc5b05` | `2adc7b506e6e9d90617a5cb1f5091fe0c039e153dd9fc72732f606c183c5f541` |
| model_config_sha256 | `9dab198f24c8c0879e481cf7822005d5ecbceedbacb390ffafa594e28d31bac4` | `b5bf1f51fc45be473a54718cef92448d90a1be001bf9b9a44b8c7f10a19feaa9` |
| tokenizer_sha256 | `798f7509a92c8e84840c5c860ea274ac7de2e3df22bac00d3a81f45333733968` | `f78138e5e2c10f13c512d100a783a466471d57279d55785f5567cd33f01e27ea` |

一致性检查（`index-build-report.json`）：`same_parent_set=true`、`same_parent_text=true`、`same_parent_evidence=true`、`parent_count=10654`、`point_counts_match_embedded=true`、`warnings=[]`。父块集合/正文/证据哈希分别是 `a074331e…`、`4fa6d4c6…`、`00de46b4…`，两路相同。

**服务器核对结果**：

- Qdrant HTTP API（默认 6333）：**不可达**。`curl -sS -m 5 http://127.0.0.1:6333/collections` 返回 exit 7 `Connection refused`；运行时使用嵌入式本地 Qdrant（`QdrantClient(path=...)`），GPU 主机没有独立 qdrant 服务，也没有 qdrant 镜像。
- 替代核对：两个集合目录均存在（`collection/knowledge_kb2_prod_20261105_v3_e5/`、`collection/knowledge_kb2_prod_20261105_v3_qwen3/`）。直接以只读方式打开各自的 `storage.sqlite`（`mode=ro&immutable=1`），统计 `points` 表并反序列化 payload 的去重 `parent_chunk_id` 与 `dense_index_contract_id`。结果：E5 points=13,766、parents=10,654；Qwen3 points=10,654、parents=10,654；两路 contract 与 manifest 完全一致。结论：**集合存在，点数、父块数与契约一致**。

## 5. 模型与提示词

### 5.1 生成模型

| 字段 | 值 | 来源 |
| --- | --- | --- |
| model_name | `ds-1017` | 发布配置；容器环境 `ACCELERATOR_MODEL_NAME` |
| base_url | `http://127.0.0.1:8000/v1` | 发布配置；容器环境 `ACCELERATOR_MODEL_BASE_URL` |
| 容器 / 镜像 | `ds-1017` / `ds1017-nvidia:2b009fc-sm120` | `docker inspect ds-1017` |
| 镜像 ID | `sha256:0b06ba91414445802caaeed4ce4fe2870df6c31c7a51d8eee69367c15b87a379` | 同上 |
| vLLM build commit | `2b009fc6d1493a9a1ad19f4d0c7230b7e6b7e63a` | 容器环境 `VLLM_BUILD_COMMIT` |
| served weights | `/models/nvidia-DeepSeek-V4.1-Flash-1017-NVFP4` | 容器启动参数 |
| tensor parallel / max-model-len / max-num-seqs | 8 / 1,048,576 / 18 | 容器启动参数 |
| `/v1/models` 返回 | `["ds-1017"]` | 只读 GET（密钥未记录） |

### 5.2 嵌入与重排

- E5：`/workspace/tmp/stage-two-seven/models/intfloat--multilingual-e5-base`（1.1G），`cuda:0`，float32，运行时 batch 8（`runtime.py`）。
- Qwen3-Embedding：`/workspace/tmp/stage-two-eight/models/Qwen--Qwen3-Embedding-0.6B`（1.2G），`cuda:0`，float32，batch 8。
- Qwen3-Reranker：`/workspace/tmp/stage-two-eight-two/models/Qwen--Qwen3-Reranker-0.6B`（1.2G），`device=cuda:0`，`dtype=auto`（代码在 CUDA 上解析为 bfloat16，否则 float16；实际生效 dtype 未从进程读取），`batch_size=4`，`max_length=8192`。

### 5.3 提示词指纹

`prompt_fingerprint = 00077cbb71e23eaddd5bb641e1d94d0cc42269bce515a121702d6bd01abd1a6d`。

算法：对参与文件按仓库相对路径排序，逐行拼接 `"<path>\t<sha256>\n"`，再对 UTF-8 字节取 sha256。参与文件（仓库与发布目录逐一相同）：

| 文件 | sha256 | 作用 |
| --- | --- | --- |
| `src/accelerator_rag/rag/answer.py` | `7d904a24a6d2f07197186a2fed8446421f31735cbc19770957c01076668a0e2b` | 要求拆解、证据选择、生成、核查提示词与核验规则 |
| `src/accelerator_rag/rag/context.py` | `c6b355a5022938493e767928353cd250ae5acc4336bfee40457fc63f302a9980` | 证据上下文与 span 构建 |
| `src/accelerator_rag/rag/evidence.py` | `cb225353ec1faa3779e74c29bc4b3f74772c14b7528b43682052888d6b03d999` | 证据子集选择与冲突处理 |
| `src/accelerator_rag/rag/retrieval.py` | `799db004d3cd4c440f6b4b65ecb779518c80977e4faff16e7d08dcbed485e154` | 多路召回与重排选择 |
| `src/accelerator_rag/rag/workflow.py` | `a7f9620fc9dcad9c2689a4610dd5e8a85ecb83ed7e7c88f141e425cb7cf286de` | 闭环与补检索提示词 |

`grep` 确认 `submit_requirements` / `submit_evidence` / `submit_claims` / `submit_grounding_review` / `submit_supplementary` 只出现在 `answer.py` 与 `workflow.py`，即全部模型提示词都在这两个文件内；其余三个文件承载核验与上下文规则，因此一并纳入指纹。

manifest 的 `prompt_version=evidence-contract-v2` 是标签，仓库和发布源码中没有同名常量；同名值出现在早先检索基线数据集的 `judgment_revision`。**不要**把 `evidence-contract-v2` 当作当前提示词的版本证明，以 `prompt_fingerprint` 为准。

## 6. 检索与生成预算

| 参数 | 值 | 来源 | 与 manifest 一致 |
| --- | --- | --- | --- |
| max_parents | 5 | `evidence.py: choose_subset(max_sources=5)` | 是 |
| max_evidence_tokens | 6,000 | `workflow.py: run_workflow(token_budget=6000)` | 是 |
| max_retrieval_rounds | 2 | `workflow.py: run_workflow(max_rounds=2)` | 是 |
| generation_max_tokens | 4,096 | `runtime.py` + 发布配置 | 是 |
| default_usage_statuses | current, reference | `retrieval/scope.py: DEFAULT_USAGE_STATUSES` | 是 |

代码里还有 manifest 未列出的边界：候选父块最多 20（`RequirementRetriever(candidate_limit=20)`）；每个查询最多注入 10 个结构化精确父块；最多预留 12 个邻近上下文位置；候选上下文超过 18,000 token 时裁剪；每轮最多 8 个检索查询；每轮最多 3 个补检索查询；要求最多 6 项；生成时 `temperature=0`、关闭并行工具调用与 thinking。四组 manifest 参数与代码默认值**没有发现不一致**。

## 7. 运行环境

| 项目 | 值 | 来源 |
| --- | --- | --- |
| GPU 主机 | `localhost.localdomain`，Rocky Linux 9.7，内核 `5.14.0-611.20.1.el9_7.x86_64`，96 线程，503 GiB 内存 | 只读 `uname` / `/etc/os-release` / `nproc` / `free` |
| GPU | 8 × NVIDIA RTX 6000D，每卡 85,651 MiB（约 83.6 GiB），驱动 580.65.06，CUDA 13.0 | `nvidia-smi` |
| 探测时显存占用 | 70,069–75,460 MiB / 卡 | 同上 |
| RAG 运行时镜像 | `accelerator-rag-runtime:20261026`，ID `sha256:6ae5d53a…`，Ubuntu 22.04 基础镜像，Python 3.12.12 | `docker inspect` / 容器内只读版本查询 |
| Python 包 | qdrant-client 1.18.0、transformers 5.14.0、sentence-transformers 5.6.0、torch 2.9.0+cu129、fastapi 0.125.0、pydantic 2.13.4 | 容器内 `importlib.metadata` |
| 容器 | `accelerator-rag`，host 网络，端口 8003，`/workspace` 只读挂载 release 目录，`/workspace/tmp` 可写；启动于 2026-11-06T09:22:52Z，探测时 healthy | `docker inspect` |
| Qdrant | 嵌入式本地模式（client 1.18.0）；`compose.yaml` 固定 `qdrant/qdrant:v1.18.1` 但未运行；6333 不可达 | `curl` / `docker images` |
| 构建环境 | manifest 记录 `kb2-parse-env Python 3.11.15`、LibreOffice 7.1.8.1 + libreoffice-calc、tesseract 4.1.1 | manifest；主机上 LibreOffice 7.1.8.1、tesseract 4.1.1 已核对；Python 3.11.15 未找到现成环境 |

## 8. 可重建命令链

| 步骤 | 命令 | 状态 |
| --- | --- | --- |
| registry 生成/合并 | `python scripts/migrate_registry_v2.py`；`python scripts/register_cable_tables.py <目录>` | 只在文档中记录（会写 registry，本次不重跑） |
| 解析与切块 | `python scripts/kb2_candidate_build.py --build-id kb2-prod-20261105-v3 --stage all` | 依赖 GPU 环境未复跑 |
| 双路索引 | `python scripts/kb2_build_indexes.py --build-dir … --model-root /workspace/tmp --output-root /workspace/tmp/kb2-indexes/kb2-prod-20261105-v3 --e5-model intfloat--multilingual-e5-base --qwen-model Qwen--Qwen3-Embedding-0.6B --device cuda:0 --batch-size <N> --write-config …` | 依赖 GPU 环境未复跑；E5 batch=8、Qwen3 batch=2 由 index-report 确认，其余 CLI 参数按脚本示例重建 |
| 发布清单落盘 | 人工整理 `release-manifest.json` 并复制到 release 目录 | 只在文档中记录；仓库无最终清单生成脚本 |
| 清单校验 | `python3 scripts/validate_release_manifest.py reports/kb-2.0.0-rc.3-20261105/release-manifest.json` | **已在本机复跑**：exit 1，`ERROR: 完整发布缺少 verification 记录: performance_baseline` |
| 本地语料清单 | `python3 scripts/research/build_rc3_inventory.py` | **已在本机复跑**：exit 0，222 文件 / 10,793 块 / `4d935fd0…`；重复运行字节级一致 |
| 100 题回归 | `python scripts/kb2_run_regression.py --base-url http://127.0.0.1:8003 --questions data/evaluation/kb2-benchmark-100-v1.json --output <path>` | 未复跑（调用生产模型有成本）；引用既有报告 |

索引报告记录的构建时间：E5 `2026-11-05T13:07:03+00:00`，Qwen3 `2026-11-05T14:33:48+00:00`；`index-build-report.json` 的 `consistency` 块见 §4。

## 9. 已验证清单

1. 仓库与服务器 `release-manifest.json` 字节相同（`537c209f…`）。
2. 服务器 registry sha256 与 manifest 一致（`f3bd4306…`）。
3. `code.source_sha256` 等于 `release-source.tar.gz` 的 sha256（`c320e6b6…`，611 个条目）。
4. 发布源码与 commit `5717746…` 的差异支持 `worktree_dirty=true`（5 个文件不同）。
5. 在线服务健康；`/v1/rag/releases/current` 返回 `kb-2.0.0-rc.3`、222 文档、102 族、10,654 索引段。
6. `/v1/models` 返回 `ds-1017`。
7. 本地 `corpus-digest.json` 的 `chunks_sha256_concat` 与服务器发布目录复算值一致。
8. 本地 chunk/quality/parse 三份报告与发布目录文件哈希一致。
9. 表格行 6,989 条、0 错位；媒体清单 3,086 条。
10. 两路索引的点数、父块数、contract 已从磁盘索引直接统计，与 manifest 一致；两路父块集合/正文/证据哈希相同。
11. 生产配置的索引条目与 manifest 完全一致。
12. 五个提示词/规则文件在仓库与发布目录中逐一相同；`prompt_fingerprint` 可复算。
13. manifest 的四组预算与代码默认值一致。
14. `build_rc3_inventory.py` 与 `validate_release_manifest.py` 的退出码与输出已记录。

## 10. 未核实/无法核实清单

1. **构建时完整工作树状态**：只用发布源码与 commit 逐文件差异间接证明；没有当时的 `git status`/diff。
2. **code.git_commit 的分支归属**：该 commit 不是当前 HEAD 祖先，无分支包含；历史重写后旧 SHA 失效。
3. **构建环境 Python 3.11.15**：当前 GPU 主机找不到 `kb2-parse-env`，只有 manifest 记录；LibreOffice/tesseract 已核对。
4. **生成模型权重与 tokenizer 指纹**：只确认了 served-model-name、镜像、启动参数；未读取权重哈希。
5. **重排模型实际 dtype**：配置为 `auto`，代码会解析为 bfloat16/float16；未从运行进程读取。
6. **Qdrant HTTP API 级核对**：6333 不可达；改用磁盘统计（点数/父块/contract 均一致）。
7. **manifest `status=live` 的合规性**：仓库校验脚本 exit 1（缺 `verification.performance_baseline`）；是字段名不一致还是确实缺记录，未由发布负责人确认。本记录不把 live 当作已通过校验。
8. **verification 报告是否随发布冻结**：manifest 引用的 `rc3-candidate-final.json` 等文件存在于仓库 `reports/`，但 release 目录中的对应文件是更早的 `rc3-candidate.json`/`rc2-production.json`（无 `-final`），且没有 `comparison.md`、`rc3-cable-lookup.json`。
9. **manifest 服务器 mtime 与最终报告生成时间的时序**：服务器 mtime 2026-11-06 00:05 +0800 早于其引用的报告（02:57 +0800），但内容哈希一致；同步方式未核实。
10. **索引构建的完整 CLI 参数**：只有 device/dtype/batch_size 等报告字段，未留存完整命令行。
11. **100 题与 30 题运行结果**：未复跑；只引用既有报告。
12. **`prompt_version` 对应关系**：代码无该常量，无法把标签映射到具体提示词文本；以 `prompt_fingerprint` 为准。
13. **release-source 全量审计**：只抽查 5 个文件，未审计 611 个条目的全部内容。
14. **部署脚本凭据**：`switch_release.sh` 内含明文模型 API key；本记录未复述其值，也未修改任何配置。

## 11. 使用限制

1. **30 道版本题必须与全库检索分开报告**。它们显式传入修订范围（`scope.mode=explicit_revisions`），属于“指定文档问答”；比较方法时必须给所有方法相同范围信息，不能与未给范围的默认检索混算。
2. 100 题集是已曝光的开发/回归材料，不是独立盲测；其中 10 道标为 sealed 的题已在本轮被阅读，不再具有盲测含义。
3. 97/100 HTTP 成功与 74/100 状态匹配不是准确率；引用父块指标 0/0 是评价字段缺失，不能解释为引用全对或全错。
4. rc.2 → rc.3 同时改变语料与能力，不能把差异解释为某一算法的因果效果。
5. 无独立人工语义评分；K7 观察期未开始；并发 3 时 rc.3 尾部延迟高于 rc.2，仍需观察。
6. 3 条 restricted 修订不在 222 条构建内；59 个设计目标是 225 条登记口径，构建内是 57 条。
7. 基线依赖发布目录、模型目录、GPU 与嵌入式 Qdrant；缺任一项不能声称可复现。
8. 引用基线时应同时引用本冻结记录和 manifest；不要只引用 `status=live`。

## 12. 相关文件

- 权威发布清单：[`reports/kb-2.0.0-rc.3-20261105/release-manifest.json`](../../../reports/kb-2.0.0-rc.3-20261105/release-manifest.json)
- 发布记录：[`reports/kb-2.0.0-rc.3-20261105/README.md`](../../../reports/kb-2.0.0-rc.3-20261105/README.md)
- 研究计划：[`docs/research/rag-research-reset-20261107.md`](../rag-research-reset-20261107.md)
- 300 题规范：[`docs/research/benchmark-300/SPEC.md`](SPEC.md)
- 本地只读语料快照：[`tmp/research-rc3/`](../../../tmp/research-rc3/)
- 机器可读冻结记录：[`baseline-freeze.json`](../../../data/evaluation/research-benchmark-300-v1/baseline/baseline-freeze.json)
