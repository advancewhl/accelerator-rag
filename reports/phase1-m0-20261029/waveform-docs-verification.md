# Phase 1 · Waveform 技术文档核验记录（2026-10-29）

本文件是 `docs/waveform/` 两份技术文档的**核验记录**，不是发布验收，也不构成系统能力声明。
未写入 JSON 台账。

## 交付物

| 文档 | 行数 | 表格数据行 | 代码定位锚点 | 文末核验范围小节 |
| --- | --- | --- | --- | --- |
| `docs/waveform/waveform-storage-dataflow.md` | 405 | 91 | 121 | §10 |
| `docs/waveform/alignment-semantics-and-diagnostics.md` | 776 | 196 | 174 | §8 |

## 证据基线

| 项 | 值 | 获取方式 |
| --- | --- | --- |
| 仓库 | `/home/whloong/waveform-storage/waveform-storage-system` | 只读 |
| HEAD | `dc50e08a2beddff42c297a237b3f3312f5c24ac9` | `git log -1 --format='%H %ad %s' --date=iso` |
| 提交时间 | 2026-10-26 21:06:55 +0800 | 同上 |
| git describe | `archive/pre-spectrum-analysis-ui-20261008-13-gdc50e08` | `git describe --always --tags` |
| 核验日 | 2026-10-29（Asia/Shanghai） | — |

## front-matter 字段来源核查

| 字段 | 结论 | 检查命令 |
| --- | --- | --- |
| `applicable_system_version` | 系统无此字段；用真实 commit 代替 | `grep -rn "applicable_system_version\|alignment_algo_hash" .`（全仓库，0 命中） |
| `alignment_algo_hash` | 系统无此字段；在数据流文档标“未定义”，在对齐文档给 Phase 1 派生值 | 同上；系统同族机制见下 |
| `verified_date` | 2026-10-29 | — |
| `owner` | 未指派（待项目负责人裁决），全文无人名 | — |

系统内唯一的同族机制（**不等价，不可混用**）：`WaveformAgentV2` 对
`processing/alignment.py` **单文件**做 sha256 → `alignment_source_hash`，输出为 provenance 的
`algorithm_source_sha256`（`src/waveform_storage/application/agent_v2_service.py` 第 48–54、618–619 行）。
代码作者明确区分“单模块摘要”与“稳定的源码文件集合”（同文件第 651–655 行注释）。

## Phase 1 派生标识实算

文件清单（按路径升序）与单文件 sha256：

| 文件 | sha256 |
| --- | --- |
| `src/waveform_storage/application/retrieval_service.py` | `0f655a6946abbfba32487319dd2708647a059e9c70f93385ce07a09ec3780165` |
| `src/waveform_storage/io/hdf5_io.py` | `d3511cc99d3b1daadac0a2bce0bd86c3eafa6ee8d84e4b0a6c2399615d0e897d` |
| `src/waveform_storage/processing/alignment.py` | `e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346` |
| `src/waveform_storage/processing/bunch_id_diagnostics.py` | `bba0f9b54ec39f3da8ddbbe19dd2f9e18b6a9c20b51edda62665c09fcbc62f9c` |
| **组合 `alignment_algo_hash`** | **`390fd8e9a708dbaaeda0c877265a74bdf21ccdabe91b0c45911c919da6c4e65d`** |

组合算法：把 4 行 `<sha256>␠␠<相对路径>` 按路径升序拼接后再取 sha256（等同仓库既有
`MANIFEST.sha256` 行格式）。重算命令写在文档第 1.2 节，逐字可复现。

交叉验证方式：`printf … | LC_ALL=C sort | xargs sha256sum | sha256sum` 与 Python
`hashlib` 独立实现两次结果一致（首次测量因临时文件中转导致一次错误值 `abcfa6a9…`，已废弃，
最终值以两种独立方法一致的 `390fd8e9…` 为准）。

## 真实数据核验（只读）

对 `data/samples/20251112/` 的 22 个 HDF5 抽样计算：

| 项 | 观测 |
| --- | --- |
| 文件命名 | `RAW-{HHMMSS}-{device_id}-S{seq:05d}.h5`，与代码命名规则一致 |
| 目录层次 | 扁平日期目录，**不含**生产路径的 `raw/BIData` 两级（历史搬运目录） |
| `RAW-110023-AC_LA_INJ1_BI_SBPM08-S00000.h5` | `BunchIDData (1,1024) uint64`、`Data (2,1024) int64`；bunchID 38207987001007→38208498501007，相邻差恒 500000 |
| `RAW-110023-*` 组 10 台设备 | 每台 1024 点、步长恒 500000；严格交集 **1023**、并集 1025 |

交集 1023 与 `docs/MongoDB元数据模块设计.md` §5 记载的“10 个文件、严格对齐得到 1023 个公共
bunch ID”一致（独立复算，非转述）。

## 代码-文档差异统计

| 文档 | 差异条数 | 编号 |
| --- | --- | --- |
| 数据流文档 | 6 | D1–D6 |
| 对齐文档 | 8 | A1–A8 |

要点：`waveform_files._id` 分段形式（文档内部不一致）、`failed` 任务也写
`status=completed` 文件记录、带段身份时导出强制 v2、`zero_policy` 作用对象是 bunchID 而非
X/Y、频率白名单所在层、时间轴基准步长并列众数缺保护、插值实为线性网格重采样。

## 未核验（与两份文档文末一致）

- 未运行任何测试（`tools/run_quality.py`、`tests/*` 均未执行）；未做发布验收、SHA-256
  manifest 校验、二进制身份核验、真实桌面 smoke。这符合仓库 `AGENTS.md` 第 7–13 行的
  “长期验证范围限制”，本次任务也未获该授权。
- 未连接现场 EPICS / timing PV / MongoDB / systemd / dashboard。
- 未执行 GUI 点击流；诊断文案取自源码字符串。
- 未测性能；文档中的 $O(n^2)$ 为复杂度分析。
- 未核验 `legacy/` 下历史对齐适配路径的逐行行为。
- 未修改 Waveform 仓库任何文件（全程只读），未 `git commit`/`push`，未写入任何密钥。

## 写入范围

本任务仅写入：

- `docs/waveform/waveform-storage-dataflow.md`
- `docs/waveform/alignment-semantics-and-diagnostics.md`
- `reports/phase1-m0-20261029/waveform-docs-verification.md`（本文件）

## 2026-10-29 13:45 修订（Lead，跨文档统一）

上面第“front-matter 字段来源核查”与“Phase 1 派生标识实算”两节记录的是**修订前**的取舍：
数据流文档标“未定义”、对齐文档用 4 文件集合哈希作 `alignment_algo_hash`。故障历史文档
（wf-audit）采用了另一口径：直接用系统既有 `algorithm_source_sha256`
（`e8db12d7…`，= sha256 of `processing/alignment.py`）。两份文档对同一系统给出不同的
`alignment_algo_hash`，属于版本绑定不一致，必须消除。

处理（已落盘并复核）：

1. **统一为系统既有定义优先**：三份 Waveform 文档的 `alignment_algo_hash` 一律取
   `e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346`
   （系统 `agent_v2_service.py:54` 的 `alignment_source_hash` / `:618-619` 的
   `algorithm_source_sha256`），并给重算命令。
2. 4 文件集合哈希保留但**改名降级**为 `alignment_doc_bundle_hash = 390fd8e9…`，仅作文档侧
   补充追溯，不写入 front-matter、不称系统能力。
3. 数据流文档不对齐算法负责，front-matter 改标“不适用”并指向对齐手册。
4. 复核命令：`sha256sum src/waveform_storage/processing/alignment.py`（Waveform 仓库）＝
   `e8db12d7…`；`grep -n "alignment_algo_hash" docs/waveform/*.md` 三处值一致。
5. 统一后的取值与重算记录见 `docs/waveform/alignment-semantics-and-diagnostics.md` §1.2、
   `docs/waveform/README.md`“状态说明”，以及 `docs/waveform/fault-history-and-version-changes.md` §0。

本次修订**不改变**两份文档的技术断言与证据；只改 front-matter 取值与相关说明句。
