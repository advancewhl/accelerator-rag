---
applicable_system_version: "waveform-storage-system@dc50e08 (2026-10-26)"
alignment_algo_hash: "e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346（系统既有 algorithm_source_sha256 = sha256(processing/alignment.py)，重算见 1.2；另有文档侧 4 文件集合哈希 390fd8e9…c4e65d，仅为补充追溯标识，非 front-matter 主值）"
verified_date: "2026-10-29"
owner: "未指派（待项目负责人裁决）"
---

# 对齐语义、参数与诊断手册

本文回答三个问题：本系统的“对齐”到底是什么（不是什么）、它由哪些参数决定、出问题时按什么
顺序判别。所有断言以源码为准；文档与代码冲突时以代码为准，冲突单列在第 7 节。

**证据基础**：只读仓库 `/home/whloong/waveform-storage/waveform-storage-system`，
HEAD `dc50e08a2beddff42c297a237b3f3312f5c24ac9`（2026-10-26 21:06:55 +0800）。
核验日 2026-10-29。行号对应该提交；`git describe --always --tags` 为
`archive/pre-spectrum-analysis-ui-20261008-13-gdc50e08`。

---

## 0. 结论先行

| 问题 | 答案 | 依据 |
| --- | --- | --- |
| “对齐”对齐的是什么？ | 对齐的是**束团编号 `bunchID`（整数集合）**，把多台设备按共同整数 ID 摆到同一列；**不做时间轴对齐、不做插值、不做物理时钟换算** | `processing/alignment.py` 模块 docstring 第 1–5 行：“order-independent bunchID alignment … does not guess scale factors or convert between incompatible device timebases” |
| 有没有时间对齐/重采样式对齐？ | **没有**。`bunchID → 相对时间` 是分析层在**对齐之后**另行换算的一步，不是对齐算法的一部分 | 对齐层 `alignment.py` 全文不含 `time`/`timestamp`/`resample`/`interp`/`tolerance` 任一标识符（`grep -Ei` 只命中 `params`）；时间轴在 `analysis/loaders.py:_id_times`（第 153–166 行） |
| 有没有容差参数？ | **对齐层没有容差**：ID 匹配是整数精确相等 | `alignment.py:_extract_aligned` 第 419–422 行 `item.bunch_ids[safe_positions] == target_ids`；`np.intersect1d` 第 340 行 |
| 有没有段间/整任务对齐？ | **未实现** | `AGENTS.md` 第 21–23 行；`docs/CURRENT_STATUS.md` 第 276–278 行 |
| 采样率 $f_s$ 从哪来？ | 采集请求的 `frequency_hz`；历史分析取 `CaptureRunSummary.frequency_hz`，不与当前机器频率混用 | `acquisition/runtime.py`；`analysis/loaders.py:_sampling_rate` 第 136–150 行；`docs/agent-api-v2.md` 第 151 行 |
| 时间零点在哪？ | **该段第一个共同 bunchID**，不是墙钟。段级 `captured_at` 只作来源信息 | `loaders.py:_id_times` 第 165 行 `ids[0]`；`engine.py:_prepare` 第 53 行再次归零 |

一句话：**本系统的“对齐”是整数 ID 交集/共识，不是信号对齐。** 任何把它描述成“按时间戳
对齐波形”的说法都是错的。

---

## 1. 字段来源说明（front-matter）

| 字段 | 取值 | 依据 |
| --- | --- | --- |
| `applicable_system_version` | `waveform-storage-system@dc50e08 (2026-10-26)` | `git log -1 --format='%H %ad'` |
| `alignment_algo_hash` | `e8db12d7…3d5346`（系统既有 `algorithm_source_sha256`） | 重算见 1.2；与 [历史故障记录与版本变更说明](fault-history-and-version-changes.md) 绑定同一值 |
| `verified_date` | 2026-10-29 | 本次核验日 |
| `owner` | 未指派（待项目负责人裁决） | Phase 1 交付物，项目内无指派记录 |

**跨文档一致性（2026-10-29 统一）**：本文与故障历史文档此前各用不同值——本文用 4 文件集合哈希、
故障历史用系统单文件摘要。现已统一为“系统已有定义优先”：`alignment_algo_hash` 取系统
`algorithm_source_sha256`（`e8db12d7…`）；4 文件集合哈希降为文档侧补充标识，编号
`alignment_doc_bundle_hash = 390fd8e9…`，不得写进系统产物、不得对外称系统能力。

### 1.1 系统没有这个字段名，但有等价机制

全仓库检索 `applicable_system_version`、`alignment_algo_hash` 两个字段名（`grep -rn` 全仓库 +
`grep -rln` 限定 `*.py|*.md|*.json|*.yml|*.yaml|*.toml` 于 `apps/ packaging/ docs/ config/
.agents/ src/ tools/`），两次均无匹配。系统既没有这两个字段名，也没有“对齐算法整体”的版本号。

**系统内自带的机制（front-matter 主值直接取用它）**：`WaveformAgentV2.__init__` 对
`src/waveform_storage/processing/alignment.py` **单文件**计算
`sha256` → `self.alignment_source_hash`，输出为 provenance 的 `algorithm_source_sha256`，
并用 `algorithm_version = "bunch-id-alignment:" + hash[:16]` 作短标识。

| 项 | 系统机制（front-matter 主值来源） | 文档侧补充标识 |
| --- | --- | --- |
| 名称 | `alignment_source_hash` / `algorithm_source_sha256` | `alignment_doc_bundle_hash` |
| 覆盖范围 | 单文件 `processing/alignment.py` | 4 个对齐相关源文件（见 1.2） |
| 出现位置 | Agent HTTP API v2 对齐任务 provenance；`write_alignment_v2` 的 metadata | 仅本文档 1.2 正文，不写入 front-matter 主值 |
| 是否系统能力 | 是 | **否** |
| 代码位置 | `application/agent_v2_service.py` 第 48–54 行（计算）、第 618–619 行（输出）；消费 `tests/test_waveform_agent_v2.py` 第 624–627 行 | — |

代码作者明确表示系统**没有**“稳定源码文件集合”的哈希惯例：频谱任务合并 provenance 时执行
`provenance.pop('algorithm_source_sha256')`，注释为
“The analysis manifest defines a spectrum version, not a stable source-file set.
Never label the alignment hash as the spectrum implementation's source identity.”
（`agent_v2_service.py` 第 651–655 行）。因此下面的多文件集合哈希**正是系统声明未定义的那种
东西**，只能作为文档侧的追溯标识，不得写进系统产物或对外声称是系统能力。

### 1.2 主值：系统单文件摘要；补充：文档侧 4 文件集合哈希

**front-matter 主值 `alignment_algo_hash` 就是系统既有值**（不新增定义）：

```bash
cd /home/whloong/waveform-storage/waveform-storage-system
sha256sum src/waveform_storage/processing/alignment.py
# e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346
```

它与 `agent_v2_service.py:54` 的 `self.alignment_source_hash` 逐字节一致；系统以
`algorithm_version = 'bunch-id-alignment:' + hash[:16]`（`:618`）与
`algorithm_source_sha256`（`:619`）写入对齐 provenance。**该值是系统能力，可直接核验。**

下面的 4 文件集合哈希是**文档侧补充标识**（`alignment_doc_bundle_hash`），覆盖范围比系统机制宽，
但系统并未定义这种“稳定源码文件集合”身份（见上段代码注释），因此只能用于文档追溯。

**文件清单（4 个，按路径 `LC_ALL=C sort` 升序）**

```
src/waveform_storage/application/retrieval_service.py
src/waveform_storage/io/hdf5_io.py
src/waveform_storage/processing/alignment.py
src/waveform_storage/processing/bunch_id_diagnostics.py
```

选取理由（逐文件必要性）：

| 文件 | 决定本文哪一部分语义 |
| --- | --- |
| `processing/alignment.py` | 对齐算法、全部 `AlignmentParameters`、`valid_mask` 语义 |
| `processing/bunch_id_diagnostics.py` | 对齐前的原始编号间隔诊断（GUI 警告与阻断依据） |
| `application/retrieval_service.py` | 默认参数（`strict`）、查询键、导出与缓存、设备顺序 |
| `io/hdf5_io.py` | 对齐结果落盘 schema（`shine-waveform-alignment` v2 / legacy） |

**算法**（等价于仓库既有的 `MANIFEST.sha256` 行格式）：

1. 对每个文件取其内容 `sha256`，写成 `<hex>␠␠<相对路径>\n`（`sha256sum` 默认格式，两空格）；
2. 按文件路径升序拼接这 4 行；
3. 对该拼接文本再取 `sha256`。

**精确重算命令**（在仓库根目录执行，逐字可复现）：

```bash
cd /home/whloong/waveform-storage/waveform-storage-system
printf '%s\n' \
  src/waveform_storage/processing/alignment.py \
  src/waveform_storage/processing/bunch_id_diagnostics.py \
  src/waveform_storage/application/retrieval_service.py \
  src/waveform_storage/io/hdf5_io.py \
  | LC_ALL=C sort \
  | xargs sha256sum \
  | sha256sum
```

**2026-10-29 实算结果**（已在 `dc50e08` 上核验）：

| 文件 | 单文件 sha256 |
| --- | --- |
| `.../application/retrieval_service.py` | `0f655a6946abbfba32487319dd2708647a059e9c70f93385ce07a09ec3780165` |
| `.../io/hdf5_io.py` | `d3511cc99d3b1daadac0a2bce0bd86c3eafa6ee8d84e4b0a6c2399615d0e897d` |
| `.../processing/alignment.py` | `e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346` |
| `.../processing/bunch_id_diagnostics.py` | `bba0f9b54ec39f3da8ddbbe19dd2f9e18b6a9c20b51edda62665c09fcbc62f9c` |
| **组合 `alignment_doc_bundle_hash`（文档侧补充，非 front-matter 主值）** | **`390fd8e9a708dbaaeda0c877265a74bdf21ccdabe91b0c45911c919da6c4e65d`** |

交叉校验：`alignment.py` 的单文件 sha256 `e8db12d7…` 与系统 `algorithm_source_sha256`
取值方式相同（都是对文件原始字节直接 `sha256`，见 `agent_v2_service.py` 第 54 行），
因此可用来确认“本机代码与该机制计算的代码相同”；**但两者数值定义不同，不可互相替代或比较**。

**已知覆盖缺口（必须显式声明）**：`analysis/loaders.py::_id_times`（第 153–166 行）定义了
“bunchID → 相对时间轴”的换算，属于本文第 4.5 节内容，但它是**分析层**、不属于对齐算法，
**不在** `alignment_doc_bundle_hash` 的 4 文件之内。该文件的版本由分析层
`ALGORITHM_VERSION = "unified-spectrum-1.0"`（`analysis/engine.py` 第 17 行）标识，两者
不可互相推断。若未来要把时间轴纳入哈希，必须重新定义并向所有消费方通告新值。

---

## 2. 对齐的定义与两层语义

### 2.1 段内对齐（已实现）

**定义**：给定同一 `capture_sequence` 下若干设备的 `(bunchID, X, Y)` 序列（每台一个 HDF5），
产出一个二维矩阵——行是设备、列是共同 bunchID——并给出逐单元有效性掩码。

对设备集合 $\mathcal{D}$、设备 $d$ 的编号集合 $\mathrm{ID}(d)$：

- **strict 模式**（默认）取精确交集

$$
\mathcal{I} = \bigcap_{d\in\mathcal{D}} \mathrm{ID}(d)
$$

- **coverage 模式**迭代收敛到共识集合（见第 3.3 节）

- **结果矩阵**：$\mathbf{x},\mathbf{y}\in\mathbb{R}^{|\mathcal{D}'|\times|\mathcal{I}|}$，
  $\mathbf{M}\in\{\text{true},\text{false}\}^{|\mathcal{D}'|\times|\mathcal{I}|}$，
  其中 $\mathcal{D}'$ 是最终参与的设备集合，$\mathcal{I}$ 升序

$$
\mathbf{M}_{r,c} = \big[\ \mathcal{I}_c \in \mathrm{ID}(d_r)\ \big],\qquad
\mathbf{x}_{r,c} = \text{X}_{d_r}(\mathcal{I}_c)\ \text{若}\ \mathbf{M}_{r,c}\ \text{否则}\ 0
$$

$\mathbf{M}_{r,c}=\text{false}$ 处的 0 是**存储占位**，不是测量值。使用方必须以掩码判断有效性
（`processing/alignment.py:_extract_aligned` 第 407–427 行；`docs/数据对齐v2设计.md` §4 末段）。

**目的**：把“每台设备各自的编号序列”变成可直接逐列比较/绘图/做频谱的公共矩阵，同时
**不**对原始编号做缩放、取模、重排或物理换算。设计动机来自现场真实批次：2025-11-12
12:07:21 的批次含 36 台设备、每台 1024 个非零唯一递增 `uint64` bunchID，但全设备严格交集为 0；
顺序式“交集下降就跳过设备”的做法会把输入顺序变成隐式业务规则（`docs/数据对齐v2设计.md` §1）。

### 2.2 段间 / 任务级对齐（未实现）

| 能力 | 状态 | 依据 |
| --- | --- | --- |
| 跨 `capture_sequence` 对齐 | 未实现 | 检索与对齐的查询键显式包含 `capture_sequence`（`retrieval_service.py:StorageQuery` 第 30–57 行），一次只处理一个段 |
| 整任务汇总（多段合并/平均） | 未实现，且被规范禁止默认拼接 | `AGENTS.md` 第 23 行“不默认拼接不连续的数据段。后续整任务频谱应先逐段计算，再按明确的分析方法汇总。本次发布规范不实现整任务分析。” |
| 段间统一时间零点 | 未实现 | 时间零点取该段第一个共同 bunchID（第 4.5 节），跨段无公共零点 |
| 自动对齐（无需操作员/调用方触发） | 未实现 | GUI 需点击对齐并（异常时）确认弹窗；API 需 POST `/read/alignments`（`docs/agent-api-v2.md` 第 106、118–135 行） |
| 把 bunchID 换算成物理时钟 | 未实现，且被明确拒绝 | 设计文档 §2“不猜测不同设备的缩放、取模或时钟换算”；`loaders.py:_id_times` 第 161 行在编号间隔不成整数倍时直接报错 |

---

## 3. 算法实现（符号级）

### 3.1 入口与总体流程

`processing/alignment.py:align_devices(records, parameters)`（第 105–156 行）：

```text
align_devices
├─ _prepare_records(records, params)      # 逐设备校验/清洗 → (prepared, quality, skipped)
├─ prepared.sort(key=device_id)           # 行顺序与输入顺序解耦（第 126 行）
├─ if 无可用设备: return _empty_result
├─ mode == "strict" → _strict_intersection(prepared)         # 第 131–139 行
│     └─ 交集为空 → 给每台设备记 skipped.reason="no_common_bunch_ids"，返回空结果
├─ mode == "coverage" → _coverage_consensus(prepared, params) # 第 140–144 行
└─ _extract_aligned(active, target_ids)  # 第 146 行 → x, y, valid_mask
```

### 3.2 单设备预处理（`_prepare_records`，第 159–287 行）

按**固定顺序**执行，任一步失败即整台设备跳过并记录原因（顺序不可交换，因为后面的检查依赖前面
的结果）：

| 序 | 检查/动作 | 失败原因 `reason` | 行号 |
| --- | --- | --- | --- |
| 1 | `device_id` 去空白后非空 | `empty_device_id` | 169–174 |
| 2 | 设备 ID 不重复 | `duplicate_device_id` | 176–181 |
| 3 | `bunch_ids` 一维、逐个为 `Integral`（非 `bool`）、非负 | `invalid_array` | 183–191、290–303 |
| 4 | X/Y 一维且为数值类型 | `invalid_array` | 185–186、306–312 |
| 5 | 三个数组长度一致 | `length_mismatch` | 193–201 |
| 6 | `bunchID == 0` 处理（`zero_policy`） | `zero_bunch_id`（仅 `reject_device`） | 203–220 |
| 7 | 过滤后非空 | `empty_after_filter` | 222–233 |
| 8 | 记录**原始顺序**是否严格递增（仅记录，不阻断） | — | 235 |
| 9 | 按 bunchID 稳定排序（`argsort(kind="stable")`） | — | 236–237 |
| 10 | 重复 ID 处理（`duplicate_policy`） | `duplicate_bunch_id`（仅 `reject_device`） | 239–263 |
| 11 | 记录相邻步长集合（排序去重元组） | — | 265–272 |

关键细节，容易误读：

- 步骤 8 的 `was_strictly_increasing` 是**原始输入顺序**的属性；此后算法仍然会排序并对齐
  乱序输入（设计文档 §2“输入乱序会稳定排序”）。因此“乱序输入”不会被拒，只是质量报告里
  `was_strictly_increasing=False`，且对齐前诊断（第 4.2 节）会把它排除出“多数参考”。
- 步骤 10 的 `duplicate_policy="first"` 会先 `np.unique` 取唯一值、再用 `first_indices`
  取第一次出现的 X/Y（第 261–263 行），即“保留首次出现”的语义。
- `zero_policy` 作用对象是 **`bunchID == 0`**，与 X/Y 是否为 0 无关
  （第 203 行 `np.count_nonzero(bunch_ids == 0)`）。X/Y 真零的处理在分析层
  （`AnalysisConfig.zero_policy ∈ {keep, mask_double_zero}`，`analysis/models.py` 第 54、77–78 行）。

### 3.3 strict 交集（`_strict_intersection`，第 337–343 行）

```python
result = records[0].bunch_ids.copy()
for record in records[1:]:
    result = np.intersect1d(result, record.bunch_ids, assume_unique=True)
    if result.size == 0:
        break
return result.astype(np.uint64, copy=False)
```

- 从第一台（已排序的设备）开始，与其余设备逐个求交；一出现空集即提前结束。
- `assume_unique=True` 合法，因为步骤 10 已保证每台设备 ID 唯一。
- 返回数组升序（`intersect1d` 的性质），因此列顺序天然升序，不依赖输入顺序。
- 交集为空**不抛异常**：返回结构化空结果，并为每台设备追加
  `SkippedDevice(reason="no_common_bunch_ids")`（第 133–138 行）。

### 3.4 coverage 共识（`_coverage_consensus`，第 346–394 行）

迭代到设备集合稳定：

1. **候选 ID 集合**（`_ids_at_coverage`，第 397–404 行）：统计每个 bunchID 出现在多少台活动设备中，
   要求至少 $r$ 台：

$$
r=\max\!\left(1,\ \left\lceil \rho_{\text{id}}\cdot n_{\text{active}} \right\rceil\right),\qquad
\mathcal{I}=\{\, i\ :\ \#\{d\in \mathcal{D}_{\text{active}}: i\in \mathrm{ID}(d)\} \ge r \,\}
$$

2. **设备覆盖率**（第 364–376 行）：

$$
c_d=\frac{|\mathcal{I}\cap \mathrm{ID}(d)|}{|\mathcal{I}|},\qquad
d\ \text{保留} \iff c_d \ge \rho_{\text{dev}}
$$

3. 剔除不达标设备并记录 `SkippedDevice(reason="low_consensus_coverage",
   detail="coverage=…, required=…")`；若本轮无剔除 → 收敛返回（第 378–379 行）。
4. 候选集合为空 → 全体记 `no_consensus_bunch_ids`，返回空结果（第 355–360 行）。

**终止性**：每轮要么无剔除而返回，要么设备数严格减少（`active = retained`，`retained` 是
`active` 的真子集），因此最多 $|\mathcal{D}|$ 轮。计算量最坏

$$
O\!\left(|\mathcal{D}|^2 \cdot n_{\text{ids}}\log n_{\text{ids}}\right)
$$

（每轮对每台设备做一次 `np.intersect1d`）。这是当前实现的复杂度上限；`docs/数据对齐v2设计.md`
没有给出性能承诺，本文也不声称任何实测耗时。

### 3.5 结果矩阵抽取（`_extract_aligned`，第 407–427 行）

```python
x_dtype = np.result_type(*(item.x.dtype for item in records))
y_dtype = np.result_type(*(item.y.dtype for item in records))
shape = (len(records), int(target_ids.size))
x = np.zeros(shape, dtype=x_dtype); y = np.zeros(shape, dtype=y_dtype)
valid_mask = np.zeros(shape, dtype=np.bool_)
for row, item in enumerate(records):
    positions = np.searchsorted(item.bunch_ids, target_ids)
    in_bounds = positions < item.bunch_ids.size
    safe_positions = np.minimum(positions, item.bunch_ids.size - 1)
    valid = in_bounds & (item.bunch_ids[safe_positions] == target_ids)
    valid_mask[row] = valid
    x[row, valid] = item.x[safe_positions[valid]]
    y[row, valid] = item.y[safe_positions[valid]]
```

要点：`searchsorted` 需要设备序列已升序（步骤 9 保证）；`safe_positions` 的夹取避免越界；
`valid` 用**整数相等**判定，**没有容差、没有插值、没有最近邻近似**。

### 3.6 落盘 schema

| schema | 内容 | 谁能写 | 代码位置 |
| --- | --- | --- | --- |
| `shine-waveform-alignment` v2 | 数据集 `bunch_ids`(`uint64`)、`x`、`y`、`valid_mask`(`bool`)、`device_ids`、`skipped_devices_json`、`quality_report_json`；属性 `schema_name`、`schema_version=2`、`created_utc`、`parameters_json`、`metadata_json` | 任意对齐结果（含 coverage 缺失单元） | `io/hdf5_io.py:write_alignment_v2` 第 139–178 行；`SCHEMA_NAME`/`SCHEMA_VERSION` 第 26–27 行 |
| legacy 交错合并 | `BunchIDData(1,N)` + `Data(2·N_dev, N)`，行内交错 X/Y；必需设备属性逐行一致 | **仅全单元有效**时；有缺失单元直接 `Hdf5SchemaError` | `io/hdf5_io.py:write_legacy_merged_hdf5` 第 238–283 行（拒绝逻辑第 251–254 行） |

两种写盘都走 `.part` 临时文件 + `os.replace` 原子替换（第 373–385 行）。

---

## 4. 参数全集

**取值范围/越界行为一列是实测的代码行为，不是设计意图。**

### 4.1 对齐参数（`AlignmentParameters`）

定义：`src/waveform_storage/processing/alignment.py:AlignmentParameters`（第 34–56 行），
不可变 `frozen dataclass`，构造时在 `__post_init__` 校验。

| 参数 | 默认值 | 单位 | 合法范围 | 越界行为 | 代码位置 |
| --- | --- | --- | --- | --- | --- |
| `mode` | `"strict"` | 枚举 | `{"strict","coverage"}` | `ValueError: unsupported alignment mode: …` | 第 38、45–46 行 |
| `min_id_device_coverage` | `1.0` | 无量纲比例 | $0 < x \le 1$（开区间左端） | `ValueError: … must be in (0, 1], got …` | 第 39、47–52 行 |
| `min_device_id_coverage` | `1.0` | 无量纲比例 | $0 < x \le 1$ | 同上 | 第 40、47–52 行 |
| `zero_policy` | `"keep"` | 枚举 | `{"keep","drop","reject_device"}` | `ValueError: unsupported zero_policy: …` | 第 41、53–54 行 |
| `duplicate_policy` | `"reject_device"` | 枚举 | `{"reject_device","first"}` | `ValueError: unsupported duplicate_policy: …` | 第 42、55–56 行 |

补充说明：

- `mode` 与两个覆盖率阈值的**语义耦合**：`strict` 模式完全忽略两个 `min_*_coverage`
  （第 131–139 行走 `_strict_intersection`，不读这两个字段）；把 `mode` 留在 `strict`
  再调阈值不会有任何效果。
- 默认值 `1.0/1.0` 时，coverage 模式退化为“全体设备都有该 ID 且每台设备覆盖 100%”，
  即等价于 strict 的严格交集；但**算法路径不同**（coverage 会写 `no_consensus_bunch_ids` /
  `low_consensus_coverage` 而不是 `no_common_bunch_ids`），诊断文案也不同。
- 调用方各处的实际取值：
  - `RetrievalService.align_prepared`：未显式传入时用 `AlignmentParameters(mode="strict")`
    （`retrieval_service.py` 第 177–180 行）。
  - Agent HTTP API v2：`AlignmentParameters(**body.get('parameters', {}))`
    （`agent_v2_service.py` 第 614 行），即完全由请求体决定，缺省字段走默认值；
    设备数限制 1–64（第 520–521 行）。
  - GUI：经 `operator_backend` 走同一 `RetrievalService`，无额外覆盖。

### 4.2 对齐前原始编号间隔诊断（不是对齐参数，但会阻断/警告）

定义：`src/waveform_storage/processing/bunch_id_diagnostics.py:diagnose_raw_steps`（第 50–213 行）。
它是**只读证据**，不改变参与对齐的记录（模块 docstring 第 1–5 行）。

| 概念 | 定义 | 代码位置 |
| --- | --- | --- |
| 单设备可用相邻步 | 原始顺序下 `current > previous` 的差值（负/零差被丢弃） | 第 112–116 行 |
| 单设备众数步长 `modal_step` | 出现次数最多的差值；**并列最多则判为“无法确定”并记 issue** | 第 117–130 行 |
| 单设备 issue 触发条件 | 非整数值 / 越界 / 含零 / 含重复 / 点数<2 / 非严格递增 / 间隔非众数整数倍 / 众数并列 | 第 84–130 行 |
| 是否参与跨设备比较（eligible） | 严格递增 且 `modal_step` 非空 且 零值数=0 且 重复数=0 且 设备 ID 非空不重复 | 第 156–161 行 |
| 多数参考 `majority_step` | 在 eligible 设备中，某众数步长**严格过半**才成立；分母 ≥2 | 第 162–170 行 |
| `differs_from_majority` | 单设备 `modal_step` ≠ `majority_step` | 第 172–182 行 |
| `raw_step_compatible` | 有明确多数 且 无缺失 且 无设备与多数不一致 且 无 issue 且 eligible 覆盖全部请求设备 | 第 187–190 行 |

`RawStepReport.summary` 的四种文案（第 192–201 行）就是 GUI 诊断栏的直接文案来源：

| 条件 | summary |
| --- | --- |
| 无任何设备序列 | 未读取到原始设备序列；连续性无法确认 |
| 存在与多数不一致 | 相邻数据编号的间隔与多数设备不一致；时间基准待核实，连续性无法确认 |
| 无明确多数 | 无法确定多数设备的常见编号间隔；时间基准待核实，连续性无法确认 |
| 缺失或存在 issue | 原始设备数据不完整，或相邻编号间隔存在疑点；时间基准待核实，连续性无法确认 |
| 全部通过 | 各设备的常见编号间隔一致，其他间隔符合其整数倍；对齐后仍需检查数据是否连续 |

最后一条的“对齐后仍需检查数据是否连续”是**关键限定**：`raw_step_compatible=True` 不等于
时间连续，也不等于物理时钟一致。

### 4.3 采样率 $f_s$ 与采集频率档位

| 参数 | 默认值 | 单位 | 合法范围 | 越界行为 | 代码位置 |
| --- | --- | --- | --- | --- | --- |
| `frequency_hz`（协议层） | 请求必填 | Hz | 有限正实数（拒绝 `bool`/非数值/NaN/∞/≤0） | `ProtocolValidationError: frequency_hz must be a finite positive number` | `acquisition/protocol.py` 第 114–122 行 |
| `frequency_hz`（服务端白名单） | — | Hz | 精确命中 $\{1000, 500, 100, 50, 10, 5, 2\}$ | `ServerSettingsError: unsupported capture frequency … Hz; supported: …` | `acquisition/runtime.py:_CAPTURE_INTERVAL_SECONDS` 第 491–501 行、`capture_interval_seconds` 第 539–549 行 |
| GUI 默认请求频率 | `100` | Hz | 同协议层 | — | `gui/operator_backend.py` 第 55–61 行；`docs/CURRENT_STATUS.md` 第 5–7 行（采集页已改为只读显示 timing PV，不再有频率下拉框） |
| 历史分析采样率 | 无默认 | Hz | 有限正数；与 HDF5 记录冲突即失败 | `ValueError: 填写的采样率与文件记录不一致…` / `该 HDF5 没有采样率记录…` | `analysis/loaders.py:_sampling_rate` 第 136–150 行 |
| 历史分析采样率来源 | `capture_run_summary` | 枚举 | `{None, "capture_run_summary"}` | `ValueError: Unknown sampling-rate source` | `analysis/models.py:AnalysisRequest` 第 113–133 行 |
| `sample_rate_hz`（GUI 手动） | `0`（表示“读取文件记录”） | Hz | `>0` 且有限；与文件记录相对误差 $10^{-6}$ 内一致 | `AnalysisRequest` 报错 / `loaders` 冲突报错 | `gui/spectrum_panel.py` 第 111–114、287–303、350–367 行；`analysis/models.py` 第 129–133 行 |

**10 Hz 的具体位置**：`_CAPTURE_INTERVAL_SECONDS` 的 `10.0 → 2100` 是 2026-10-26 现场确认加入的
一档（`runtime.py` 第 496–498 行注释：与 5 Hz 相同的 20000 点段目标，$20000/10=2000$ s 加 5 Hz
余量）。该表是**现场规则，不做插值**——任何不在表内的频率被明确拒绝
（`docs/CURRENT_STATUS.md` 第 36–39 行“该表属于现场规则，不可插值”）。

**历史频率不得用当前机器频率替代**：`docs/agent-api-v2.md` 第 151 行
“采样率来自历史 `CaptureRunSummary.frequency_hz`。缺失或与 HDF5 冲突时失败，不读取当前机器
频率代替历史频率。”代码对应 `agent_service.py` 第 155–171 行。

### 4.4 timing PV 跟随与频率一致性

| 项 | 值/行为 | 代码位置 |
| --- | --- | --- |
| PV 名 | `AC-LA-INJ1-TIM:WRN1:MCFQ8` | `runtime.py:TIMING_FREQUENCY_PV` 第 503 行 |
| EPICS 地址 | `10.101.2.1:6310`（读该 PV 时临时设置 `EPICS_CA_ADDR_LIST` 且 `AUTO_ADDR_LIST=NO`） | 第 504、514–515 行；原文恢复在 `finally`（第 526–536 行） |
| 读取点 | `float(pv.read(timeout=timeout_seconds).data[0])` | 第 521 行 |
| 单次读取超时 | `timeout_seconds=10`（`read_timing_frequency` 形参默认值） | 第 507 行 |
| 服务端读取总超时 | `FREQUENCY_PV_RESPONSE_TIMEOUT_SECONDS = 20.0`，超时抛 `TimeoutError` | `acquisition/server.py` 第 50 行、`_read_frequency_bounded` 第 618–646 行 |
| 异构校验 | 读到频率后**先过一次白名单** `capture_interval_seconds(frequency)`；不在表内即失败 | `runtime.py` 第 522–525 行 |
| 拒绝条件（读数） | 非有限或 $\le 0$ → `ServerSettingsError("timing-system frequency PV returned an invalid value")` | 第 522–523 行 |
| 与请求一致性 | $\left\vert f_{\text{req}}-f_{\text{PV}}\right\vert \le \max\left(10^{-6},\ 10^{-6}\max(\vert f_{\text{req}}\vert,\vert f_{\text{PV}}\vert)\right)$（`math.isclose(rel_tol=1e-6, abs_tol=1e-6)`）；否则 `FREQUENCY_MISMATCH` | `server.py` 第 576–587 行 |
| 请求前是否读 | 是：`handle_message` 在提交任务前读 PV 并比对（幂等重试与忙碌请求**不**再读，第 554–560 行注释） | `server.py` 第 561–588 行 |
| 只读查询命令 | `get_timing_frequency` → payload `{"frequency_hz": …, "source": "timing_pv"}`；服务忙时 `SERVICE_BUSY`，未配置读取器时 `TIMING_FREQUENCY_UNAVAILABLE` | `server.py:_handle_timing_frequency` 第 590–616 行 |
| Agent HTTP | `GET /api/agent/v2/control/timing-frequency`，经同一后端读取 | `application/agent_v2_http.py` 第 190–194 行；`docs/agent-api-v2.md` 第 172 行 |

**“跟随”的精确含义（重要，避免误判）**：这是**开环、请求级、单次采样**的读取与校验，
不是闭环跟踪：

- 每个请求**读一次**，然后与该请求的 `frequency_hz` 比对，一致才提交（上表）；
- 运行期间**不重读** PV，也不按 PV 变化调整周期；
- 周期等待值 $I(f_s)$ 来自**请求的** `frequency_hz`（`runtime.py` 第 292 行
  `interval = capture_interval_seconds(plan.frequency_hz)`），不是来自 PV 读数；
- GUI 会在启动时读一次、采集前再读一次并跟随最新值（`docs/CURRENT_STATUS.md` 第 5–7 行），
  但**落盘元数据里的 `frequency_hz` 仍是请求值**（`runtime.py` 第 336 行）。

### 4.5 触发

| 项 | 实际实现 | 代码位置 |
| --- | --- | --- |
| 触发方式 | 对每台设备的 `capture_pv` 写 **0 → 1**，等待 `pulse_seconds`，再批量写 **0**（电平脉冲） | `transport/epics_gateway.py:EpicsGateway.trigger` 第 47–68 行 |
| 触发是否同步 | 所有已连接设备在同一 `Batch` 内写 0 与 1，随后**统一**等待并统一复位；没有逐设备时序图，也没有硬件触发链路 | 第 49–53 行（写入 + 等待）、第 60–63 行（复位） |
| 触发模式参数 | **不存在**。没有 internal/external/software 选择、没有延迟/提前量、没有极性配置 | `EpicsGateway.__init__` 第 17–30 行只有 `timeout`、`pulse_seconds`、`waiter`；`CaptureRequest` 无触发字段（`protocol.py` 第 97–106 行） |
| `epics_pulse_seconds` | 默认 `5` s，范围 1–60（环境变量 `WAVEFORM_EPICS_PULSE_SECONDS`） | `runtime.py` 第 52、130–136 行 |
| `epics_connect_timeout_seconds` | 默认 `10` s，范围 1–3600 | `runtime.py` 第 51、123–129 行 |
| 单设备触发失败 | 该设备本周期记失败，`failure_stage="EPICS 触发"`，不影响其他设备 | `capture_service.py` 第 99–128、140–147 行 |
| 全部设备触发失败 | 直接返回全失败结果，不进入等待/下载 | 第 104–128 行 |
| 触发是否等待束流就绪 | 无相关逻辑 | 全模块无对应代码 |

**触发与 bunchID 的关系**：触发只决定“何时让设备开始写 TXT”，**不决定** bunchID 的编号
规则，也不参与对齐。系统不假设不同设备共享同一个触发时刻或同一编号基准。

### 4.6 时间基准、零点与段内时间轴

对齐结果**本身没有时间轴**（`AlignmentResult` 字段里没有时间，见 `alignment.py` 第 84–94 行）。
时间轴由分析层从对齐结果派生：

1. **前置硬条件**（`analysis/loaders.py:_id_times`，第 153–166 行）：
   - 一维整数数组；
   - 点数 $2 \le N \le 5{,}000{,}000$（`MAX_POINTS`，第 26 行）；
   - 不含 0（`np.any(ids == 0)` 即拒）；
   - 严格递增（`min(differences) <= 0` 即拒，错误文案“bunchID 必须唯一并严格递增，
     不能压缩或重排波形时基”）；
   - 所有相邻差值必须是**基准步长**的整数倍，否则错误文案
     “bunchID 间隔不是同一基本步长的整数倍，无法建立采样时间轴”。
2. **基准步长取众数**：`step = Counter(differences).most_common(1)[0][0]`（第 162 行）。
   注意：这里**没有**“众数并列则失败”的保护（与 4.2 的诊断不同），并列时按 `Counter`
   的插入序取第一个——这是当前实现的一个已知薄弱点，见第 6 节 U9。
3. **相对时间**（第 165–166 行）：

$$
\text{slots}_k=\frac{\mathrm{ID}_k-\mathrm{ID}_0}{\text{step}},\qquad
t_k=\frac{\text{slots}_k}{f_s}=\frac{\mathrm{ID}_k-\mathrm{ID}_0}{\text{step}\cdot f_s}
$$

4. **零点再归零**：`analysis/engine.py:_prepare` 第 53 行 `times = times - times[0]`，
   即最终时间轴的零点就是该段**第一个共同 bunchID**。
5. **墙钟不进时间轴**：段级 `captured_at` 只作为来源信息；`ChannelSeries.time_basis`
   在 HDF5/对齐来源下是相对时基，`utc_origin` 仅 Archiver 来源填充
   （`loaders.py` 第 169–200 行；`_archiver_frame` 第 51–78 行设 `time_basis="utc"`）。
   `docs/spectrum-analysis-design.md` §“时间轴与质量规则”：“HDF5 保留相对时间；采集轮次
   开始时间只记为来源信息。”

**结论**：$t_k$ 只在**单段、单设备**内自洽；跨设备时，因为按**共同** bunchID 取列，
所有设备的 $t_k$ 使用同一 `ID_0`/`step`/$f_s$，故在“编号步进等于采样步进”的**假设**下才可
横向比较。这个假设**未被系统验证**，GUI 明确写“分析器根据对齐后的 bunchID 和当前采样率
建立相对时间轴；这不确认原始设备物理时钟一致性”
（`gui/operator_window.py:_refresh_history_diagnostic`，第 2242–2245 行）。

### 4.7 插值与重采样

对齐层**无插值**（第 3.5 节）。插值只发生在分析层，用于把非等间隔时间轴放到等间隔网格上：

| 项 | 值/行为 | 代码位置 |
| --- | --- | --- |
| 网格点数 | $N_{\text{grid}}=\left\lfloor t_{\max}\,f_s + 10^{-7}\right\rfloor + 1$ | `analysis/engine.py:_prepare` 第 79 行 |
| 网格 | $t^{\text{grid}}_i = i/f_s$，$i=0,\dots,N_{\text{grid}}-1$ | 第 82 行 `np.arange(count, dtype=float) / rate` |
| 插值方法 | **线性插值** `np.interp(grid, times, values)`（无 cubic、无 resample_poly、无 FFT 重采样） | 第 85 行 |
| 上限 | `MAX_RESAMPLED_POINTS = 5_000_000`，超限报错“重采样网格过大，请核对采样率和时间单位” | 第 18 行、第 80–81 行 |
| 短缺口 | 网格点数多于实测点数时用线性插值填补，统计量 `short_gap_fill_points = count - len(values)` | 第 84 行 |
| 长缺口 | **不插值**：`intervals.max() > max_gap_factor/rate + 1e-9` 直接报错“存在长采样缺口；本次未跨缺口插值，请选择连续数据段” | 第 73–74 行 |
| `max_gap_factor` | 默认 `5.0`，必须 $>1$ | `analysis/models.py:AnalysisConfig` 第 53、73 行 |
| 重复时间戳 | 先按时间稳定排序，再对重复时间取均值合并（`np.bincount/weights`） | `engine.py` 第 41–49 行 |
| 抖动告警 | `MAD(Δt) > 0.1/f_s` → 仅警告“采样抖动较大，等间隔插值可能影响高频结果” | 第 77–78 行 |
| Welch | 在重采样后的等间隔网格上计算 | 第 109 行 `welch_density(values, rate, …)` |

### 4.8 容差

| 场景 | 容差 | 说明 | 代码位置 |
| --- | --- | --- | --- |
| bunchID 对齐匹配 | **0（精确整数相等）** | 无阈值、无最近邻、无插值 | `alignment.py` 第 419–422 行 |
| coverage 覆盖率比较 | 精确浮点 `>=` | $\rho$ 直接与「重叠数 / 候选集大小」比较 | 第 372–373 行 |
| 频率一致性 | `isclose(rel_tol=1e-6, abs_tol=1e-6)` | 见 4.4 | `server.py` 第 576–581 行 |
| 采样率一致性 | `isclose(rel_tol=1e-6)`（无 abs_tol） | 文件记录 vs 用户填写 | `loaders.py` 第 143–146 行 |
| 长缺口判定 | $+\ 10^{-9}$ 的浮点余量 | `> max_gap_factor/rate + 1e-9` | `engine.py` 第 73 行 |
| 网格点数 | $+\ 10^{-7}$ 的浮点余量 | `floor(t*f_s + 1e-7)+1` | `engine.py` 第 79 行 |
| Nyquist 覆盖 | 无余量 | $f_s/2 \le f_{\text{search,high}}$ 报错；$f_s/2 < f_{\text{bg,high}}$ 报错 | `engine.py` 第 67–70 行 |

**易误判点**：把“对齐”理解成带容差的时间匹配，就会去找一个不存在的 `tolerance_ms` 参数。
系统里**没有毫秒级/微秒级时间容差**，只有上面这些浮点比较余量。

### 4.9 通道对齐顺序

| 顺序 | 规则 | 代码位置 |
| --- | --- | --- |
| 结果行（设备）顺序 | 按 `device_id` **字典序**（`prepared.sort(key=lambda item: item.device_id)`），与请求/查询中的设备顺序无关 | `alignment.py` 第 126 行 |
| 结果列（bunchID）顺序 | **升序**（strict 靠 `intersect1d`；coverage 靠 `np.unique`） | 第 340 行、第 403 行 |
| 检索阶段的设备顺序 | 按 `StorageQuery.device_ids` 的给定顺序排序待下载对（`order` 索引），这只影响下载后 `records` 的**输入**顺序，不影响对齐后的行顺序 | `retrieval_service.py:RetrievalService.prepare` 第 123、139 行 |
| 分析层的设备顺序 | 遍历 `result.x` 的行序（即上面的字典序），逐设备生成 `X`/`Y` 两个通道 | `loaders.py:_waveform_series` 第 180–200 行 |
| 非请求设备 | 有文件但不在 `device_ids` 里的设备记 `SkippedDevice(reason="unknown_device")` 并被丢弃 | `retrieval_service.py` 第 127–136 行 |

**可操作结论**：不要依赖“结果行序等于我请求里的设备顺序”；要按 `result.device_ids`
（元组）取值，它是唯一的行序事实源。

### 4.10 单位

| 量 | 单位 | 证据 |
| --- | --- | --- |
| `bunchID` | **无量纲整数**（`uint64`）。不是秒、毫秒、微秒、样点序号 | `hdf5_io.py` 第 76–80 行 `uint64`；GUI 明写“相邻采样点的 bunchID 差值，不是时间间隔”（`operator_window.py:RawStepDiagnosticsDialog.__init__` 第 394 行；`_confirm_raw_step_alignment` 第 1981 行） |
| `step`（基准步长） | 无量纲 ID 差值 | `loaders.py:_id_times` 第 162 行 |
| $t$（时间轴） | **秒**（相对量，零点=首个共同 bunchID） | `loaders.py` 第 165–166 行；`engine.py` 第 63 行 `duration_seconds` |
| $f_s$ | Hz | `protocol.py`；`loaders.py` |
| 周期等待 $I(f_s)$、`duration_seconds`、各类超时、`pulse_seconds` | **秒** | `runtime.py` 第 491–501 行；第 50–54 行 |
| `frequency_hz` 偏差比较 | Hz（相对/绝对各 $10^{-6}$） | `server.py` 第 576–581 行 |
| 频谱频率/分辨率 | Hz；dB | `engine.py` 第 112–114、104 行 |
| X/Y | **原始读数**（`int64`），默认无物理单位 | `hdf5_io.py` 第 81–82 行；注册表 `x_unit`/`y_unit`/`scale_factor` 默认 `None`（`config/registry.py` 第 56–58、129–132 行）；设计文档 §2“不定义未经现场确认的物理单位” |

**系统内没有使用毫秒或微秒作为任何字段的单位**；所有时间量都用秒或（分析结果的）Hz。
在文档、日志或问答里把 bunchID 差值写成“毫秒”属于单位错误。

---

## 5. 诊断手册

每条给出：**典型症状 → 判别步骤 → 期望观测 → 误判排除**。所有 `reason` 字符串都来自代码，
可据其直接检索。

### 5.1 对齐结果为空（0 个共同 bunchID）

- **症状**：`AlignmentResult.bunch_ids.size == 0`；GUI 显示“所选设备没有共同 bunchID”并阻止绘图/
  导出（`operator_window.py` 第 2289–2297、1168 行）；API 返回空的 `data_points`。
- **判别步骤**
  1. 看 `result.skipped_devices` 的 `reason`：`no_common_bunch_ids`（strict，第 135 行）/
     `no_consensus_bunch_ids`（coverage，第 357 行）/ 每设备的 `zero_bunch_id`、
     `duplicate_bunch_id`、`length_mismatch`、`invalid_array`、`empty_after_filter`
     （第 171–248 行）。
  2. 若全部设备 `status="usable"` 而交集为空，看 `quality_report[*].step_values`：**不同设备
     的最常见步长不同**会直接导致交集为 0（设计文档 §1 记录的现场情形：主覆盖簇 30 台、
     3 台 500000 步长但窗口错开、2 台 75/76 步长的 L1 冷 BPM、1 台 61/75/76 的 COL0 BPM）。
  3. 用 `diagnose_raw_steps` 的 `majority_step` / `differs_from_majority` 判断是“多数一致、少数
     错窗”（此时换 coverage 模式有意义）还是“无共识”。
- **期望观测**：strict 下错窗设备会让交集恰好等于“所有设备的公共窗口”；若窗口完全不相交，
  交集为 0 是**正确**结果，不是缺陷。
- **误判排除**：
  - “交集为 0 说明读取失败”——不是。读取失败会以 `fetch` 层的 `read_failed` 出现在
    `skipped_devices`（`ssh_storage.py:download_device_series` 第 291–294 行），
    `quality_report` 里也不会有该设备。
  - “交集为 0 说明设备坏”——不是。设计文档 §2 明确“不把不同步长或不同窗口自动判定为坏设备”。
  - 用 `MongoDB元数据模块设计.md` §5 的真实记录校准预期：同一 `11:00:23` 组的 10 个文件
    交集 1023；同一 `15:41:01` 组的 12 个文件**没有**全局公共 ID，严格对齐安全返回空
    （本次已本地复核前者：10 台、交集 1023）。

### 5.2 结果行数/列数比预期少

- **症状**：`result.device_ids` 少于请求设备；或 `bunch_ids.size` 远小于单设备点数。
- **判别步骤**
  1. 数 `skipped_devices` 逐条 `reason`：`file_not_found`（`retrieval_service.py` 第 147–150 行）、
     `unknown_device`（第 129–135 行）、`read_failed`（`ssh_storage.py` 第 291–294 行）。
  2. 若设备都在，用 `quality_report[*].original_count` / `usable_count` 看是否被清洗掉了点
     （`zero_policy="drop"` 或 `duplicate_policy="first"` 会减点）。
  3. 列数偏少通常是交集性质：`bunch_ids` 是**共同**列，不是并集。
- **期望观测**：`|device_ids| + |skipped_devices|` 覆盖全部请求设备（对 strict 成立；
  coverage 会额外追加 `low_consensus_coverage`）。
- **误判排除**：“点数少 = 采集丢包”——先看 `original_count` 是否本来就是 1024；若原始点数就
  不足，问题在 TXT 解析（`expected_points` 校验，`txt_parser.py` 第 48–51 行）而不在对齐。

### 5.3 设备被跳过：`duplicate_bunch_id`

- **症状**：默认参数下某设备整台消失，`reason="duplicate_bunch_id"`，`detail` 里 `duplicate_count=…`。
- **判别步骤**
  1. 确认 `duplicate_policy` 实际取值。默认 `reject_device`（`alignment.py` 第 42 行）→ 整台跳过；
     若为 `first`，则保留首次出现、不跳过（第 261–263 行）。
  2. 用 `quality_report` 的 `original_count` 与 `usable_count` 交叉验证。
- **期望观测**：`reject_device` 下该设备不参与交集，其他设备结果不受影响。
- **误判排除**：“重复 ID 一定来自采集端”——`_as_uint64_ids` 只转换不排序，重复是在排序后由
  `np.unique(return_counts=True)` 发现的（第 239–244 行），所以重复可能来自文件本身，也可能
  来自上游把多段拼进一个文件（这一条属推测，需查该文件来源，勿直接归因）。

### 5.4 设备被跳过：`zero_bunch_id`

- **症状**：`reason="zero_bunch_id"`，`detail="zero_count=…"`。
- **判别步骤**
  1. 确认 `zero_policy`。默认 `keep`（第 41 行）→ **不会**因 0 而跳过；只有
     `reject_device` 才跳（第 204–217 行），`drop` 则过滤 0 点后继续（第 218–220 行）。
  2. 若 `zero_policy="drop"` 后点数为 0 → 变成 `empty_after_filter`（第 222–233 行）。
- **期望观测**：`keep` 下 0 是一个合法 ID，会进入交集并可能使交集变小（若它只出现在一台设备上）。
- **误判排除**：
  - 别把 `zero_policy` 当成“X/Y 零值策略”。它对 X/Y 完全无作用（第 203 行只统计 `bunch_ids == 0`）。
    X/Y 双零的处理在分析层 `mask_double_zero`（`engine.py` 第 32–36 行）。
  - 时间轴侧则是**硬拒绝**含 0 ID 的序列（`loaders.py` 第 157–158 行），与对齐层的 `keep`
    默认值不同——两层的 0 值策略不一致，需要分别核对。

### 5.5 覆盖率模式收敛到很小的簇

- **症状**：coverage 模式返回的设备集合与直觉相反，小簇被保留、主簇被剔除。
- **判别步骤**
  1. 打印最终 `parameters`（随 `AlignmentResult` 一起返回，`alignment.py` 第 94 行；
     也写进 v2 文件属性 `parameters_json`，`hdf5_io.py` 第 158 行）确认两个阈值。
  2. 对每轮候选集合按 `_ids_at_coverage` 的公式手算 $r=\max(1,\lceil \rho_{\text{id}} n\rceil)$；
     $\rho_{\text{id}}$ 很小时 $r$ 会退化成 1（等于并集），$\rho_{\text{id}}=1$ 时是严格交集。
  3. 检查被剔除设备的 `detail` 里 `coverage=… required=…`（第 381–391 行）。
- **期望观测**：迭代单调收敛；每轮至少剔除一台设备，最多 $|\mathcal{D}|$ 轮。
- **误判排除**：
  - “coverage 会按输入顺序选簇”——不会。设备顺序在进入算法前已按 `device_id` 排序
    （第 126 行），且 `docs/数据对齐v2设计.md` §3 明确“不会按输入顺序任选四舍五入出一个结果”。
  - “coverage 结果可以写 legacy 文件”——不能。存在缺失单元时 `write_legacy_merged_hdf5`
    直接抛 `Hdf5SchemaError("legacy merged schema cannot represent missing aligned values")`
    （第 251–254 行）；`RetrievalService.export` 的 `auto` 也会改选 v2（第 231–232 行）。

### 5.6 绘图/导出出现可疑的 0 值台阶

- **症状**：波形里出现一整段 0，怀疑采集异常。
- **判别步骤**
  1. 看 `valid_mask` 对应位置：`False` 处的 0 是**占位**，不是测量
     （`alignment.py` 第 414–416 行；设计文档 §4 末段）。
  2. 若 `valid_mask=True` 且 X/Y 都为 0，那是真实读数（设计文档 §2“X/Y 为 0 是合法数据”），
     分析层默认 `zero_policy="keep"` 保留它们。
- **期望观测**：strict 模式 `valid_mask` 全 True；coverage 模式才可能出现 False。
- **误判排除**：不要用 `np.count_nonzero(x==0)` 判断缺失——必须用掩码。legacy 文件没有掩码，
  所以 legacy 路径在存在缺失单元时被设计为拒绝写入（见上条）。

### 5.7 原始编号间隔异常告警（对齐前的阻断弹窗）

- **症状**：GUI 弹“相邻数据编号的间隔与多数设备不一致…”，需人工确认才继续。
- **判别步骤**
  1. 读弹窗/诊断栏：`report.summary` 属 4.2 表里的哪一条；`majority_step` 及
     `majority_count/majority_denominator`。
  2. 逐设备看 `minimum_step～maximum_step` 与 `modal_step(次数/总数)`（诊断表列定义见
     `operator_window.py:RawStepDiagnosticsDialog.__init__` 第 376–392 行）。
  3. 设备是否严格递增：不递增的会进 `issue`（"原始 bunchID 未严格递增"，第 109–110 行）
     并被排除出多数参考（第 156–161 行）。
- **期望观测**：真实现场案例（`docs/CURRENT_STATUS.md` 第 169 行）：25 台可读设备、
  每台 20000 点；目标设备 `AC_LA_L1_BI_COLDBPM05` 相邻差 28～76，其余 24 台观测步进 2000；
  5 段严格共同点数为 422/621/455/375/288；任务记录 500 Hz，分析器推算跨度
  0.574～1.240 s，均未达 5 s 频谱准入时长。
- **误判排除**：
  - 告警**不阻断**算法：确认后仍执行 strict 对齐、**保留全部所选 BPM**、不自动剔除或缩放
    （弹窗文案 `operator_window.py` 第 1981–1986 行）。
  - `raw_step_compatible=True` 不等于连续：summary 末句“对齐后仍需检查数据是否连续”。
  - 单设备时“多数参考无法确定”是**正常**观测（分母 <2 时 `has_clear_majority=False`，
    第 166 行），不是设备故障。

### 5.8 频谱分析报“无法分析/采样率无效/时长不足”

这些不是对齐失败，但经常与对齐结果一起出现，按顺序排除：

| 报错文案（代码原文） | 判别要点 | 代码位置 |
| --- | --- | --- |
| `该 HDF5 没有采样率记录，请填写该次采集的实际采样率` | HDF5 缺 `sample_rate_hz`/`frequency_hz`，且调用方未提供 | `loaders.py` 第 148–150 行 |
| `填写的采样率与文件记录不一致，请核对该次采集` | 文件记录与显式值相对差 > $10^{-6}$ | `loaders.py` 第 143–146 行 |
| `bunchID 必须唯一并严格递增，不能压缩或重排波形时基` | 对齐结果的 `bunch_ids` 必须已升序唯一；strict/coverage 输出天然满足，手工造的数据可能不满足 | `loaders.py` 第 160–161 行 |
| `bunchID 间隔不是同一基本步长的整数倍，无法建立采样时间轴` | 存在“跨设备的编号体系差异”被带进同一序列，或原设备存在跳号 | `loaders.py` 第 163–164 行 |
| `bunchID 点数无效或含零 ID，请核对原始数据` | 含 0 ID（对齐层可能 `keep` 了它）或点数越界 | `loaders.py` 第 157–158 行 |
| `连续记录时长不足：… 秒 < … 秒` | 对齐后跨度太短；**跨度是按 $t_k$ 算的，不是点数除以采样率** | `engine.py` 第 71–72 行 |
| `存在长采样缺口；本次未跨缺口插值，请选择连续数据段` | 缺口 > `max_gap_factor/f_s` | `engine.py` 第 73–74 行 |
| `Nyquist 频率不能完整覆盖搜索频带` / `…背景频带` | $f_s/2$ 与模板频带不匹配 | `engine.py` 第 67–70 行 |
| `常值序列无法分析频谱` | `np.ptp(values)` 近 0 | `engine.py` 第 75–76 行 |
| `重采样网格过大，请核对采样率和时间单位` | $N_{\text{grid}} > 5\times10^6$，通常是把 Hz 填成了 kHz 或把秒填成毫秒 | `engine.py` 第 80–81 行 |

**最重要的误判排除**：`docs/CURRENT_STATUS.md` 第 169 行明确记录
“该推算不把 bunchID 当作时钟，也不把点数除以采样率当作连续时长”。因此
“$N$ 点 / $f_s$” **不是**该段的真实时长；真实跨度必须按 4.6 节的 $t_k$ 公式算。

### 5.9 频率相关采集被拒

| 错误码/文案 | 含义 | 下一步 | 代码位置 |
| --- | --- | --- | --- |
| `TIMING_FREQUENCY_FAILED: unsupported capture frequency 10 Hz; supported: … Hz` | 该频率不在 `_CAPTURE_INTERVAL_SECONDS` 表内 | 只能选表内档位；**不要插值或改小数** | `runtime.py` 第 539–549 行 |
| `FREQUENCY_MISMATCH` | 请求频率与 PV 读数不一致（超 $10^{-6}$ 相对/绝对） | 重新读 `get_timing_frequency`，让请求跟随实际值 | `server.py` 第 582–587 行 |
| `TIMING_FREQUENCY_FAILED: timing frequency PV read failed: …` | PV 读取异常/超时（总限 20 s） | 查 EPICS 地址 `10.101.2.1:6310` 与 PV 名 | `server.py` 第 561–569 行、第 50 行 |
| `SERVICE_BUSY`（`get_timing_frequency`） | 有采集任务在跑，只读查询被拒 | 等任务结束 | `server.py` 第 593–598 行 |
| `TIMING_FREQUENCY_UNAVAILABLE` | 服务未配置频率读取器 | 检查启动装配 | `server.py` 第 599–604 行 |

**历史教训（真实事件）**：`docs/CURRENT_STATUS.md` 第 25–39 行记录了 10 Hz 事故——
PV 读数 `10 Hz` 正常，但白名单表缺 10 Hz，导致 `read_timing_frequency()` 在返回前失败，
服务端返回 `TIMING_FREQUENCY_FAILED`，GUI 显示“暂不可用”，且同一校验挡在 GUI
`start_capture`、Agent v2 `control/captures` 和服务端 `handle()` 三处。修复方式是把
`10.0: 2100` 加入表，**不是**放宽校验。

---

## 6. 已实现能力 vs 未实现/规划

### 6.1 系统已有能力（逐条可核验）

| # | 能力 | 核验位置 |
| --- | --- | --- |
| C1 | 整数 bunchID 严格交集对齐（默认模式） | `alignment.py:align_devices` 第 131–139 行、`_strict_intersection` 第 337–343 行 |
| C2 | coverage 共识对齐（两档覆盖率阈值 + 迭代替换） | 第 140–144、346–404 行 |
| C3 | 零值/重复 ID 策略（各 2–3 档） | 第 41–42、203–263 行 |
| C4 | 逐设备质量报告与逐设备跳过原因 | `DeviceQuality` 第 59–72 行、`_prepare_records` 第 274–285 行 |
| C5 | `valid_mask` 区分缺失与真实 0 | 第 91、414–426 行 |
| C6 | 对齐前置原始编号间隔诊断 + 多数参考 + 人工确认 | `bunch_id_diagnostics.py` 全模块；GUI `_confirm_raw_step_alignment` 第 1953 行 |
| C7 | 对齐结果 v2 / legacy 双 schema 读写 + 原子替换 | `hdf5_io.py` 第 139–341 行 |
| C8 | 一次查询内复用同一 `AlignmentResult`（缓存键含 request_id+sequence） | `retrieval_service.py` 第 30–68、204–206 行 |
| C9 | 导出格式选择 `auto/legacy/v2`（`auto` 依 `valid_mask` 决策） | 第 221–232 行 |
| C10 | 从对齐结果派生相对时间轴并做频谱分析 | `loaders.py:_id_times`、`engine.py:_prepare` |
| C11 | 单文件对齐算法源码摘要（`algorithm_source_sha256`） | `agent_v2_service.py` 第 48–54、618–619 行 |
| C12 | Agent HTTP API v2 异步对齐任务 + provenance + 附件 | `agent_v2_service.py` 第 600–640 行；`docs/agent-api-v2.md` §Read API |

### 6.2 尚未实现 / 规划中（不得说成已有）

| # | 未实现项 | 证据 | 若要做的前置条件 |
| --- | --- | --- | --- |
| U1 | 段间（跨 `capture_sequence`）对齐或拼接 | `AGENTS.md` 第 23 行；`CURRENT_STATUS.md` 第 276–278 行；`StorageQuery` 强制一段 | 需先定义段间时间基准与汇总方法 |
| U2 | 整任务级频谱/统计汇总 | `AGENTS.md` 第 23 行“本次发布规范不实现整任务分析” | 逐段计算 + 明确汇总方法 |
| U3 | 带容差的时间对齐 | 对齐层无容差参数（第 4.8 节） | 需物理时钟基准，当前被设计明确排除 |
| U4 | bunchID → 物理时钟/绝对时间的换算 | `docs/数据对齐v2设计.md` §2“不猜测…时钟换算”；`loaders.py` 第 161 条直接报错 | 需现场确认各设备编号体系 |
| U5 | 重采样/插值式对齐 | `alignment.py` 模块 docstring；第 3.5 节 | 同上 |
| U6 | 自动对齐（无需操作员/调用方触发） | GUI 需点击 + 异常确认；API 需显式 POST | 需误对齐风险控制方案 |
| U7 | 独立对齐真实 fixture 重放现场主簇/错窗簇/异步长簇 | `docs/数据对齐v2设计.md` §6 第 1 条列为“进入现场前仍需要” | 脱敏真实 fixture |
| U8 | 覆盖率阈值与不同 bunchID 体系语义的现场确认 | 同上第 2 条 | 现场负责人裁决 |
| U9 | 时间轴基准步长的并列众数保护 | `loaders.py:_id_times` 用 `Counter.most_common(1)` 取第一个，无并列检测；而诊断层 `bunch_id_diagnostics.py` 第 121–130 行**有**并列检测。两层保护不一致 | 一处即可：把并列判为不可建轴 |
| U10 | 字段名 `alignment_algo_hash` 本身 | 第 1.1 节：系统无此字段名，但有等价的 `algorithm_source_sha256`；front-matter 取该值 | 若系统未来正式定义该字段名，按系统定义替换 |
| U11 | 段内逐采样点时间戳 | 每文件仅一个段级 `captured_at`（数据流文档第 3.3 节） | 需设备侧提供 |

---

## 7. 文档-代码差异

以代码为准。仅列与“对齐语义/参数/诊断”直接相关的条目。

| # | 文档说什么 | 代码实际做什么 | 证据 |
| --- | --- | --- | --- |
| A1 | `docs/数据对齐v2设计.md` §2：“X/Y 为 0 是合法数据，通过 `valid_mask` 与缺失值区分”（易被读成 `zero_policy` 管 X/Y） | `zero_policy` 只作用于 **`bunchID == 0`**；X/Y 零值既不参与对齐决策，也不影响 `valid_mask`。X/Y 双零的排除在分析层 `zero_policy="mask_double_zero"` | `alignment.py` 第 203 行；`analysis/models.py` 第 54、77–78 行；`engine.py` 第 32–36 行 |
| A2 | `docs/数据对齐v2设计.md` §3 只文档化两个覆盖率阈值，未提 `zero_policy`/`duplicate_policy` | 这两个参数有默认值且默认行为会**整台剔除设备**（`reject_device`），对结果影响比阈值更大 | `alignment.py` 第 41–42 行；第 204–217、245–260 行 |
| A3 | `docs/数据对齐v2设计.md` §2“输入乱序会稳定排序” | 确实稳定排序，但 `was_strictly_increasing` 记录的是**排序前**的原始顺序；因此“乱序输入”在对齐里被容忍、在诊断里被排除出多数参考并可触发告警 | `alignment.py` 第 235–237 行 vs `bunch_id_diagnostics.py` 第 104–110、156–161 行 |
| A4 | `docs/数据对齐v2设计.md` §6：导出 `auto` 依缺失单元选 v2 | 带 `request_id` 的导出**强制** v2，显式 `legacy` 被覆盖；仅无 `request_id` 时 `auto` 才生效 | `retrieval_service.py` 第 231–238 行 |
| A5 | `docs/数据对齐v2设计.md` §1 描述现场 36 台设备、每台 1024 个 bunchID、全设备交集 0（2025-11-12 12:07:21） | 该数值本文**未复现**（本地样本为 2025-11-12 的 22 个文件、两组各 10/12 台，11:00:23 组交集 1023 已复核）。§1 的 36 台/交集 0 属既有文档记载，本次未独立核验 | `docs/数据对齐v2设计.md` 第 8–16 行；本地 `data/samples/20251112/` 只读计算 |
| A6 | `docs/spectrum-analysis-design.md` §“时间轴与质量规则”：“短缺口可按参数插值” | 插值是 `np.interp` **线性**插值，且不区分“短缺口”与“采样点缺失”——它把非等间隔轴重采样到 $i/f_s$ 网格；所谓“长缺口”由 `max_gap_factor/f_s` 单独判据直接报错 | `engine.py` 第 73–74、82–85 行 |
| A7 | `docs/agent-api-v2.md` 第 155 行称 alignment 的 `algorithm_version` “绑定现有 alignment 源码摘要” | 属实，但仅是**单文件**摘要，且系统明确拒绝把它当作“稳定源码文件集合”身份（频谱侧即因此删除该字段） | `agent_v2_service.py` 第 48–54、618–619、651–655 行 |
| A8 | `docs/CURRENT_STATUS.md` 第 169 行给出的段内推算跨度 0.574～1.240 s（500 Hz、422～288 个共同点） | 与 $\Delta t=1/500=2$ ms 自洽，且用的是**区间数**而非点数：$(288-1)\times2\,\text{ms}=0.574$ s、$(621-1)\times2\,\text{ms}=1.240$ s，与文档数值逐位吻合。但该一致性只在“编号步进 = 采样步进”假设下成立，文档本身也声明不把 bunchID 当时钟 | `docs/CURRENT_STATUS.md` 第 169 行；`loaders.py` 第 165–166 行（$t_{N-1}=(\mathrm{ID}_{N-1}-\mathrm{ID}_0)/(\text{step}\cdot f_s)$） |

---

## 8. 适用版本与核验范围

### 已核验（2026-10-29，只读）

| 类别 | 文件/内容 |
| --- | --- |
| 对齐核心 | `src/waveform_storage/processing/alignment.py`（全文 444 行逐行核对） |
| 对齐诊断 | `src/waveform_storage/processing/bunch_id_diagnostics.py`（全文 213 行） |
| 对齐编排 | `src/waveform_storage/application/retrieval_service.py`（第 1–260 行全文） |
| 对齐落盘 | `src/waveform_storage/io/hdf5_io.py`（第 1–341 行） |
| 时间轴/重采样 | `src/waveform_storage/analysis/loaders.py`（第 136–200 行）；`analysis/engine.py`（第 1–90 行）；`analysis/models.py`（第 38–133 行） |
| 采集频率/触发/timing PV | `src/waveform_storage/acquisition/runtime.py`（第 38–175、256–550 行）；`acquisition/server.py`（第 48–50、236–273、500–646 行）；`transport/epics_gateway.py`（全文 82 行） |
| 协议校验 | `src/waveform_storage/acquisition/protocol.py`（全文 582 行） |
| GUI 诊断文案 | `src/waveform_storage/gui/operator_window.py` 的 `RawStepDiagnosticsDialog.__init__`（第 333 行起）、`_confirm_raw_step_alignment`（第 1953 行起）、`_refresh_history_diagnostic`（第 2112 行起）；`gui/spectrum_panel.py`（采样率控件） |
| Agent 层 | `src/waveform_storage/application/agent_v2_service.py`（第 40–60、510–525、600–660 行） |
| 既有文档 | `docs/数据对齐v2设计.md`、`docs/agent-api-v2.md`、`docs/spectrum-analysis-design.md`、`docs/CURRENT_STATUS.md`、`docs/采集协议v2候选.md`、`AGENTS.md` |
| 哈希计算 | 4 个源文件的单文件 sha256 与组合 sha256（本地只读计算，两次独立方法交叉验证：`sha256sum` 管道与 Python `hashlib`） |
| 真实数据 | `data/samples/20251112/` 的 10 个 `RAW-110023-*` 文件：shape/dtype/相邻步长/严格交集（1023） |

### 未核验（不得据此推断）

- **未运行任何测试**：`tests/test_alignment.py`、`tests/test_waveform_agent_v2.py` 等均未执行；
  未做发布验收、SHA-256 manifest 校验、二进制身份核验或真实桌面 smoke。
- **未执行 GUI 点击流**：诊断弹窗、诊断栏的文案取自源码字符串，未在真实界面上核对渲染效果。
- **未连接现场**：EPICS、timing PV、MongoDB、systemd 均未访问；`AC-LA-INJ1-TIM:WRN1:MCFQ8`
  的实际读数未取得（只在 `docs/CURRENT_STATUS.md` 找到 `10 Hz` 的历史记录）。
- **未做性能测量**：第 3.4 节的 $O(n^2)$ 是复杂度分析，不是实测耗时；系统无性能承诺。
- 未核验 `legacy/overlap_adapter.py`、`legacy/acquisition_agent_adapter.py` 中的历史对齐路径
  （本次只按需读了 `transport/ssh_storage.py` 的 `find_h5_files`）。若现场仍走 legacy 分支，
  其行为需另行核对。
- 未核验 `codex`/`AOCI` 描述与当前代码的一致性。
- 待核实（无法从代码唯一确定）：`runtime.py` 第 496–498 行注释“20000 triggers / 10 Hz = 2000 s”
  与“每周期一个文件”的对应关系；10 Hz、2100 s 的实际分段产出未在现场数据中验证。
