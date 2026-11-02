---
applicable_system_version: "waveform-storage-system@dc50e08 (2026-10-26, full dc50e08a2beddff42c297a237b3f3312f5c24ac9；工作树另有 1 个未提交修改 src/waveform_storage/application/agent_v2_service.py，不属于对齐路径，详见 §0)"
alignment_algo_hash: "e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346 (sha256 of src/waveform_storage/processing/alignment.py, size 15148；等价于系统既有字段 algorithm_source_sha256 / algorithm_version='bunch-id-alignment:e8db12d72a0ad553')"
verified_date: "2026-10-29"
owner: "未指派（待项目负责人裁决）"
---

# 历史故障记录与版本变更说明

> 本文件是 Phase 1 / M0 的 Waveform 核心运维文档之一。它只陈述**有原始证据支持的事实**，并把「已证实 / 推断 / 待核实」严格分开。
> 取证对象：`/home/whloong/waveform-storage/waveform-storage-system`（只读审计，未写入、未 commit、未重启任何服务）。
> 配套材料：结构化台账 `reports/phase1-m0-20261029/waveform-audit/cases.json`（12 条案例）、人读版 `…/cases.md`、证据定位 `…/evidence-index.md`、复算脚本 `…/verify_fixtures.py`。

---

## 0. front-matter 字段说明

本仓库**没有**定义 `applicable_system_version` / `alignment_algo_hash` / `verified_date` / `owner` 这四个字段名（在 `docs/` 全量检索零命中）。因此逐字段说明取值依据，避免被误当成系统内置元数据：

| 字段 | 仓库是否已有等价机制 | 本文件取值与依据 |
| --- | --- | --- |
| `applicable_system_version` | **部分有**。系统使用 `release_id` + `source_revision` + `source_manifest_sha256` + `binary_sha256`（见 `交付/*/BUILD-INFO`、`release-pair.json`、`docs/RELEASE_CHECKLIST.md`），但没有单一「系统版本」字段。 | 取审计基线的真实 git 提交：`git rev-parse HEAD` → `dc50e08a2beddff42c297a237b3f3312f5c24ac9`，日期由 `git log -1 --date=iso` 得出。**不编造版本号。** |
| `alignment_algo_hash` | **有，但字段名不同**。`src/waveform_storage/application/agent_v2_service.py:54` 计算 `alignment_source_hash = sha256(alignment.__file__ 的源码)`；`:618-619` 以 `algorithm_version='bunch-id-alignment:'+hash[:16]` 与 `algorithm_source_sha256=hash` 写入对齐 provenance。另有独立机制 `.aoci/baseline.json` 逐文件记录 `sha256` / `normalized_sha256`。 | 取系统既有机制的**真实值**：`e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346`。两个独立机制互相印证（见下）。**这不是 Phase 1 新增定义**，只是把系统已有的 `algorithm_source_sha256` 映射到本字段名。 |
| `verified_date` | 无此字段。系统记录的是各次交付的 `built_at` / `verified_at`。 | `2026-10-29`（本次审计执行日期）。 |
| `owner` | 无此字段。`git` 提交作者为 `whloong`，但**作者 ≠ 文档责任人**。 | `未指派（待项目负责人裁决）`。**不编造人名。** |

### `alignment_algo_hash` 的精确定义、范围限制与重算命令

**输入文件清单（只有 1 个文件）**：

```text
src/waveform_storage/processing/alignment.py        size = 15148 bytes
```

**重算命令（任选其一，结果必须一致）**：

```bash
W=/home/whloong/waveform-storage/waveform-storage-system

# 方式 1：直接对工作树文件求哈希（系统 agent_v2_service.py:54 做的就是这件事）
sha256sum "$W/src/waveform_storage/processing/alignment.py"
# e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346

# 方式 2：对上表基线提交中的 blob 求哈希（可脱离工作树复现）
git -C "$W" show dc50e08:src/waveform_storage/processing/alignment.py | sha256sum
# 同上；git blob id = d829d3232f9e91979a7bd9f9f7ce93d1e4819442

# 方式 3：读 AOCI 基线（另一套独立机制的自证）
python3 -c "import json;print(json.load(open('$W/.aoci/baseline.json'))['files']['src/waveform_storage/processing/alignment.py']['sha256'])"
# e8db12d7…（与方式 1/2 一致）
```

**这个标识覆盖什么、不覆盖什么（引用时必须带上这句）**：

- ✅ 覆盖：`processing/alignment.py` 中的对齐纯函数（strict / coverage 两种模式、`valid_mask`、`skipped_devices`、`quality_report`、设备稳定排序）。
- ❌ **不覆盖**：`analysis/loaders.py:_id_times()`（把对齐后 bunchID 换算为相对时间轴的逻辑）、`analysis/engine.py`（采样率与跨度的推导）、`processing/bunch_id_diagnostics.py`（原始步长预检查）、`gui/operator_window.py`（历史页呈现）。
- 含义：**`alignment_algo_hash` 相同，不代表「时间基准 / 采样率 / 历史页呈现」相同。** 本文件第 1 节的版本时间线表明，这几块是分别独立变化的 —— 例如 2026-10-19 的改变全部发生在 hash 覆盖范围之外。

### 系统内既有的、与本字段**不等价**的身份标识

本文件**不**把这些标识当作 `alignment_algo_hash`，列出以防混淆：

| 标识 | 出处 | 语义 | 为什么不等价 |
| --- | --- | --- | --- |
| `release_id`（如 `20261026-timing-10hz-r1`） | `交付/*/BUILD-INFO` | 一次构建发布的日期化名字 | 一个 release 包含大量无关改动 |
| `source_revision` | 同上 | 构建时记录的上游提交 | 常配 `source_state=working-tree`，源码可能≠该提交（见案例 case-04） |
| `source_manifest_sha256` | 同上 | 全部源码输入的清单哈希 | 覆盖全仓库，粒度太粗，且受构建文件集影响 |
| `binary_sha256` | 同上 | 产物二进制哈希 | 与算法语义无对应关系，随构建环境变化 |
| AOCI Entry / Baseline `normalized_sha256` | `aoci.txt`、`aoci.meta.txt`、`.aoci/baseline.json` | 代码认知对象的逐文件身份 | 面向认知索引，不是对外契约字段；但它与 `algorithm_source_sha256` 在 `alignment.py` 上恰好一致（本文件用作交叉验证） |

---

## 1. 版本时间线

只保留与**对齐 / 时间基准 / 采样率 / 触发**相关的变更。「默认行为前后」列是本文件的引用锚点。

| 日期（+0800） | commit | 改了哪个文件 / 函数 | 默认行为：之前 → 之后 |
| --- | --- | --- | --- |
| 2026-07-24 20:27 | `e432d0b` | 项目基线 | legacy 顺序式对齐仍在默认路径上 |
| 2026-07-25 22:22 | `36a927b` | `processing/alignment.py`（新建） | 新增 Qt/SSH/HDF5 无关的对齐纯函数；支持 strict 与 coverage 两模式 → 「按输入顺序求交集、交集下降时跳过设备」不再是唯一路径 |
| 2026-07-25 22:44 | `0b5870c` | `legacy/overlap_adapter.py`（隔离） | legacy 重叠逻辑收进适配器 → 新对齐路径不再调用 legacy 算法 |
| 2026-07-25 22:48 | `3a76c39` | `application/retrieval_service.py`（新增） | 对齐入口收口到应用服务，GUI 不再持有算法细节 |
| **2026-08-26 15:32** | `89bb146` | `acquisition/runtime.py:477-482` | **国庆前最后一个提交**：`_CAPTURE_INTERVAL_SECONDS` = `{1000:2, 100:12, 50:22, 2:512}`；legacy 代理仅 `100/50/1000/2` 分支 |
| *2026-08-26 → 2026-10-07* | — | — | **41 天 23 小时零提交**（本文件第 6 节的核心证据） |
| **2026-10-07 16:30** | `61b47db` | ① `acquisition/server.py`（新增 `FREQUENCY_MISMATCH`）<br>② `acquisition/runtime.py`（补 `500.0:4`、`5.0:4200`）<br>③ `gui/operator_window.py:1243-1248`（新增 `(末 bunchID − 首 bunchID)/1_000_000` 当秒数） | ① **服务端提交前开始校验「请求频率 == timing PV」**，不一致拒绝（此前无此校验）<br>② 支持档位 4 → 6，仍无 10 Hz<br>③ 历史页出现「数据时长：X s」（隐含「bunchID 是 1 MHz 计时钟且无缺口」的未声明假设） |
| 2026-10-08 15:55 | `dbbc0d6`（构建源 `51afde8`） | r4 版本对 | 段身份改为 `request_id + capture_sequence`；历史检索从「按时刻选」改为「按任务 + 段选」，禁止隐式拼接数据段；首次带 `BUILD-INFO` / `source_revision` |
| 2026-10-12 15:22 | `2be9026` | `gui/operator_window.py:791-796`、`:1690` | 时长逻辑重构为 `_duration_status_text()` 但**除式不变**（两处仍 `/ 1_000_000`） |
| 2026-10-13 12:09 | `368a9aa` | AOCI 快照 | `交付/20261016-history-quality-r1` 的 `source_revision` |
| **2026-10-19 10:14** | `f7f28fb` | 新增 `processing/bunch_id_diagnostics.py`（213 行）；`gui/operator_window.py`（+1075/−若干）；`analysis/engine.py`（+82）；`tests/test_formal_history_bpm_selection.py`（+305） | ① **移除 bunchID→秒 换算**，改显「分析器推算跨度」（来自 `_analysis_quality_preview.duration_seconds`）<br>② 对齐前强制**原始步长预检查**，步长异常必须显式确认才继续 strict 对齐<br>③ 保留全部设备，不自动剔除 / 不缩放 / 不插值<br>④ 文案区分「相邻数据编号的间隔」与「时间间隔」 |
| 2026-10-20 10:43 | `25e6b73` | `processing/alignment.py`（**仅** `DeviceSeries` 增加 `metadata` 字段）；新增 `algorithm_source_sha256` provenance | 对齐算法行为**不变**；首次对外暴露对齐算法源码哈希（即本文件 `alignment_algo_hash` 的来源） |
| 2026-10-22 16:47 | `5f17b67` | `application/agent_v2_service.py:54,618-619` | Agent API v2 的对齐产物写入 `algorithm_version` / `algorithm_source_sha256` |
| **2026-10-26 20:24** | `cae6b64` | `acquisition/runtime.py:498`（新增 `10.0: 2100`）；`gui/operator_window.py`（删除频率下拉框，采集前重读 PV 跟随） | ① 10 Hz 从「拒绝」变「支持」（此前后台整条 v2 采集通道在 10 Hz 下不可用）<br>② **前端不再允许指定采集频率**，消除频率漂移窗口；服务端频率校验保留 |

**时间线读法（重要）**：与「对齐语义」真正相关的代码只在 2026-07-25 建立、2026-10-19 修补呈现层；**国庆前后（2026-10-01 ~ 10-08）没有任何对齐算法改动**。国庆后变的是「历史检索与时间基准呈现」，不是对齐算法。

**关于 10 Hz 的额外校准（2026-10-29 由 EPICS Archiver 补入）**：10 Hz **不是**国庆后才出现的新频率。Archiver 显示 `AC-LA-INJ1-TIM:WRN1:MCFQ8` 至少自 **2026-08-17** 起就在 2/5/10/20/50/100/1000 Hz 之间反复跳变，10 Hz 在 08-17、08-27、08-28、09-04、10-01、10-23、10-27 均有记录（case-09）。因此 `cae6b64` 是**补支持**，不是对假期后新状态的反应 —— 时间线上不应把该改动当作「国庆后现象」。

---

## 2. 案例逐条

> 12 条案例，编号与本仓库 `cases.json` 一致。每条给出：现象 / 触发 / 影响 / 版本 / 预期 vs 实际 / 根因证据 / 替代解释 / 修复与验证 / 未决。
> 所有 `文件:行` 若无特别说明均指审计基线 `dc50e08`；已删除代码用 `git show <sha>:<path>` 形式给出，**引用时必须带 sha**。

### case-01　2025-11-12 批次 36 台严格 bunchID 交集为 0　`已证实`

- **现象**：同一批 36 台设备 HDF5 形状/dtype/长度一致，但全设备严格共同 bunchID 数为 **0**。约 30 台构成主覆盖簇；3 台同为 500,000 步长但窗口完全错开；2 台 L1 冷 BPM 步长 ~75/76；1 台 COL0 步长 61/75/76。
- **触发**：对异构 bunchID 空间执行「按输入顺序求交集、交集下降时跳过设备」的顺序式算法。
- **影响**：输入顺序变成隐式业务规则，可能保留小簇而排除主簇 → 对齐结果不可重复、不可解释。
- **版本**：`e432d0b`（2026-07-24 基线）仍含 legacy 顺序式路径。
- **预期 vs 实际**：预期同批设备有可用共同集 → 实际为 0。
- **根因证据**：`docs/history/2026-07/线上运行基线调查.md`（调查 2026-07-25，对真实文件 `RAW-120721-AC_LA_INJ1_BI_SBPM08-S00000.h5` 做只读 `h5dump`，SHA-256 `49c0f6abccff15d7f356f6ca39003f7ee77f8926d004e5edbdc95dc360fc8e88`）；`docs/问题清单与改进路线.md:132-160`（WF-006）；`docs/数据对齐v2设计.md:1-20,40`。
- **替代解释**：「3 台是坏设备」——被文档明确否认：不同步长只说明存在不同编码或时基，不足以判定设备为坏设备。
- **修复与验证**：`36a927b`/`0b5870c`/`3a76c39`（2026-07-25）把对齐改为纯函数 + strict/coverage 双模式 + 输出 `valid_mask`/`skipped_devices`/`quality_report` + 设备按 `device_id` 稳定排序。验证为 `tests/test_alignment.py`（空输入、单设备、无交集、含 0、重复、乱序、异常长度、冲突簇）。
- **未决**：不同 bunchID 编码体系的物理语义；覆盖率阈值 —— 两者均未与现场确认（`docs/数据对齐v2设计.md` 第 6 节列为进入现场前的前置条件，至今无结论）。

### case-02　2026-10-02 真实采集 20 台中 18 台零字节　`已证实`

- **现象**：`request_id=24fbc7de-eec1-4e25-a50f-6f4f29fd6c46`，INJ1 20 台，5 Hz，`expected_points=20000`，`duration_seconds=4200`。23:06:07 确认 running，预期 00:13:08 结束，实际 00:13:10 结束；终态 failed，`error_code=PARTIAL_DEVICE_FAILURE`，`message="18 of 20 device(s) failed"`。`failed_source_files_zero_bytes` 列出 SBPM03–SBPM20 共 18 台；`verified_hdf5_points={SBPM01:20000, SBPM02:20000}`。
- **触发**：5 Hz / 4200 s 的 20 台设备采集；18 台报 `no completed matching file`。
- **影响**：该段可用设备从 20 台降为 **2 台** → 后续跨设备对齐只能基于 2 台。这是「部分成功段」在现实中的样子（与测试构造的部分成功场景须分开，见 `cases.md` 第 3 节）。
- **版本**：名义 `89bb146`（2026-08-26），但部署与该提交不一致（见 case-04）。
- **预期 vs 实际**：预期 20 台各产 20000 点 → 实际 2 台成功、18 台零字节、任务 failed 但 2 台数据已落盘。
- **根因证据**：`logs/capture-BI-5Hz-20000-70min-20261002-230306-24fbc7de-eec1-4e25-a50f-6f4f29fd6c46.json`（`device_results` 20 条 + `failed_source_files_zero_bytes` 18 条 + 真实落盘路径 `/SHINE_Data/AC/LA/20261002/raw/BIData/`）。同类现象：`docs/handoffs/TASK_HANDOFF_2026-08-28_17-17-38_UTC+0800.md`（47 台全 `no completed matching file`；五区抽样 `/home/data/bram_result.txt` 均 0 字节，mtime 停在 2026-08-26）。
- **替代解释**：① 设备侧 BRAM 未写入 —— `docs/handoffs/TASK_HANDOFF_2026-08-27_14-17-05_UTC+0800.md` 记录 `fpga_test()` 无条件 `return 0` 而 `task4()` 仍打印 `Data Save Done`，会掩盖失败；交接标为 `[Inference]`，**不是定论**。② 采集端等待/校验不足 —— 已被否定：600 s 内 893 个设备轮次仍无有效文件，且绕过 Candidate 用设备本机 `caput` 同样为空。③ 零字节是 `fopen(...,"w")` 后无数据留下的残迹 —— 交接记录为 `[Fact]`。
- **修复与验证**：设备侧根因不在本仓库（越界，未修复）。系统侧应对：段身份 `request_id + capture_sequence`、历史页按任务/段选择、禁止隐式拼接（r4 起）。验证：日志自带逐设备错误与实际落盘路径，可与 `/SHINE_Data` 交叉核对。
- **未决**：18 台零字节的设备侧真实根因未由设备组确认。

### case-03　2026-10-02 采集被服务关停中断　`已证实`

- **现象**：`request_id=5c9321c5-35d8-4075-80b3-4b3111afebf4`，100 Hz / 1800 s；22:16:33 提交 → 22:19:40 `running` → **22:20:27 `cancelled`**，`message="capture cancelled during service shutdown"`，`latest_status=cancelled`。
- **触发**：采集任务运行期间采集服务被关停（部署/重启）。
- **影响**：启动约 4 分钟后被打断，无完整数据落盘，正在执行的设备轮次被打断。
- **版本**：名义 `89bb146`；实际部署不可考（case-04）。
- **预期 vs 实际**：预期跑满 1800 s 或被用户显式取消 → 实际被服务关停标记 cancelled。
- **根因证据**：`logs/capture-BI-20261002-221633-5c9321c5-35d8-4075-80b3-4b3111afebf4.json`。
- **替代解释**：① 用户主动取消 —— 不支持，文案明确是 service shutdown 而非 operator cancel；② 前端断开被误判取消 —— 不支持，后端任务独立线程执行，且 22:53 有第二个任务在同一服务上被接受（服务已重启）。
- **修复与验证**：未在仓库中找到专门修复。后续发布纪律要求「切换前确认无 accepted/running 任务」（`交付/20261026-timing-10hz-r1/evidence/deploy.deploy.sh` 的部署事务守卫）。无独立验证记录。
- **未决**：关停原因（部署 / 重启 / 崩溃）无记录；当时是否已有该守卫无法确认（部署版本 ≠ 任何提交）。

### case-04　现场部署无法用任何 git 提交定位　`已证实`

- **现象**：2026-10-02 22:53 的采集以 `frequency_hz=5.0` 被服务端 **accepted**；而国庆前最后提交 `89bb146` 的 `_CAPTURE_INTERVAL_SECONDS` 只有 `1000/100/50/2`，`legacy/adapter` 也只有 `100/50/1000/2` 四个分支 → 5 Hz 必然抛 `ServerSettingsError`。
- **触发**：把「git 历史」当作「现场部署历史」使用。
- **影响**：任何「某版本引入某缺陷 / 某版本修复某缺陷」的归因在 2026-10-02 前后都不成立；现场二进制身份与源码清单不可考。
- **版本**：`89bb146`（2026-08-26，仅 4 档）→ `61b47db`（2026-10-07，提交历史中首次出现 500/5 Hz）。
- **预期 vs 实际**：预期部署可由某提交或带 `BUILD-INFO` 的 release 唯一确定 → 实际无法确定；最早带 `release_id`+`source_revision`+`source_manifest_sha256` 的交付是 2026-10-08 的 r4。
- **根因证据**：`logs/capture-BI-5Hz-20000-20261002-225334-3d53c87f-f81e-46a7-b2fc-c9c5e7ba909a.json`（`frequency_hz=5.0`，`response.accepted=true`）；`git show 89bb146:src/waveform_storage/acquisition/runtime.py` 第 477-482 行；`git show 89bb146:src/waveform_storage/legacy/acquisition_agent_adapter.py` 第 367-380 行；`git log -S'4200' -- src/waveform_storage/acquisition/runtime.py`（仅命中 `61b47db`）；`交付/20261008-history-release-r4/operator/BUILD-INFO`。
- **替代解释**：① 5 Hz 由 `WAVEFORM_CAPTURE_FREQUENCY_HZ` 绕过 —— 不支持，该变量只覆盖 GUI 读取 PV 的步骤，服务端白名单仍会拒绝；② 日志是仿真产物 —— 不支持，落盘路径是真实 `/SHINE_Data/.../20261002/...` 且给出具体点数；③ 历史被改写/缺分支 —— 无法排除，但 `git log --all` 显示该区间零提交，且 `61b47db` 是一次超大合并提交（含 `config/devices.operator.json` 11496 行），与「长期未提交的现场改动一次性合并」一致。
- **修复与验证**：`61b47db` 合并现场工作树；发布流程自 r4 起引入 `BUILD-INFO` / `release-pair.json` / `source_manifest_sha256`。验证方式为本次审计的交叉比对。
- **未决**：2026-10-02 现场二进制 SHA-256 未知；`source_state=working-tree` 意味着即使有 `BUILD-INFO`，源码也不完全等于 `source_revision` —— 实证：r4 的 `operator_window.py` 清单哈希 `077e0aa4add65f10c5e8388b9bf62b80ced5f8837aa4180f8757685a77d6bab6`，而 `51afde8:src/waveform_storage/gui/operator_window.py` 的 blob SHA-256 是 `2bfd4068…`。

### case-05　2026-10-07 前服务端无「请求频率 vs timing PV」一致性校验　`已证实`

- **现象**：拒绝码 `FREQUENCY_MISMATCH` 及其判定逻辑**首次出现在 `61b47db`（2026-10-07 16:30:43）**。此前服务端 `handle()` 直接 `tasks.submit(request)`，不读 timing PV、不比对。
- **触发**：任何绕过正式 GUI 的客户端（运维客户端、脚本、旧前端）以与机器实际频率不一致的频率提交采集。
- **影响**：请求频率决定 `capture_interval_seconds()` 等待值与下游声明的采样率。若与机器实际频率不符，段内 20000 点覆盖的真实时长、以及任何由采样率推导的时间轴/频谱频率轴都会按**错误比例**解释 —— 这是「时基偏移」最典型的发生机制。
- **版本**：`89bb146`（无校验）→ `61b47db`（引入校验）→ `cae6b64`（前端不再允许指定频率）。
- **预期 vs 实际**：预期服务端在接受前比对 → 实际 2026-10-07 前无此校验；此后 `src/waveform_storage/acquisition/server.py:561-589` 读 PV 并 `math.isclose(rel_tol=1e-6, abs_tol=1e-6)` 比对，不一致返回 `FREQUENCY_MISMATCH`（`:586`）。
- **根因证据**：`git log --all -S'FREQUENCY_MISMATCH'`（唯一命中 `61b47db`）；`server.py:561-589`；`apps/acquisition_server/main.py:146`；`runtime.py:292`。
- **替代解释**：「客户端校验即可」不成立 —— 正式 GUI 确实校验（`apps/operator_gui/candidate_backend.py:85-91`，不一致抛 `RuntimeError` 且不发请求），但覆盖不到运维客户端/脚本路径。
- **修复与验证**：`61b47db` 服务端强制校验 + `cae6b64` 前端跟随 PV。验证：`tests/test_acquisition_server.py`、`tests/test_waveform_agent_v2.py`；286 项质量门 `OK`（`交付/20261026-timing-10hz-r1/evidence/quality.log`）。
- **未决**：2026-10-07 之前完成的采集是否曾以不一致频率提交 —— 无法核实，该期间无 timing PV 读数记录。另：`apps/operator_gui/experimental_backend.py:79` 在 HEAD 仍读 `WAVEFORM_CAPTURE_FREQUENCY_HZ`（实验 GUI 路径），说明覆盖机制未在全部入口消失。

### case-06　历史页把 bunchID 差值 ÷10⁶ 当「数据时长（秒）」　`已证实`

- **现象**：对齐完成后显示「数据时长：X.XXXXXX s」，控件 tooltip 写「最后一个 bunch ID 减第一个 bunch ID，换算为秒」；实现为 `seconds = (int(ids[-1]) - int(ids[0])) / 1_000_000`。
- **触发**：任意一次多设备严格对齐完成后刷新数据时长标签。
- **影响**：该数值被用来判断「本次采集有多长」以及是否满足频谱最短时长门槛。它隐含一个**未声明**假设：bunchID 是 1 MHz 计时钟且序列无缺口。步长不属于该假设、或 ID 有缺口时，显示的秒数会偏离真实记录时长。
- **版本**：引入 `61b47db`（2026-10-07，`operator_window.py:1243-1248`，tooltip `:572-574`）→ `2be9026`（2026-10-12，重构为 `_duration_status_text()`，`:791-796` 与 `:1690` 两处仍 `/1_000_000`）→ `51afde8`（r4 的 `source_revision`，第 1271 行仍含该式）→ **移除于 `f7f28fb`（2026-10-19）**。
- **预期 vs 实际**：预期时长来自真实时间轴或任务记录的实际采集时长 → 实际为硬编码 `1_000_000` 除法，代码中无注释、无出处、不读采样率也不读任务时长，tooltip 却声称已「换算为秒」。
- **根因证据**：`git show 61b47db:src/waveform_storage/gui/operator_window.py` 第 572-574、1243-1248 行；`git show 2be9026:…` 第 791-796、1690 行；`git show 51afde8:…` 第 1271 行；HEAD `src/waveform_storage/gui/operator_window.py:1047-1058`（已改为「分析器推算跨度」）；`git show f7f28fb:…`（新 tooltip「来自分析器建立的相对时间轴；不是 bunchID 数值换算结果」）。
- **替代解释（必须写清，否则会误判）**：**这个除法并非总是错的。** 若 bunchID 是 1 MHz 计时钟，`(末−首)/1e6` 就是秒。本次审计在真实 fixture 上验证：2026-10-12 任务 seq0 主流设备原始跨度 `(末−首)/1e6 = 39.998 s`，而 `20000 点 / 500 Hz = 40.000 s`，两者一致 —— 说明对步长 2000、500 Hz 的主簇设备该换算成立。缺陷在于：① 假设未声明；② 对步长 28–76 的 `AC_LA_L1_BI_COLDBPM05` 不成立；③ 无缺口检查时会高估时长。
- **修复与验证**：`f7f28fb` 改显「分析器推算跨度」（取 `_analysis_quality_preview.duration_seconds`），新增 `processing/bunch_id_diagnostics.py`（模块 docstring：*never converts bunchID values to time*），弹窗明确「相邻采样点的 bunchID 差值，不是时间间隔」。验证：241 项完整质量门（`交付/20261016-history-quality-r1/evidence/full-quality.log`）、4 项 `bunch_id_diagnostics` 测试、8 张双分辨率 offscreen 截图、`docs/CURRENT_STATUS.md:121` 记录文案变更。
- **未决**：① 2026-10-07 至 10-18 窗口内是否有操作员据错误秒数做判断 —— 仓库无操作日志、无用户报告；② HEAD 的「分析器推算跨度」仍有残余风险：`analysis/loaders.py:153-166`（`_id_times`）用「众数步长 ≡ 一个采样周期」建相对时间轴（`slots=(id−id[0])/step`、`times=slots/sample_rate`），共同 ID 集合带缺口时缺口会被压缩而非保留为间隔 —— 本案例 5 段均为连续窗口，未受影响。

### case-07　2026-10-12 任务 25 台严格交集塌缩至 1.44%–3.11%　`已证实`

> 本次审计范围内**唯一**「国庆后真实数据出现严重对齐异常」的原始证据。

- **现象**：`request_id=22833275-5e77-41c5-b703-f306accde164`（存储日期 2026-10-12，采样率 500 Hz，5 个数据段，每段 25 台可读设备 × 20000 点）。

  | capture_sequence | 严格共同点数 | 相对 20000 点 | 分析器推算跨度 | 留一（排除目标设备后） |
  | ---: | ---: | ---: | ---: | ---: |
  | 0 | 422 | 2.11% | 0.842 s | 19570 |
  | 1 | 621 | 3.11% | 1.240 s | 19528 |
  | 2 | 455 | 2.28% | 0.908 s | 19532 |
  | 3 | 375 | 1.88% | 0.748 s | 19547 |
  | 4 | 288 | 1.44% | 0.574 s | 19542 |

  排除其他任意单台设备时，交集仍为 288–621。
- **触发**：在「选择BPM」中同时选择 `AC_LA_L1_BI_COLDBPM05` 与其余 24 台设备，执行 strict（精确交集）对齐。目标设备相邻 bunchID 差 28–76（众数 76），其余 24 台恒为 2000。
- **影响**：97–98% 采样点被交集丢弃；推算跨度 0.574–1.240 s 低于频谱配置的 5 s 最短记录门槛，该任务 5 段在频谱页**无法分析**。注意：这不是「波形错位」，而是「共同点几乎全部丢失」——原始记录本身各段仍完整覆盖约 40 s（`(末−首)/1e6 = 39.998 s`）。
- **版本**：`368a9aa`（2026-10-13，r1 交付 `source_revision`）；`f7f28fb`（2026-10-19）把核验代码入库。**对齐算法在此前后未变**（见 `alignment_algo_hash` 覆盖范围说明）。
- **预期 vs 实际**：预期 25 台同批设备有接近 20000 个共同 bunchID → 实际 288–621。
- **根因证据**：`outputs/history-ui-validation-20261016/real-data-20261012-all-segments.json`（逐段 `strict_common_bunch_id_count`、`leave_one_out_target.change_vs_all_devices`、`target.step_min/max/mode`、`sampling_rate_fields.frequency_hz=500.0`）；`…-sequence-0.json` 至 `…-sequence-4.json`；`…/bunch-id-fixtures/22833275-5e77-41c5-b703-f306accde164_S00000.npz` 至 `S00004.npz`（含 `fixture_sha256`）；`交付/20261016-history-quality-r1/README.md`（「2026-10-12 历史数据核验」表与留一检查结论）；`docs/CURRENT_STATUS.md:169`；**本次审计独立复算** `reports/phase1-m0-20261029/waveform-audit/verify_fixtures.py`（5 段全部逐位一致，`RESULT: ALL CHECKS PASSED`）。
- **替代解释**：① 我方对齐算法有 bug —— 被留一检查排除（移除目标设备后共同点立即回到 19528–19570，即 97.6%–97.9%）；② 该设备硬件/时钟故障 —— 交付记录明确「不单独证明物理时钟或硬件故障」，本文件同意：步长差异只证明编码/时基不同，不能证明坏设备；③ 采集频率与 timing PV 不一致 —— 2026-10-12 已被 `FREQUENCY_MISMATCH`（2026-10-07 起）排除，且 500 Hz ↔ 步长 2000 在 1 MHz 假设下自洽（2000 µs = 500 Hz）；④ 两台设备真在采不同物理事件 —— 无法排除，无设备侧同步信号记录；⑤ 设备已被修复 —— 无设备组反馈记录。
- **修复与验证**：`f7f28fb` 新增 `processing/bunch_id_diagnostics.py`（对齐前统计每台设备相邻 ID 步长、众数、是否与多数设备不一致；异常时必须**显式确认**才继续 strict 对齐；保留全部设备，不自动剔除/缩放/插值）。验证：本机激活 + 真实桌面 smoke（PID `3120745`，运行时二进制 SHA-256 `c88b8213e97eff8d601b0154ed31f3432541bf87a2066d669058ae121b7c4beb`）、241 项质量门、4 项诊断测试、8 张两分辨率截图、本次 fixture 复算。
- **未决**：① 该设备步长 28–76 是固件差异、配置差异还是时钟故障，仓库内无裁决依据；② 25 台真实 X/Y 联合 GUI 补测按用户要求未执行，异常态截图为「真实 bunchID + 示例 X/Y」，不能称为多设备原始波形验收；③ 未做 47 台全量步长普查，是否有其他同类设备未知。

### case-08　timing PV = 10 Hz 时整条 v2 采集通道被拒　`已证实`

- **现象**：正式前端「采集参数 → 当前频率」显示「暂不可用」。服务端原文：`accepted=False error_code=TIMING_FREQUENCY_FAILED message="unsupported capture frequency 10 Hz; supported: 1000, 500, 100, 50, 5, 2 Hz"`。
- **触发**：定时 PV `AC-LA-INJ1-TIM:WRN1:MCFQ8`（`10.101.2.1:6310`）读数为 10 Hz，而 `_CAPTURE_INTERVAL_SECONDS` 缺 `10.0` 档。
- **影响**：**不是显示故障。** 同一白名单校验挡在 GUI `start_capture`、Agent API v2 `control/captures` 与服务端 `handle()`（提交时读 PV 并调 `capture_interval_seconds()` 算等待值，见 `runtime.py:292`），因此 10 Hz 下整条 v2 采集通道不可用；「暂不可用」只是最早暴露的表象。
- **版本**：`89bb146`（4 档）→ `61b47db`（补 500/5）→ `5f17b67`（r1 源码基线，仍无 10）→ **`cae6b64`（2026-10-26 20:24:54）修复**。**与国庆假期无关**：EPICS Archiver 证明 10 Hz 至少自 **2026-08-17** 起就反复出现（case-09 / case-12），`cae6b64` 只是**补支持**，不是对「假期后新状态」的反应。
- **预期 vs 实际**：预期系统跟随机器实际频率 → 实际 10 Hz 属白名单外，`read_timing_frequency()` 在返回前调用 `capture_interval_seconds()` 抛 `ServerSettingsError`，服务端包成 `TIMING_FREQUENCY_FAILED`。
- **根因证据**：HEAD `src/waveform_storage/acquisition/runtime.py:491-501`（含 `10.0: 2100`）、`:503-505`（PV 名与 EPICS 地址）、`:507-533`（`read_timing_frequency`，`:524` 做白名单校验）、`:539-550`（`KeyError` → `unsupported capture frequency …`）；`src/waveform_storage/acquisition/server.py:561-589`；`apps/acquisition_server/main.py:146`；`交付/20261026-timing-10hz-r1/README.md:7-32`；`docs/CURRENT_STATUS.md:25-49`。
- **替代解释**：① 隧道 / ZMQ / systemd / EPICS 连接故障 —— 已被发布前实测排除（隧道 master 存活、`health` 返回 accepted、服务 active 且无在跑任务；错误内容是频率数值本身而非连接超时）；② GUI 显示层 bug —— 不成立，修复后同路径 `get_timing_frequency` 返回 `frequency_hz=10.0`；③ PV 瞬时抖动 —— 不成立，打包与远程界面均显示 10 Hz。
- **修复与验证**：`cae6b64` 新增 `10.0: 2100`（现场确认：20000 触发 / 10 Hz = 2000 s + 余量；该表属现场规则，**禁止插值**）；`tests/test_acquisition_server.py` 改为断言 `10 → 2100`、拒绝样例改 20 Hz；`docs/agent-api-v2.openapi.json` enum 加 `10`；GUI 去掉频率下拉框，改为只读显示服务端 PV 并在采集前重读跟随。验证：286 项质量门 `OK`；61 项定向（18+31+12）；协议 smoke 5 端点通过（1 任务 / 5 段 / 125 精确文件）；`evidence/live-timing-frequency.json` 返回 `accepted=true, frequency_hz=10.0, source=timing_pv`；`evidence/deploy.json` 记录 `MainPID=1991109`、`ActiveState=active`、`binary_sha256` 与 `BUILD-INFO` 一致。
- **未决**：① 10 Hz 下的真实采集/下载/HDF5 落盘**从未验证**（未发送任何真实采集请求），首次真实采集建议人工核对分段文件大小；② 真实桌面 GUI 复验未做（`deploy.json` 状态 `GUI SMOKE PENDING`），「当前频率」显示 10 Hz 由协议读取 + 离屏截图推得；③ 该故障的**暴露期**已由 EPICS Archiver 界定为「至少 2026-08-17 起 PV 就多次记录到 10 Hz」（见 case-09 / case-12），但具体哪些窗口有采集请求被拒仍无记录；④ `phy01` 独立会话未验证。

### case-09　timing PV 是可变的运行频率读数：10 Hz 至少自 2026-08-17 起反复出现　`已证实`

> 2026-10-29 由 EPICS Archiver 只读证据从「推断」升级为「已证实」，并**推翻了**「国庆后 PV 一次性从 5 Hz 切到 10 Hz」这一前提。

- **现象**：Archiver（`source_id=TIM_ARCHIVER_URL`，`http://10.101.9.19:17668`）显示 `AC-LA-INJ1-TIM:WRN1:MCFQ8` 在 **2 / 5 / 10 / 20 / 50 / 100 / 1000 Hz** 之间反复跳变。10 Hz 记录出现在 **2026-08-17、08-27、08-28、09-04、10-01、10-23、10-27**；2026-08-17 当天 **78 分钟内 10/2 交替 6 次**；2026-10-29 live 窗口 context 读数为 **50 Hz**（2026-10-28T09:28:03Z）。
- **触发**：现场加速器运行态频率调整，与 Waveform 软件发布节奏无关。
- **影响**：① **推翻「国庆后 PV 变为 10 Hz」这一因果前提** —— 10 Hz 是长期存在的运行态读数，任何时刻读到 10 Hz 都会触发 case-08 的白名单缺口；② **历史采集的采样率不能由「当前 PV 读数」推断**，必须取自该任务记录（`CaptureRunSummary.frequency_hz`）—— 这是 case-07 之后频谱页采样率来源设计的直接依据；③ 2026-10-26 修复当天归档内**零变化点**，最后一次记录为 2026-10-23T13:36:41Z 的 10 Hz → 修复时 PV 确实处于 10 Hz，与 `docs/CURRENT_STATUS.md:28` 一致。
- **版本**：`cae6b64` 首次在代码中记录 10 Hz 已被现场确认（`runtime.py:495-497` 注释 `Field-confirmed on 2026-10-26`）；该提交是**补支持**，不是对假期后新状态的反应。
- **预期 vs 实际**：若「国庆后对齐异常」源于 PV 在假期后切到 10 Hz，则 2026-10-08 之前 PV 不应出现 10 Hz → 实际 10 Hz 在 **2026-08-17（国庆前 45 天）** 已有归档记录，并在 08-27、08-28、09-04、10-01 反复出现。**假设被推翻。**
- **根因证据**（5 次只读查询，`strategy=lastSample`，逐点在本次审计中独立复算一致；完整点列见 `reports/phase1-m0-20261029/waveform-audit/evidence-index.md` 第 12 节）：

  | 窗口 | start → end（UTC） | max_points | 返回点数 | bin_seconds | 关键点 |
  | --- | --- | ---: | ---: | ---: | --- |
  | A | 2026-08-15T00:00 → 2026-10-01T00:00 | 2000 | 42 | 2031 | `08-17T06:14:50.469014Z=10`、`08-27T02:31:36.103140Z=10`、`08-28T08:11:06.830204Z=10`、`09-04T01:54:55.619560Z=10`、`09-04T09:31:10.691215Z=10` |
  | B | 2026-08-17T00:00 → 2026-08-17T08:00 | 500 | 7 | 58 | `06:14:50=10`、`07:04:04=2`、`07:04:48=10`、`07:13:20=2`、`07:18:08=10`、`07:32:12=2` |
  | C | 2026-10-01T00:00 → 2026-10-02T00:00 | 500 | 2 | 173 | `09-29T20:53:13.709428Z=5`、`10-01T09:59:55.853957Z=10`（= 10-01 17:59:55 +0800，假期首日） |
  | D | 2026-10-23T00:00 → 2026-10-28T00:00 | 2000 | 16 | 216 | `10-23T12:02:27=10`、`12:38:51=1000`、`12:46:20=10`、`13:36:41=10`；`10-27T13:02:41=20`、`13:09:30=10`、`14:21:47=50` |
  | E | 2026-10-26T00:00 → 2026-10-27T00:00 | 500 | 1（**in_range 0**、`context_only`） | 173 | 唯一 context 点 `2026-10-23T13:36:41.419348Z=10` |

  另有 `archiver_resolve_pvs` 确认该 PV 解析到 `TIM_ARCHIVER_URL`，与 `src/waveform_storage/acquisition/runtime.py:503` 的 `TIMING_FREQUENCY_PV` 字面一致。
- **替代解释**：
  1. **归档是降采样视图**（部分成立，必须一并引用）：5 次返回全部 `segments[].downsampled=true`、`bin_seconds` 15–2031 s，因此只声称「**归档记录时刻的读数**」，不声称 raw 全量事件序列。粗 bin 会吞掉短时跳变 —— 同一 08-17 区间，窗口 A（bin=2031 s）只看到 1 个 10 Hz，窗口 B（bin=58 s）看到 2 个；但即便窗口 A 也仍记录到 08-17、08-27、08-28、09-04 的 10 Hz，**不影响「10 Hz 长期存在」这一结论**。
  2. 「10 Hz 只在 08-17 短暂抖动」：**不成立** —— 08-27、08-28、09-04、10-01、10-23、10-27 均有 10 Hz 记录。
  3. 「Archiver 的 PV 与软件读的不是同一个」：**已排除** —— 名称解析成功且字面一致。
  4. 「PV 值的物理含义不明」（是否机器实际束流频率、是否含档位语义）：**成立且未解决** —— 但服务端读的就是这个 PV，对软件行为而言等价。
- **修复与验证**：无需修复（环境侧运行态）。系统侧改进：`cae6b64` 之后采集前必定重读 PV 并跟随，PV 跳变不再造成频率错配。验证：本次审计用 MCP `archiver_query_series` 以相同 PV 与 5 个窗口重新查询，逐点核对时间戳与数值，与 Lead 给出的点数（7 / 42 / 2 / 16 / 1）**逐一一致**。
- **未决**：① PV 在 2/5/10/20/50/100/1000 Hz 间跳变的物理/运行含义未由运行值班确认；② 归档为降采样视图，逐次变化需直查 Archiver 原始接口；③ 10 Hz 窗口内是否有采集被提交并失败，仓库内无记录（见 case-12）。

### case-10　对「国庆后 Waveform 对齐异常」的裁定　`推断`

- **现象**：`PRAB_PLAN.md` 四处把「国庆后」与「对齐异常 / 对齐逻辑差异」绑定：第 14 行「例如国庆前后的对齐逻辑差异」、第 37 行文档标题「含国庆后对齐问题根因与修复对比」、第 73 行「如国庆后波形对齐偏移」、第 104 行「彻底查清并整理包括国庆后 Waveform 对齐异常在内的真实历史案例」。
- **触发**：计划撰写时把「观察到的现象」与「版本变更」之间的因果关联当成了已知事实。
- **影响**：直接影响 Phase 1 任务定义、本文档标题与 Task 3 种子题设定；若按原措辞入库，会向 RAG 语料写入未经证实的因果断言。
- **版本**：`89bb146`（国庆前最后提交）→ `61b47db`（假期内首个提交，此前 42 天零提交）。
- **预期 vs 实际**：若为版本回归，应在 2026-09-25~10-29 有修改对齐语义的提交，且 10-08 后出现回归或用户报告。**三条均不成立**：① 2026-08-26 15:32 至 2026-10-07 16:30 零提交；② `processing/alignment.py` 自 2026-07-25 起仅被 `25e6b73` 改过且只加 `metadata` 字段；③ 仓库内无用户报告、无失败测试、无日志记录「国庆后对齐偏移」（`grep -rn 对齐异常 docs/` 零命中）。相反，国庆后确有真实严重对齐异常（case-07），但根因是单台设备 bunchID 步长不相容，不是代码变更。
- **根因证据**：`git log --all --date=iso --reverse`（零提交区间）；`git log --all -S'偏移'`（仅命中 2026-07-25 基线快照）；`git show 25e6b73 -- src/waveform_storage/processing/alignment.py`（仅加字段）；`outputs/history-ui-validation-20261016/real-data-20261012-all-segments.json`（case-07 原始统计）；`交付/20261016-history-quality-r1/README.md`。
- **替代解释**：① 计划措辞来自口头/会议信息而非仓库 —— 无法核实；若确有外部来源，应补为可引用材料，否则不得作为事实入库；② 计划所指的「对齐」其实是「历史检索/时间基准呈现」—— 这与仓库事实最接近：国庆后确有该层的实质变化（case-06），但那是显示层缺陷，不是回归；③ 「偏移」指严格的物理时间偏移 —— 无任何证据支持（无跨设备相对时延测量、无同步信号记录，`git log -S'offset'` 命中的全是频谱 analysis offset 等无关语义）。
- **修复与验证**：无代码修复。建议按第 6 节替换措辞。验证方式：对每个断言做可证伪检查（零提交区间、算法 diff、全文检索）。
- **未决**：`PRAB_PLAN` 的「国庆后对齐异常」是否有仓库之外的来源？若有，应作为外部证据补入 `evidence-index.md` 并降级为「转述」。

### case-11　`interval=10` 语义歧义（10 分钟 vs 10 Hz）　`待核实`

- **现象**：交接记录原文 —— 「旧版软件的 `interval=10` 表示 10 分钟，不是 10 Hz」「`attempted_cycles=19` 不是硬件采样点数，频率语义仍需设备/需求侧确认」。
- **触发**：把旧协议/旧界面里的 `interval` 数值当作频率，或把 `attempted_cycles` 当作采样点数。
- **影响**：若把 10 分钟读成 10 Hz，等待值/时长判断会差 60 倍；下游按错误频率声明采样率后，由采样率推导的时间轴与频率轴全部按错误比例解释 —— 这正是「对齐/时基偏移」最典型的表现形式。
- **版本**：`89bb146` 期间的现场版本（交接快照 HEAD `b3f18a2`，**未出现在本仓库历史中**）。
- **预期 vs 实际**：预期频率、时长、采样点数三者语义在协议与界面中各有明确字段与单位 → 实际历史上确实存在同名字段承载不同单位（`interval` 是分钟；`frequency_hz` 才是 Hz；`attempted_cycles` 是设备轮次）。
- **根因证据**：`docs/handoffs/TASK_HANDOFF_2026-08-28_17-17-38_UTC+0800.md`（`[Constraint]` 段全文）；`docs/history/2026-07/线上运行基线调查.md` 1.3 节（线上 `nohup.out` 两次请求为 2 Hz / 600 s，说明服务端把界面分钟数换算为秒；「在取得原始请求帧或线上源码前仍不能确认具体换算位置」）。
- **替代解释**：该歧义**只存在于文档与旧代码注释中，从未在真实数据分析中触发** —— 很可能；仓库内没有任何采集记录、分析结果或用户报告显示曾把 `interval` 当频率使用。
- **修复与验证**：`61b47db` 的协议 v2 显式拆分 `frequency_hz` 与 `duration_seconds`，字段名自带单位。**无验证记录。**
- **未决**：2026-10-07 之前的分析结果（若存在）是否用过被误读的频率参数，需要历史产物中的参数记录才能判断；频率语义至今无设备/需求侧确认结论。

### case-12　10 Hz 白名单缺口的可触发窗口自 2026-08-17 起即存在　`已证实`

- **现象**：`_CAPTURE_INTERVAL_SECONDS` 在 2026-10-26（`cae6b64`）之前**从不含** `10.0` 档；而 Archiver 显示 PV 自 2026-08-17 起在多个日期记录到 10 Hz。二者叠加：这些窗口内任何走 v2 采集路径的请求都会被 `TIMING_FREQUENCY_FAILED` 拒绝。
- **触发**：在 PV 读数为 10 Hz 的时刻提交采集（GUI `start_capture` / Agent API v2 `control/captures` / 服务端 `handle()`）。
- **影响**：把 case-08 的暴露期从「2026-10-26 前后」扩展到「**至少 2026-08-17 至 2026-10-26 的若干窗口**」，并说明该缺陷与国庆假期**无因果关系** —— 它是「按已知档位枚举的白名单」与「运行态多值 PV」之间的**恒定不匹配**。
- **版本**：`89bb146`（4 档：1000/100/50/2）→ `61b47db`（补 500/5，仍无 10）→ `cae6b64`（新增 `10.0: 2100`，缺口关闭）。
- **预期 vs 实际**：预期白名单覆盖 PV 可能出现的全部档位，或遇未覆盖档位时给出可操作降级路径 → 实际为枚举式白名单，不在表内即整体拒绝。
- **根因证据**：`git show 89bb146:src/waveform_storage/acquisition/runtime.py` 第 477-482 行；`git log -S'4200' -- src/waveform_storage/acquisition/runtime.py`（仅 `61b47db`）；`git log --all -S'10.0: 2100'`（仅 `cae6b64`）；`src/waveform_storage/acquisition/runtime.py:539-550`；`docs/CURRENT_STATUS.md:33-34`（10 Hz 从未被支持，原 `tests/test_acquisition_server.py` 明确断言 10 Hz 必须被拒绝）；Archiver 窗口证据见 case-09。
- **替代解释**：① 这些窗口内实际没有采集需求，因此从未暴露 —— **很可能**，仓库内没有 2026-08-17 至 10-25 的采集失败记录；但不能因此断言缺陷不存在（代码路径恒定，且服务端提交时必读 PV）；② Archiver 记录的 10 Hz 不代表机器真在 10 Hz 运行 —— 可能，但服务端读的就是这个 PV，对软件行为等价；③ 20 Hz / 1000 Hz 等档位同样构成缺口 —— 部分成立：1000 Hz 在表内，**20 Hz 不在表内**（Archiver 2026-10-27T13:02:41Z 有 20 Hz 记录），属同类潜在下一个缺口，但不计为已发生事故。
- **修复与验证**：`cae6b64` 补齐 10 Hz（`交付/20261026-timing-10hz-r1/evidence/live-timing-frequency.json` 修复后返回 `10.0`；`quality.log` 286 项 `OK`）。**注意**：本轮只补 10 Hz，白名单仍是枚举式，遇未列出档位（如 20 Hz）仍会整体拒绝 —— 这是设计选择而非遗漏，需现场负责人裁决是否改为显式可配置表。
- **未决**：① 2026-08-17 至 10-25 是否有采集因 10 Hz 被拒，需现场 `state/*.json` 或服务端日志，仓库内没有；② 白名单继续手工枚举还是改为现场可配置档位表 —— 待现场负责人裁决（当前 20 Hz 仍不在表内）。

---

## 3. 真实运行事故 / 测试构造 / 设计设想的分离

引用本文件时必须先分清证据来源，否则会把测试场景写成事故，或把事故当成测试。

### 3.1 真实运行事故（有现场原始记录）

| 案例 | 时间 | 一手证据 |
| --- | --- | --- |
| case-01 | 2025-11-12 12:07:21 批次 | `docs/history/2026-07/线上运行基线调查.md`（只读 h5dump 真实文件 + SHA-256） |
| case-02 | 2026-10-02 23:03→00:13 | `logs/capture-BI-5Hz-20000-70min-20261002-230306-24fbc7de-*.json`（含真实 `/SHINE_Data/...` 落盘路径） |
| case-03 | 2026-10-02 22:16→22:20 | `logs/capture-BI-20261002-221633-5c9321c5-*.json` |
| case-07 | 2026-10-12 任务 | `outputs/history-ui-validation-20261016/real-data-20261012-*.json` + 5 个 `.npz` fixture |
| case-08 | 2026-10-26 前 | 服务端错误原文 + `交付/20261026-timing-10hz-r1/evidence/live-timing-frequency.json` |

**外部一手数据源**（不在 Waveform 仓库内，引用时须同时给出 `source_id` 与查询窗口）：

| 案例 | 数据源 | 一手证据 |
| --- | --- | --- |
| case-09 / case-12 | EPICS Archiver，`source_id=TIM_ARCHIVER_URL`，`http://10.101.9.19:17668`，PV `AC-LA-INJ1-TIM:WRN1:MCFQ8` | 5 次只读 `archiver_query_series`（`strategy=lastSample`）+ 1 次 `archiver_query_live`，参数与点列见 `reports/phase1-m0-20261029/waveform-audit/evidence-index.md` 第 12 节；本次审计独立复算逐点一致 |

### 3.2 测试构造（**不得**写成真实事故）

| 构造物 | 位置 | 构造了什么 | 易被误读之处 |
| --- | --- | --- | --- |
| 步长 500,000 / 1,000,000 合成序列 | `tests/test_alignment.py:34-42` | 两种步长的设备序列 | 数字与 case-01 真实步长量级相同 |
| `step = int(1_000_000 / fs)` 合成 bunchID | `tests/test_spectrum_analysis.py:27` | 按 1 MHz 计时钟假设合成 | 该假设对主流设备成立、对 COLD BPM 不成立，测试不覆盖后者 |
| 「请求 2 台、实际 1 台、sequence 0/3 跳号」 | `tests/test_partial_history_integration.py` | 部分成功段 + 段号跳号整链路 | r4 明确写「现场所选任务没有部分成功段」—— 该场景当时只有测试构造 |
| 异常/空交集截图 | `交付/20261016-history-quality-r1/evidence/preflight-anomaly-*.png`、`zero-intersection-*.png` | 真实 bunchID + **示例合成** X/Y | 交付记录自述「不能称为多设备原始波形验收」 |
| 单设备 20000 点桌面 smoke | `交付/20261016-history-quality-r1/evidence/gui-history.json` | 只选 1 台设备 | 只有 1 台时「多数步进参考无法确定」，**不覆盖** case-07 的 25 台异常 |

### 3.3 设计文档设想（尚未现场验证）

| 文档 | 设想 | 状态 |
| --- | --- | --- |
| `docs/数据对齐v2设计.md` 第 6 节 | coverage 覆盖率阈值、HDF5 v2 物理单位、GUI 点击流验证 | 文档自述「尚未做 GUI 点击流或现场验证」，4 项前置条件至今无结论 |
| `docs/采集协议v2候选.md` | 10 Hz 等待值 2100 s | 注释标 `Field-confirmed on 2026-10-26`，但 10 Hz 真实采集/下载/落盘**从未验证** |
| `docs/采集协议v1候选.md` | 旧协议耗时字段 | 仅设计，未现场部署 |

---

## 4. 证据可信度分级说明

引用本文件的任何结论时，按下列级别标注来源强度。**级别低于 B1 的内容不得用于断言因果。**

| 级别 | 名称 | 定义 | 本文件的例子 | 可否支撑因果断言 |
| --- | --- | --- | --- | --- |
| **A0** | 外部一手 | 仓库之外的一手数据源，只读查询且参数可复述 | case-09/case-12：EPICS Archiver 5 次查询（`source_id=TIM_ARCHIVER_URL`） | ✅ 可（限「归档记录时刻的读数」，不声称 raw 全量） |
| **A1** | 一手可复算 | 原始数据在场，且第三方可独立重算得到同一结果 | case-07：5 个 `.npz` fixture → `verify_fixtures.py` 全部一致 | ✅ 可 |
| **A2** | 一手不可复算 | 原始记录在场，但依赖的现场对象已不存在（文件已清理、机器已变更） | case-02/03 的采集日志（现场 `/SHINE_Data` 文件不在本地）；case-01 的 h5dump（原始 HDF5 已清理） | ✅ 可（限记录内容） |
| **A3** | 发布证据 | 交付目录内的构建 / 部署 / 验收记录，带二进制 SHA-256、PID、质量门计数 | case-08：`deploy.json` + `quality.log` + `live-timing-frequency.json` | ✅ 可（限「该交付做了什么」） |
| **B1** | 代码事实 | HEAD 或指定 commit 的 `文件:行`，可 `git show` 复核 | case-06 的 `/1_000_000` 除式；case-05 的 `FREQUENCY_MISMATCH` | ✅ 可（限「代码是什么」） |
| **B2** | 文档记录 | 仓库内的设计 / 状态 / 交接文档，反映记录当时的事实 | `docs/CURRENT_STATUS.md:169`；`docs/handoffs/…2026-08-28…` | ⚠️ 只能引用为「记录如此」，不能外推 |
| **C1** | 计划措辞 | 规划文件中的说法（如 `PRAB_PLAN.md`） | case-10 | ❌ 本身不是证据 |
| **C2** | 测试构造 | 测试代码、合成 fixture | 第 3.2 节全部 | ❌ 不能当事故 |

**两条硬性引用纪律**：

1. **引用已删除代码必须带 sha**。例如「历史上曾把 bunchID 差值当秒数」必须写成 `git show 61b47db:src/waveform_storage/gui/operator_window.py` 第 1243-1248 行，**不能**写成「operator_window.py 里有 `/1_000_000`」——HEAD 已无此代码。
2. **`alignment_algo_hash` 相同不代表时间基准相同**。它只覆盖 `processing/alignment.py`；时间轴换算（`analysis/loaders.py:_id_times`）、跨度推导（`analysis/engine.py`）、诊断（`processing/bunch_id_diagnostics.py`）、呈现（`gui/operator_window.py`）都不在该哈希范围内（见第 0 节）。

---

## 5. 遗留缺口

按「补证据的性价比」排序。**在这些缺口关闭前，本文件不宣称任何案例已完全闭环。**

1. ~~**timing PV `AC-LA-INJ1-TIM:WRN1:MCFQ8` 的历史序列**~~ —— **2026-10-29 已补齐**（EPICS Archiver，`source_id=TIM_ARCHIVER_URL`，5 次只读查询，见 `evidence-index.md` 第 12 节）。结论：PV 是可变的运行态读数，10 Hz 至少自 2026-08-17 起反复出现，**不存在国庆前后一次性切换**。这条缺口关闭后 case-09 由「推断」升级为「已证实」，「国庆后 PV 变为 10 Hz」的前提被推翻。**未解决的是它的下游问题**：⑧ 哪些窗口有采集被拒、⑨ PV 多值性的物理含义、⑩ Archiver 的原始（非降采样）序列。
2. **2026-10-02 现场服务端二进制的 SHA-256 与源码清单**（case-04）。没有它，国庆前后的行为差异无法与代码版本对齐。
3. **`AC_LA_L1_BI_COLDBPM05` 的设备侧说明**（固件版本 / bunchID 编码语义 / 是否已修复）。决定 case-07 是「设备差异」还是「设备故障」。
4. **`PRAB_PLAN`「国庆后对齐异常」的外部来源**（会议记录 / 口述 / 设备组反馈）。若存在，必须降级为「转述」并补入 `evidence-index.md`。
5. **2026-10-07 至 2026-10-18 窗口内的操作员使用记录**（case-06）。决定该显示缺陷是否有真实误读后果。
6. **10 Hz 下的真实采集闭环**（case-08）。当前完全未验证。

---

## 6. 与 `PRAB_PLAN` 措辞的差异声明

`PRAB_PLAN.md` 中的相关说法**目前只是计划措辞，不是已核实事实**。逐条裁定如下。凡本节判为「不成立」的措辞，**不得**进入 RAG 语料或种子题的标准答案。

### 6.1 逐条裁定

| # | `PRAB_PLAN` 原文 | 位置 | 裁定 | 依据 |
| --- | --- | --- | --- | --- |
| 1 | 「例如国庆前后的对齐逻辑差异」 | 第 14 行 | **不成立** | 2026-08-26 15:32 → 2026-10-07 16:30 零提交；`processing/alignment.py` 自 2026-07-25 起仅 `25e6b73` 改过且只加 `metadata` 字段 |
| 2 | 文档标题「含国庆后对齐问题根因与修复对比」 | 第 37 行 | **需改写** | 对齐算法无缺陷可修；真实缺陷是对齐**前**的原始步长诊断缺失与**对齐后**的时间基准呈现错误，修复在 2026-10-19（`f7f28fb`） |
| 3 | 「如国庆后波形对齐偏移」 | 第 73 行 | **「偏移」不成立** | 仓库内无任何 time-offset 测量或记录；`git log -S'offset'` 命中的全是频谱 analysis offset。真实现象是「共同点塌缩」（case-07），不是「波形错位」 |
| 4 | 「彻底查清并整理包括国庆后 Waveform 对齐异常在内的真实历史案例」 | 第 104 行 | **部分成立** | 「国庆后确实存在真实对齐异常」成立（case-07，2026-10-12，保留率 1.44%–3.11%）；「是版本回归」不成立 |

### 6.2 建议替换措辞（可直接用于 M6 文档与种子题）

| 原措辞 | 建议替换为 |
| --- | --- |
| 国庆前后的对齐逻辑差异 | 「国庆前后**历史检索与时间基准呈现**存在差异：2026-10-07（`61b47db`）引入『bunchID 差值 ÷10⁶ 当秒数』显示，2026-10-19（`f7f28fb`）移除并新增原始步长预检查；**对齐算法本身自 2026-07-25 起未变**。」 |
| 含国庆后对齐问题根因与修复对比 | 「含 2026-10-12 真实任务（`22833275-…`）跨 25 台严格共同点塌缩至 1.44%–3.11% 的根因（单台 L1 冷 BPM bunchID 步长 28–76 vs 其余 24 台 2000）与 2026-10-19 原始步长预检查修复的对比。」 |
| 国庆后波形对齐偏移 | 「2026-10-12 真实任务跨 25 台严格共同点仅剩 422/621/455/375/288（共 20000 点），根因为单台设备 bunchID 步长与其余设备不相容；**未观察到时间偏移（offset）**。」 |
| 国庆后 Waveform 对齐异常 | 「2026-10-12 真实任务的对齐塌缩（留存 1.44%–3.11%）是最接近『国庆后对齐异常』的现场证据；该现象在 2025-11-12 批次已有同类前兆（严格交集为 0），属设备 bunchID 编码/时基差异，不是软件版本回归。」 |

### 6.3 `PRAB_PLAN` 中**确实成立**的技术判断

以下说法有证据支持，可保留：

- **「分析脚本与文档口径失配（Code-Doc Drift）」真实存在**（第 14 行前半句）。直接实证：`交付/20261008-history-release-r4/README.md` 与 `packaging/direct-operator/README.md` 曾写「界面以最后一个与第一个 bunch ID 之差显示数据时长，单位秒」，而该换算对步长 28–76 的设备不成立；`cae6b64` 才把文案改为「bunchID 是数据编号，不能直接当作秒数或采样率」。
- **「`source_version` / 算法 Hash 不一致」是真实风险类别**（第 14 行）。直接实证：① 2026-10-02 现场部署 ≠ 任何提交（case-04）；② 即使有 `BUILD-INFO`，`source_state=working-tree` 也让源码 ≠ `source_revision`（r4 的 `operator_window.py` 清单哈希 `077e0aa4…` ≠ `51afde8` 的 blob `2bfd4068…`）；③ 系统确实已有 `algorithm_source_sha256`（`agent_v2_service.py:54,618-619`）可用于锁定对齐算法版本。
- **「不同版本/口径的冲突结论必须分版本并列回答」**（第 49 行）是正确策略。本文件的第 1 节时间线就是为这种并列回答提供锚点：**同一个「数据时长」概念在 2026-10-07~10-18 与 2026-10-19 之后有两套口径，且只有后者可复用。**

### 6.4 引用纪律（给 M6 语料与种子题）

1. 引用 case-06 时必须写明「`git show 61b47db:…` 第 1243-1248 行」，并说明该代码**已不在 HEAD**。
2. 引用 case-07 时不得写成「国庆后对齐偏移」，只能写「严格共同点塌缩 / 覆盖率塌缩」。
3. 引用 case-08 时必须说明：10 Hz 至少自 **2026-08-17** 起反复出现（case-09，EPICS Archiver 证据），`cae6b64`（2026-10-26）是**补支持**而非对「假期后新状态」的反应；**不得**表述为「国庆后才出现 10 Hz」或「国庆后 18 天才出现 10 Hz」。
4. 任何「国庆前后的对齐逻辑差异」表述，必须附带本文件第 1 节的零提交区间证据。
5. `PRAB_PLAN` 的原措辞不得作为任何答案的「标准答案」来源（C1 级，不是证据）。
