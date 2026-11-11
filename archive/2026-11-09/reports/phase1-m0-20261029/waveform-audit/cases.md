# Waveform 历史案例台账（人读版）

- **审计对象**：`/home/whloong/waveform-storage/waveform-storage-system`（只读）
- **审计基线**：`dc50e08a2beddff42c297a237b3f3312f5c24ac9`（2026-10-26 21:06:55 +0800）
- **审计日期**：2026-10-29
- **结构化台账**：[cases.json](cases.json) ｜ **证据定位**：[evidence-index.md](evidence-index.md) ｜ **复算脚本**：[verify_fixtures.py](verify_fixtures.py)
- **案例数**：12 —— 已证实 10 / 推断 1 / 待核实 1
- **2026-10-29 增补**：case-09 与新增 case-12 采用 EPICS Archiver 只读证据（`source_id=TIM_ARCHIVER_URL`），推翻了「国庆后 PV 一次性变为 10 Hz」的前提。查询参数见 [evidence-index.md](evidence-index.md) 第 12 节。

分级定义：**已证实**＝提交、diff、日志、交付目录或真实数据中存在可直接引用的原始记录，且本次审计可独立复算或相互印证；**推断**＝有原始记录但结论依赖一步未记录的推理（推理链已写明）；**待核实**＝只有设计文档、测试构造或第三方转述，缺现场原始记录。

---

## 1. 结论先行：`PRAB_PLAN` 所称「国庆后 Waveform 对齐异常」的裁定

**判定：作为「国庆前后的版本回归」不成立（未证实）；作为「国庆后真实观察到的对齐异常」部分成立（已证实）。**

三个可证伪的检查，全部否定「版本回归」：

| 检查 | 方法 | 结果 |
| --- | --- | --- |
| 国庆前是否有对齐相关改动？ | `git log --all --date=iso --reverse` | 2026-08-26 15:32:11 至 2026-10-07 16:30:43 **零提交**（41 天 23 小时）。不存在「国庆前的改动」可供回归 |
| 对齐算法本身是否变过？ | `git log -- src/waveform_storage/processing/alignment.py` | 自 2026-07-25 起仅两次：`36a927b`（2026-07-25 建立）与 `25e6b73`（2026-10-20）。后者 diff **只给 `DeviceSeries` 加了 `metadata` 字段**，无算法变更 |
| 是否有用户报告/失败测试/日志记录「国庆后对齐偏移」？ | `grep -rn 偏移\|对齐异常 docs/`、`git log -S` | `对齐异常` 在 `docs/` 零命中；`偏移` 仅命中 2026-07-25 的基线快照文件。仓库内**没有任何**此类报告 |

**但「国庆后确实存在严重对齐异常」是真的**，而且原始证据齐全 —— 见 [case-07](#case-07)：2026-10-12 的真实任务（国庆后第 4 天）跨 25 台对齐后，严格共同点只剩 422/621/455/375/288（保留率 **1.44%–3.11%**）。本次审计用归档的 uint64 bunchID fixture 独立复算，5 个段全部与交付记录逐位一致。

最接近 `PRAB_PLAN` 措辞的三条事实，按接近程度排序：

1. **2026-10-12 真实数据的严格交集塌缩**（case-07）：根因是单台 `AC_LA_L1_BI_COLDBPM05` 的相邻 bunchID 步长为 28–76，其余 24 台恒为 2000；留一检查证明限制完全来自这一台。**这是设备/数据属性，不是代码回归。**
2. **国庆后「时间基准呈现」层的一次实质错误**（case-06）：`61b47db`（2026-10-07）把 `(末 bunchID − 首 bunchID) ÷ 1_000_000` 直接当「数据时长（秒）」显示，`f7f28fb`（2026-10-19）才移除。若把「对齐异常」理解为「对齐结果看起来时长/点数不对」，这是国庆后唯一真实存在的显示层缺陷。
3. **10 Hz 采集与 timing PV 跟随改动 `cae6b64`**（case-08 / case-09 / case-12）：引入时间 **2026-10-26 20:24:54**，与假期无关。EPICS Archiver 证明 **10 Hz 至少自 2026-08-17 起就反复出现**（08-17、08-27、08-28、09-04、10-01、10-23、10-27），因此不存在「国庆后 PV 才切到 10 Hz」这回事；`cae6b64` 修的是**白名单支持缺口**（补 `10.0: 2100`），不是对假期后新状态的反应，更不是对齐偏移。

> 一句话：**「国庆后」与「对齐异常」都真实存在，但两者之间没有因果关系。** 最需要补的一份证据是 timing PV `AC-LA-INJ1-TIM:WRN1:MCFQ8` 的历史序列 —— 它同时决定 case-08 的真实起始时间与 case-09 的结论强度（见第 6 节）。

---

## 2. 版本时间线（仅保留与对齐 / 时间基准 / 采样率 / 触发相关的变化）

| 日期 | commit | 变更 | 文件 / 函数 | 默认行为前后 |
| --- | --- | --- | --- | --- |
| 2026-07-25 22:22:29 | `36a927b` | 对齐纯函数落盘 | `processing/alignment.py` | 新增 strict/coverage 两种模式；不再用「按输入顺序求交集、交集下降时跳过设备」 |
| 2026-07-25 22:44:49 | `0b5870c` | legacy 重叠路径隔离 | `legacy/overlap_adapter.py` | 新对齐路径不再调用 legacy 算法 |
| 2026-07-25 22:48:33 | `3a76c39` | 检索应用服务 | `application/retrieval_service.py` | 对齐入口收口到应用服务 |
| **2026-08-26 15:32:11** | `89bb146` | 国庆前最后一个提交 | `acquisition/runtime.py:477-482` | `_CAPTURE_INTERVAL_SECONDS` 仅 `1000/100/50/2`；`legacy/adapter` 亦仅此四分支 |
| *（41 天零提交）* | — | — | — | — |
| **2026-10-07 16:30:43** | `61b47db` | 国庆假期内首个提交（超大合并提交） | `runtime.py`（补 500/5 Hz）、`acquisition/server.py`（新增 `FREQUENCY_MISMATCH`）、`gui/operator_window.py:1243-1248`（新增 bunchID÷1e6 当秒数） | **① 服务端开始校验请求频率 == timing PV（此前无校验）**；② 5 Hz 进入支持表（等待 4200 s）；③ 历史页出现「数据时长 = (末−首 bunchID)/1e6」 |
| 2026-10-08 15:55 | `dbbc0d6`（构建源 `51afde8`） | r4 版本对发布 | 交付记录首次带 `BUILD-INFO` / `source_revision` | 段身份改为 `request_id + capture_sequence`；「按时刻选」→「按任务/段选」 |
| 2026-10-12 15:22:56 | `2be9026` | 历史检索布局重构 | `operator_window.py:791-796`、`:1690` | `(末−首)/1_000_000` 逻辑被重构但**保持不变**（两处） |
| 2026-10-13 12:09:14 | `368a9aa` | AOCI 快照 | — | r1 交付记录的 `source_revision` |
| **2026-10-19 10:14:52** | `f7f28fb` | 历史页质量改进 | 新增 `processing/bunch_id_diagnostics.py`；`operator_window.py` 改显「分析器推算跨度」；`analysis/engine.py` +82 行 | **移除 bunchID→秒换算**；对齐前强制原始步长预检查 + 显式确认；保留全部设备，不自动剔除/缩放/插值 |
| 2026-10-20 10:43:00 | `25e6b73` | Agent API v1 冻结 | `processing/alignment.py`（仅加 `metadata` 字段）；新增 `algorithm_source_sha256` provenance | 对齐算法**不变**；首次对外暴露对齐算法源码哈希 |
| 2026-10-22 16:47:37 | `5f17b67` | Agent API v2 加固 | `application/agent_v2_service.py:54,618-619` | `algorithm_version = 'bunch-id-alignment:' + sha256(alignment.py)[:16]` |
| **2026-10-26 20:24:54** | `cae6b64` | 支持 10 Hz + 跟随 timing PV | `runtime.py:498`（`10.0: 2100`）、`gui/operator_window.py`（删除频率下拉框） | **前端不再允许指定频率**，采集前重读 PV 并跟随；10 Hz 从「拒绝」变「支持」 |

补充：`f7f28fb` 之后 2026-10-17 的 5 个 `*-local` 交付只改文字与布局（`步进`→`相邻数据编号的间隔`），对齐与诊断规则不变（`docs/CURRENT_STATUS.md:121`）。

---

## 3. 严格区分：真实运行事故 / 测试构造 / 设计设想

`PRAB_PLAN` 的风险之一是把三者混为一谈，或反过来把真实事故当成测试场景。本审计按证据来源强制分离。

### 3.1 真实运行事故（有现场原始记录）

| 案例 | 时间 | 原始证据 | 现场性 |
| --- | --- | --- | --- |
| case-01 | 2025-11-12 12:07:21 批次 | `docs/history/2026-07/线上运行基线调查.md`（只读 h5dump 真实文件 + SHA-256） | 生产数据 |
| case-02 | 2026-10-02 23:03→00:13 | `logs/capture-BI-5Hz-20000-70min-20261002-230306-24fbc7de-*.json`，含真实 `/SHINE_Data/...` 落盘路径 | 生产采集 |
| case-03 | 2026-10-02 22:16→22:20 | `logs/capture-BI-20261002-221633-5c9321c5-*.json`（`capture cancelled during service shutdown`） | 生产采集 |
| case-07 | 2026-10-12 任务 | `outputs/history-ui-validation-20261016/real-data-20261012-*.json` + 5 个 `.npz` fixture | 生产归档数据 |
| case-08 | 2026-10-26 前 | 服务端原文 `TIMING_FREQUENCY_FAILED: unsupported capture frequency 10 Hz` + `live-timing-frequency.json` | 生产服务 |

### 3.2 测试构造（**不得**写成真实事故）

| 构造物 | 位置 | 构造了什么 | 为什么容易误读 |
| --- | --- | --- | --- |
| 步长 500,000 / 1,000,000 的合成序列 | `tests/test_alignment.py:34-42` | 伪造两种步长的设备序列验证交集 | 数字与 case-01 的真实步长量级相同，易被当作真实数据 |
| `step = int(1_000_000 / fs)` 合成 bunchID | `tests/test_spectrum_analysis.py:27` | 按「bunchID 是 1 MHz 计时钟」假设合成 | 该假设对主流设备成立、对 COLD BPM 不成立，测试本身不覆盖后者 |
| 「请求 2 台、实际 1 台、sequence 0/3 跳号」 | `tests/test_partial_history_integration.py` | 部分成功段 + 段号跳号的整链路 | **r4 交付记录明确写「现场所选任务没有部分成功段」**（`交付/20261008-history-release-r4/README.md`）——即该场景当时只有测试构造，没有现场对应物 |
| 异常/空交集 GUI 状态截图 | `交付/20261016-history-quality-r1/evidence/*.png`（`preflight-anomaly-*`、`zero-intersection-*`） | 用**真实** bunchID + **示例合成** X/Y | 记录本身注明「不能称为多设备原始波形验收」 |
| 单设备 20,000 点桌面 smoke | `交付/20261016-history-quality-r1/evidence/gui-history.json` | 只选 1 台设备 | 只有 1 台时「多数步进参考无法确定」，**不覆盖** case-07 的 25 台异常场景 |

### 3.3 设计文档设想（尚未现场验证）

| 文档 | 设想内容 | 状态 |
| --- | --- | --- |
| `docs/数据对齐v2设计.md` | coverage 模式覆盖率阈值、HDF5 v2 schema 的物理单位、不同 bunchID 体系的语义 | 文档自述「尚未做 GUI 点击流或现场验证」；第 6 节列 4 项进入现场前的前置条件，其中「与现场负责人确认覆盖率阈值」至今无结论 |
| `docs/采集协议v2候选.md` | 10 Hz 等待值 2100 s | 注释明确 `Field-confirmed on 2026-10-26`，但 10 Hz 下的**真实采集/下载/落盘从未验证** |
| `docs/采集协议v1候选.md` | 旧协议耗时字段 | 仅设计，未在现场部署 |

---

## 4. 案例逐条

> 每条给出：现象 / 触发 / 影响 / 版本 / 预期 vs 实际 / 根因证据 / 替代解释 / 修复与验证 / 未决。完整字段见 [cases.json](cases.json)。

### case-01　2025-11-12 批次 36 台严格交集为 0 — `已证实`

- **现象**：同批 36 台 shape/dtype/长度一致，全设备严格共同 bunchID 为 0。约 30 台主覆盖簇；3 台同为 500,000 步长但窗口完全错开；2 台 L1 冷 BPM 步长约 75/76；1 台 COL0 步长 61/75/76。
- **触发**：对异构 bunchID 空间执行「按输入顺序求交集、交集下降时跳过设备」的顺序式算法。
- **影响**：输入顺序变成隐式业务规则，可能保留小簇而排除主簇 —— 对齐结果不可重复。
- **版本**：`e432d0b`（2026-07-24 基线）仍含 legacy 顺序式路径。
- **预期 vs 实际**：预期有可用共同集 → 实际为 0。
- **根因证据**：`docs/history/2026-07/线上运行基线调查.md`（对真实文件 `RAW-120721-AC_LA_INJ1_BI_SBPM08-S00000.h5` 做只读 `h5dump`，SHA-256 `49c0f6ab…`）；`docs/问题清单与改进路线.md:132-160`；`docs/数据对齐v2设计.md:1-20,40`。
- **替代解释**：设备坏 ≠ 步长不同（文档明确否认把 3 台判为坏设备）。
- **修复**：`36a927b` / `0b5870c` / `3a76c39`（均 2026-07-25）—— 对齐改纯函数，strict + coverage 双模式，设备结果按 `device_id` 稳定排序，输出 `valid_mask` / `skipped_devices` / `quality_report`。
- **验证**：`tests/test_alignment.py`；`docs/数据对齐v2设计.md:22-60`。
- **未决**：不同 bunchID 编码体系的物理语义、覆盖率阈值均未与现场确认。

### case-02　2026-10-02 采集 20 台中 18 台零字节 — `已证实`

- **现象**：`request_id=24fbc7de-…`，INJ1 20 台，5 Hz，`duration_seconds=4200`，`expected_points=20000`。23:06:07 running → 00:13:10 failed，`PARTIAL_DEVICE_FAILURE`，`"18 of 20 device(s) failed"`。`failed_source_files_zero_bytes` 列出 SBPM03–SBPM20 共 18 台；只有 SBPM01、SBPM02 各有 1 个成功环次、各 20000 点。
- **影响**：该段可用设备从 20 台降为 2 台 —— 后续任何跨设备对齐只能基于 2 台。这是「部分成功段」在现实中的样子。
- **版本**：名义 `89bb146`（但与部署不一致，见 case-04）。
- **根因证据**：`logs/capture-BI-5Hz-20000-70min-20261002-230306-24fbc7de-eec1-4e25-a50f-6f4f29fd6c46.json`；同类现象见 `docs/handoffs/TASK_HANDOFF_2026-08-28_17-17-38_UTC+0800.md`（47 台全 `no completed matching file`，五区抽样 `/home/data/bram_result.txt` 均 0 字节）。
- **替代解释**：① 设备侧 BRAM 未写入（`SHINE.cpp` 的 `fpga_test()` 无条件 `return 0`，`task4()` 仍打印 `Data Save Done`）—— 交接记录标为 `[Inference]`，非定论；② 采集端等待不足 —— 已被否定（600 s 内 893 个设备轮次仍无有效文件；绕过 Candidate 用设备本机 `caput` 同样为空）。
- **修复**：设备侧根因不在本仓库（越界）。系统侧应对是段身份 `request_id + capture_sequence` 与「禁止隐式拼接数据段」。
- **验证**：日志自带 requested/succeeded/failed 与实际落盘路径，可与 `/SHINE_Data` 交叉核对。
- **未决**：18 台零字节的设备侧真实根因仍未由设备组确认。

### case-03　2026-10-02 采集被服务关停中断 — `已证实`

- **现象**：`request_id=5c9321c5-…`，100 Hz / 1800 s，22:16:33 提交 → 22:19:40 running → **22:20:27 cancelled**，`message="capture cancelled during service shutdown"`。
- **影响**：启动约 4 分钟后被打断，无完整数据落盘。
- **根因证据**：`logs/capture-BI-20261002-221633-5c9321c5-35d8-4075-80b3-4b3111afebf4.json`。
- **替代解释**：文案写的是 service shutdown 而非 operator cancel，故不支持「用户主动取消」；22:53 有第二个任务在同一服务上被接受，说明服务已重启。
- **修复**：未在仓库中找到专门修复。后续发布纪律要求「切换前确认无 accepted/running 任务」（`交付/20261026-timing-10hz-r1/evidence/deploy.deploy.sh` 的事务守卫）。
- **未决**：关停原因（部署/重启/崩溃）无记录；当时是否已有该守卫无法确认（部署版本 ≠ 任何提交）。

### case-04　现场部署无法用任何 git 提交定位 — `已证实`

- **现象**：2026-10-02 22:53 的采集以 `frequency_hz=5.0` 被服务端 **accepted**；而国庆前最后提交 `89bb146` 的 `_CAPTURE_INTERVAL_SECONDS` 只有 `1000/100/50/2`，`legacy/adapter` 也只有 `100/50/1000/2` 分支 —— 5 Hz 必然 `ServerSettingsError`。
- **影响**：任何「某版本引入/修复某缺陷」的归因在 2026-10-02 前后都不成立；现场二进制身份不可考。
- **根因证据**：`logs/capture-BI-5Hz-20000-20261002-225334-3d53c87f-*.json`（`accepted=true`）；`git show 89bb146:src/waveform_storage/acquisition/runtime.py` 第 477–482 行；`git log -S'4200' -- src/waveform_storage/acquisition/runtime.py`（仅命中 `61b47db`）；交付记录中最早带 `source_revision` 的是 `交付/20261008-history-release-r4/operator/BUILD-INFO`（`51afde8`，`source_state=working-tree`）。
- **替代解释**：① 5 Hz 由 `WAVEFORM_CAPTURE_FREQUENCY_HZ` 绕过 —— 不支持，该变量只覆盖 GUI 读 PV 步骤，服务端白名单仍拒绝；② 日志是仿真 —— 不支持，路径是真实 `/SHINE_Data/AC/LA/20261002/raw/BIData/` 且给具体点数；③ 历史被改写/丢分支 —— 无法排除，但 `--all` 显示该区间零提交，且 `61b47db` 是一次超大合并提交（含 `config/devices.operator.json` 11496 行），与长期未提交的现场改动合并提交一致。
- **修复**：`61b47db` 合并现场工作树；发布流程自 r4 起引入 `BUILD-INFO` / `release-pair.json` / `source_manifest_sha256`。
- **未决**：2026-10-02 现场二进制 SHA-256 未知；`source_state=working-tree` 意味着即使有 `BUILD-INFO`，源码也不完全等于 `source_revision`（r4 的 `operator_window.py` 清单哈希 `077e0aa4…` ≠ `51afde8` 的 blob SHA-256 `2bfd4068…`）。

### case-05　2026-10-07 前服务端无频率一致性校验 — `已证实`

- **现象**：`FREQUENCY_MISMATCH` 及其判定逻辑**首次出现在 `61b47db`（2026-10-07 16:30:43）**；此前 `handle()` 直接 `tasks.submit(request)`，不读 timing PV、不比对。
- **影响**：请求频率决定 `capture_interval_seconds()` 等待值与下游声明的采样率。若与机器实际频率不符，段内 20000 点覆盖的真实时长、以及任何由采样率推导的时间轴/频率轴都会按错误比例解释 —— 这是「时基偏移」最典型的发生机制。
- **根因证据**：`git log --all -S'FREQUENCY_MISMATCH'`（唯一命中 `61b47db`）；`src/waveform_storage/acquisition/server.py:561-589`（读 PV + `math.isclose(rel_tol=1e-6, abs_tol=1e-6)` + `FREQUENCY_MISMATCH`）；`apps/acquisition_server/main.py:146`；`runtime.py:292`。
- **替代解释**：「客户端校验即可」不成立 —— 正式 GUI 确实校验（`apps/operator_gui/candidate_backend.py:85-91`，不一致抛 `RuntimeError` 且不发请求），但覆盖不到运维客户端/脚本路径。
- **修复**：`61b47db`（服务端强制校验）+ `cae6b64`（前端不再允许指定频率）。
- **验证**：`tests/test_acquisition_server.py` 与 `tests/test_waveform_agent_v2.py`；286 项质量门 `OK`（`交付/20261026-timing-10hz-r1/evidence/quality.log`）。
- **未决**：2026-10-07 之前完成的采集是否曾以不一致频率提交，无法核实（无该期间的 PV 记录）；`apps/operator_gui/experimental_backend.py:79` 在 HEAD 仍读 `WAVEFORM_CAPTURE_FREQUENCY_HZ`（实验 GUI 路径）。

### case-06　历史页把 bunchID 差值 ÷10⁶ 当「数据时长（秒）」— `已证实`

- **现象**：对齐完成后显示「数据时长：X.XXXXXX s」，tooltip 写「最后一个 bunch ID 减第一个 bunch ID，换算为秒」，实现 `seconds = (int(ids[-1]) - int(ids[0])) / 1_000_000`。
- **触发**：任意一次多设备严格对齐完成后刷新标签。
- **影响**：该数值被用来判断「本次采集有多长」以及是否满足频谱最短时长门槛。它隐含一个**未声明**的假设：bunchID 是 1 MHz 计时钟且序列无缺口。步长不属于该假设、或 ID 有缺口时，显示的秒数会偏离真实记录时长。
- **版本**：引入 `61b47db`（2026-10-07，`operator_window.py:1243-1248`，tooltip 在 `:572-574`）；`2be9026`（2026-10-12）重构为 `_duration_status_text` 但除式不变（`:791-796` 与 `:1690` 两处）；`51afde8`（r4 的 `source_revision`）第 1271 行仍含该式；**移除于 `f7f28fb`（2026-10-19）**。
- **替代解释**：**这个除法并非总是错的。** 本次审计在真实 fixture 上验证：2026-10-12 任务 seq0 主流设备原始跨度 `(末−首)/1e6 = 39.998 s`，而 `20000 点 / 500 Hz = 40.000 s` —— 对步长 2000、500 Hz 的主簇设备，该换算成立（说明 bunchID 确实近似 1 MHz 计时钟）。缺陷在于：① 假设未声明；② 对步长 28–76 的 `AC_LA_L1_BI_COLDBPM05` 不成立；③ 无缺口检查时会高估时长。
- **根因证据**：`git show 61b47db:src/waveform_storage/gui/operator_window.py` 第 572-574、1243-1248 行；`git show 2be9026:…` 第 791-796、1690 行；`git show 51afde8:…` 第 1271 行；HEAD `src/waveform_storage/gui/operator_window.py:1047-1058`（改为「分析器推算跨度」，取 `_analysis_quality_preview` 的 `duration_seconds`）；`git show f7f28fb:…`（新 tooltip「来自分析器建立的相对时间轴；不是 bunchID 数值换算结果」）。
- **修复**：`f7f28fb` —— 改显「分析器推算跨度」；新增 `processing/bunch_id_diagnostics.py`（模块 docstring：*never converts bunchID values to time*）；弹窗明确「相邻采样点的 bunchID 差值，不是时间间隔」。
- **验证**：241 项完整质量门（`交付/20261016-history-quality-r1/evidence/full-quality.log`）；4 项 `bunch_id_diagnostics` 测试；8 张双分辨率 offscreen 截图；`docs/CURRENT_STATUS.md:121` 记录「步进」改为「相邻数据编号的间隔」。
- **未决**：2026-10-07 至 10-18 窗口内是否有操作员据错误秒数做判断 —— 仓库无操作日志、无用户报告；HEAD 的「分析器推算跨度」仍有残余风险：`analysis/loaders.py:_id_times` 用「众数步长 ≡ 一个采样周期」建相对时间轴，共同 ID 集合带缺口时缺口会被压缩而非保留为间隔（本案例 5 段均为连续窗口，未受影响）。

### case-07　2026-10-12 任务 25 台严格交集塌缩至 1.44%–3.11% — `已证实`

> 本次审计范围内**唯一**「国庆后真实数据出现严重对齐异常」的原始证据。

- **现象**：`request_id=22833275-5e77-41c5-b703-f306accde164`（存储日期 2026-10-12，500 Hz，5 段，每段 25 台 × 20000 点）。

  | capture_sequence | 严格共同点 | 保留率 | 分析器推算跨度 |
  | ---: | ---: | ---: | ---: |
  | 0 | 422 | 2.11% | 0.842 s |
  | 1 | 621 | 3.11% | 1.240 s |
  | 2 | 455 | 2.28% | 0.908 s |
  | 3 | 375 | 1.88% | 0.748 s |
  | 4 | 288 | 1.44% | 0.574 s |

  留一检查：排除 `AC_LA_L1_BI_COLDBPM05` 后共同点升至 **19570 / 19528 / 19532 / 19547 / 19542**；排除其他任意单台仍为 288–621。
- **触发**：同时选择该 COLD BPM 与其余 24 台做 strict 对齐。目标设备相邻步长 28–76（众数 76），其余 24 台恒为 2000。
- **影响**：97–98% 采样点被交集丢弃；推算跨度 0.574–1.240 s 低于频谱 5 s 最短记录门槛，该任务 5 段在频谱页无法分析。
- **版本**：`368a9aa`（2026-10-13，r1 交付 `source_revision`）；`f7f28fb`（2026-10-19）把核验代码入库。
- **根因证据**：`outputs/history-ui-validation-20261016/real-data-20261012-all-segments.json`、`…-sequence-0..4.json`、`bunch-id-fixtures/22833275-…_S00000..S00004.npz`（附 `fixture_sha256`）；`交付/20261016-history-quality-r1/README.md`；`docs/CURRENT_STATUS.md:169`；**本次独立复算** `verify_fixtures.py` 全部一致。
- **替代解释**：① 我方算法 bug —— 被留一检查排除（移除该设备后共同点立即回到 97.6%–97.9%）；② 该设备硬件/时钟故障 —— 交付记录明确「不单独证明物理时钟或硬件故障」，本次同意，步长差异只证明编码/时基不同；③ 采集频率与 PV 不一致 —— 2026-10-12 已被 `FREQUENCY_MISMATCH`（2026-10-07 起）排除，且 500 Hz ↔ 步长 2000 在 1 MHz 假设下自洽；④ 两台设备真的在采不同物理事件 —— 无法排除，无设备侧同步信号记录；⑤ 设备已被修复 —— 无设备组反馈记录。
- **修复**：`f7f28fb` 新增 `processing/bunch_id_diagnostics.py`：对齐前统计每台设备相邻 ID 步长、众数、是否与多数设备不一致；异常时**必须显式确认**才继续 strict 对齐；保留全部设备，不自动剔除、不缩放、不插值。
- **验证**：交付记录（本机激活 + 真实桌面 smoke，PID `3120745`，二进制 SHA-256 `c88b8213…`）；241 项质量门；4 项诊断测试；8 张两分辨率 offscreen 截图；本次 fixture 复算。
- **未决**：该设备步长 28–76 是固件/配置差异还是时钟故障，仓库内无裁决依据；25 台真实 X/Y 联合 GUI 补测按用户要求未执行；未做 47 台全量步长普查。

### case-08　timing PV = 10 Hz 时整条 v2 采集通道被拒 — `已证实`

- **现象**：前端「采集参数 → 当前频率」显示「暂不可用」。服务端原文：`accepted=False error_code=TIMING_FREQUENCY_FAILED message="unsupported capture frequency 10 Hz; supported: 1000, 500, 100, 50, 5, 2 Hz"`。
- **触发**：PV `AC-LA-INJ1-TIM:WRN1:MCFQ8`（`10.101.2.1:6310`）读数为 10 Hz，而 `_CAPTURE_INTERVAL_SECONDS` 缺 `10.0`。
- **影响**：**不是显示故障。** 同一白名单校验挡在 GUI `start_capture`、Agent API v2 `control/captures` 与服务端 `handle()`（服务端提交时读 PV 并调 `capture_interval_seconds()` 算等待值），因此 10 Hz 下整条 v2 采集通道不可用。
- **版本**：`89bb146`（仅 4 档）→ `61b47db`（补 500/5）→ `5f17b67`（r1 源码基线仍无 10）→ **`cae6b64`（2026-10-26 20:24:54）修复**。
- **根因证据**：HEAD `src/waveform_storage/acquisition/runtime.py:491-501`（含 `10.0: 2100`）、`:524` 与 `:539-550`（`read_timing_frequency` 调 `capture_interval_seconds`，`KeyError`→`unsupported capture frequency`）、`:292`（采集循环同样调用）；`server.py:561-589`；`交付/20261026-timing-10hz-r1/README.md:7-32`；`docs/CURRENT_STATUS.md:25-49`。
- **替代解释**：① 隧道/ZMQ/systemd/EPICS 故障 —— 已被发布前实测排除（隧道 master 存活、`health` accepted、服务 active 无在跑任务，错误内容是频率数值本身而非连接超时）；② GUI 显示层 bug —— 不成立，修复后同路径 `get_timing_frequency` 返回 `frequency_hz=10.0`；③ PV 瞬时抖动 —— 不成立，打包与远程界面均显示 10 Hz。
- **修复**：`cae6b64` —— 新增 `10.0: 2100`（现场确认：20000 触发 / 10 Hz = 2000 s + 余量）；测试改为断言 `10 → 2100`、拒绝样例改 20 Hz；`openapi.json` enum 加 `10`；GUI 去掉频率下拉框，改只读显示并在采集前重读跟随。
- **验证**：286 项质量门 `OK`；61 项定向；协议 smoke 5 端点通过（1 任务/5 段/125 文件）；`live-timing-frequency.json` 返回 `accepted=true, frequency_hz=10.0, source=timing_pv`；`deploy.json` 记录 `MainPID=1991109`、`ActiveState=active`、二进制哈希一致。
- **未决**：10 Hz 真实采集/下载/HDF5 落盘**从未验证**（未发送任何真实采集请求）；真实桌面 GUI 复验未做（`GUI SMOKE PENDING`）；暴露期已由 EPICS Archiver 界定为「至少 2026-08-17 起 PV 就多次读到 10 Hz」（case-09 / case-12），但具体哪些窗口有采集被拒仍无记录；`phy01` 独立会话未验证。

### case-09　timing PV 是可变的运行频率读数：10 Hz 至少自 2026-08-17 起反复出现，不存在「国庆前后一次性 5→10 切换」— `已证实`

> 本案例原为「推断」，2026-10-29 由 Lead 提供 EPICS Archiver 原始序列、本次审计独立复算后升级为「已证实」，并推翻了原假设。

- **现象**：Archiver 显示 `AC-LA-INJ1-TIM:WRN1:MCFQ8` 在 2 / 5 / 10 / 20 / 50 / 100 / 1000 Hz 之间反复跳变。10 Hz 记录出现在 **2026-08-17、08-27、08-28、09-04、10-01、10-23、10-27**；2026-08-17 当天 78 分钟内 10/2 交替 6 次。2026-10-29 live 窗口 context 读数为 50 Hz（2026-10-28T09:28:03Z）。
- **触发**：现场加速器运行态频率调整，与 Waveform 软件发布节奏无关。
- **影响**：① **推翻「国庆后 PV 变为 10 Hz」这一因果前提** —— 10 Hz 是长期存在的运行态读数，任何时刻读到 10 Hz 都会触发 case-08 的白名单缺口；② 历史采集的采样率**不能**由「当前 PV 读数」推断，必须取自该任务记录（`CaptureRunSummary.frequency_hz`）；③ 2026-10-26 修复当天归档内零变化点，最后一次记录为 2026-10-23T13:36:41Z 的 10 Hz → 修复时 PV 确实处于 10 Hz，与 `docs/CURRENT_STATUS.md:28` 一致。
- **预期 vs 实际**：若「国庆后对齐异常」源于 PV 在假期后切到 10 Hz，则 2026-10-08 之前 PV 不应出现 10 Hz → 实际 10 Hz 在 **2026-08-17（国庆前 45 天）** 已有归档记录，并在 08-27、08-28、09-04、10-01 反复出现。**假设被推翻。**
- **根因证据**（5 个只读 Archiver 窗口，`strategy=lastSample`，全部 `source_id=TIM_ARCHIVER_URL`，逐点在本次审计中独立复算一致）：

  | 窗口 | start → end（UTC） | max_points | 返回点数 | bin_seconds | 关键点（UTC） |
  | --- | --- | ---: | ---: | ---: | --- |
  | A | 2026-08-15T00:00 → 2026-10-01T00:00 | 2000 | 42（in_range 41 + context 1） | 2031 | `08-17T06:14:50.469014Z=10`、`08-27T02:31:36.103140Z=10`、`08-28T08:11:06.830204Z=10`、`09-04T01:54:55.619560Z=10`、`09-04T09:31:10.691215Z=10`；另含 2/5/100/1000 Hz |
  | B | 2026-08-17T00:00 → 2026-08-17T08:00 | 500 | 7（in_range 6 + context 1） | 58 | `08-15T03:44:24.753965Z=2`、`06:14:50.469014Z=10`、`07:04:04.288342Z=2`、`07:04:48.727715Z=10`、`07:13:20.706811Z=2`、`07:18:08.493513Z=10`、`07:32:12.955437Z=2` |
  | C | 2026-10-01T00:00 → 2026-10-02T00:00 | 500 | 2（in_range 1 + context 1） | 173 | `09-29T20:53:13.709428Z=5`、`10-01T09:59:55.853957Z=10`（= 10-01 17:59:55 +0800，**国庆假期首日**） |
  | D | 2026-10-23T00:00 → 2026-10-28T00:00 | 2000 | 16 | 216 | `10-23T12:02:27.767979Z=10`、`12:17:30.650561Z=100`、`12:25:31.951082Z=10`、`12:38:51.326852Z=1000`、`12:46:20.066366Z=10`、`13:21:30.271680Z=10`、`13:36:41.419348Z=10`；`10-27T02:45:28.069522Z=10`、`13:02:41.497781Z=20`、`13:05:00.699117Z=5`、`13:09:30.980527Z=10`、`13:25:36.805871Z=5`、`14:21:47.047689Z=50` |
  | E | 2026-10-26T00:00 → 2026-10-27T00:00 | 500 | 1（**in_range 0**，`data_state=context_only`） | 173 | 唯一 context 点 `10-23T13:36:41.419348Z=10` → 修复当天归档值未变，仍是 10 Hz |

  另有 `archiver_resolve_pvs` 确认该 PV 解析到 `TIM_ARCHIVER_URL`（`http://10.101.9.19:17668`），与 `src/waveform_storage/acquisition/runtime.py:503` 的 `TIMING_FREQUENCY_PV` 字面一致。
- **替代解释**：
  1. **归档是降采样视图**（部分成立，必须一并引用）：每窗口 `segments[].downsampled=true`、`bin_seconds` 15–2031 s，因此本案例只声称「**归档记录时刻的读数**」，不声称 raw 全量事件序列。粗 bin 会吞掉短时跳变 —— 同一 08-17 区间，窗口 A（bin=2031 s）只看到 1 个 10 Hz，窗口 B（bin=58 s）看到 2 个。但即便窗口 A 也仍记录到 08-17、08-27、08-28、09-04 的 10 Hz，**不影响「10 Hz 长期存在」这一结论**。
  2. 「10 Hz 只在 08-17 短暂抖动」：**不成立** —— 08-27、08-28、09-04、10-01、10-23、10-27 均有 10 Hz 记录。
  3. 「Archiver 的 PV 与软件读的不是同一个」：**已排除** —— 名称解析成功且字面一致。
  4. 「PV 值的物理含义不明」（是否机器实际束流频率、是否含档位语义）：**成立且未解决** —— 但服务端读的就是这个 PV，对软件行为而言等价。
- **修复与验证**：无需修复（环境侧运行态）。系统侧改进：`cae6b64` 之后采集前必定重读 PV 并跟随，PV 跳变不再造成频率错配。验证方式：本次审计用 MCP `archiver_query_series` 以相同 PV 与 5 个窗口重新查询，逐点核对时间戳与数值，并与 Lead 给出的点数（7 / 42 / 2 / 16 / 1）逐一对照，**全部一致**。
- **未决**：① PV 在 2/5/10/20/50/100/1000 Hz 间跳变的物理/运行含义未由运行值班确认；② 归档为降采样视图，精确到逐次变化需直接查 Archiver 原始接口（本工具上限 `max_points=20000`）；③ 10 Hz 窗口内是否有采集被提交并失败，仓库内无记录（见 case-12）。

### case-10　对 `PRAB_PLAN` 措辞的裁定 — `推断`

见第 1 节与 [docs/waveform/fault-history-and-version-changes.md](../../../../docs/waveform/fault-history-and-version-changes.md) 第 6 节（措辞差异声明）。

- **证据**：`git log --all --date=iso --reverse`（零提交区间）；`git log -- processing/alignment.py` + `git show 25e6b73 -- …`（算法未变）；`grep -rn 偏移\|对齐异常 docs/`（零命中）。
- **替代解释**：计划措辞可能来自会议/口述等仓库外来源，无法核实；若确有，应补为可引用的外部材料，否则不得作为事实入库。
- **未决**：`PRAB_PLAN` 的「国庆后对齐异常」是否有仓库之外的来源？若有，应降级为「转述」并补入 evidence-index。

### case-11　`interval=10` 语义歧义（10 分钟 vs 10 Hz）— `待核实`

- **现象**：交接记录原文 —— 「旧版软件的 `interval=10` 表示 10 分钟，不是 10 Hz」「`attempted_cycles=19` 不是硬件采样点数，频率语义仍需设备/需求侧确认」。
- **影响**：若把 10 分钟读成 10 Hz，等待值/时长判断差 60 倍，下游按错误频率声明采样率，则时间轴与频率轴全部按错误比例解释 —— 这正是「对齐/时基偏移」最典型的表现形式。
- **证据**：`docs/handoffs/TASK_HANDOFF_2026-08-28_17-17-38_UTC+0800.md`（`[Constraint]` 段）；`docs/history/2026-07/线上运行基线调查.md:1.3`（线上日志两次请求为 2 Hz / 600 s，「在取得原始请求帧或线上源码前仍不能确认具体换算位置」）。
- **替代解释**：该歧义**只存在于文档与旧代码注释中，从未在真实数据分析中触发** —— 很可能；仓库内没有任何采集记录、分析结果或用户报告显示曾把 `interval` 当频率使用。
- **修复**：`61b47db` 的协议 v2 显式拆分 `frequency_hz` 与 `duration_seconds`，字段名自带单位。
- **未决**：2026-10-07 之前的分析结果（若存在）是否用过被误读的频率参数，需要历史产物中的参数记录才能判断；频率语义至今无设备/需求侧确认结论。

### case-12　10 Hz 白名单缺口的可触发窗口自 2026-08-17 起即存在 — `已证实`

- **现象**：`_CAPTURE_INTERVAL_SECONDS` 在 2026-10-26（`cae6b64`）之前**从不含** `10.0` 档；而 Archiver 显示 PV 自 2026-08-17 起在多个日期记录到 10 Hz。二者叠加：这些窗口内任何走 v2 采集路径的请求都会被 `TIMING_FREQUENCY_FAILED` 拒绝。
- **触发**：在 PV 读数为 10 Hz 的时刻提交采集（GUI `start_capture` / Agent API v2 `control/captures` / 服务端 `handle()`）。
- **影响**：把 case-08 的暴露期从「2026-10-26 前后」扩展到「**至少 2026-08-17 至 2026-10-26 的若干窗口**」，并说明该缺陷与国庆假期**无因果关系** —— 它是「按已知档位枚举的白名单」与「运行态多值 PV」之间的恒定不匹配。
- **版本**：`89bb146`（4 档：1000/100/50/2）→ `61b47db`（补 500/5，仍无 10）→ `cae6b64`（新增 `10.0: 2100`，缺口关闭）。
- **预期 vs 实际**：预期白名单覆盖 PV 可能出现全部档位，或遇未覆盖档位时给出可操作降级路径 → 实际为枚举式白名单，不在表内即整体拒绝。
- **根因证据**：`git show 89bb146:src/waveform_storage/acquisition/runtime.py` 第 477-482 行；`git log -S'4200' -- src/waveform_storage/acquisition/runtime.py`（仅 `61b47db`）；`git log --all -S'10.0: 2100'`（仅 `cae6b64`）；`src/waveform_storage/acquisition/runtime.py:539-550`；`docs/CURRENT_STATUS.md:33-34`（10 Hz 从未被支持，原 `tests/test_acquisition_server.py` 明确断言 10 Hz 必须被拒绝）；Archiver 窗口证据见 case-09。
- **替代解释**：① 这些窗口内实际没有采集需求，因此从未暴露 —— **很可能**，仓库内没有 2026-08-17 至 10-25 的采集失败记录；但不能因此断言缺陷不存在（代码路径恒定且服务端提交时必读 PV）；② Archiver 记录的 10 Hz 不代表机器真在 10 Hz 运行 —— 可能，但服务端读的就是这个 PV，对软件行为等价；③ 20 Hz / 1000 Hz 等档位同样构成缺口 —— 部分成立：1000 Hz 在表内，**20 Hz 不在表内**（Archiver 2026-10-27T13:02:41Z 有 20 Hz 记录），属同类潜在下一个缺口，但本案例不把它算作已发生事故。
- **修复与验证**：`cae6b64` 补齐 10 Hz 档位（`交付/20261026-timing-10hz-r1/evidence/live-timing-frequency.json` 修复后返回 `10.0`；`quality.log` 286 项 OK）。**注意**：本轮只补 10 Hz，白名单仍是枚举式，遇未列出档位（如 20 Hz）仍会整体拒绝 —— 这是设计选择而非遗漏，需现场负责人裁决是否改为显式可配置表。
- **未决**：① 2026-08-17 至 10-25 是否有采集因 10 Hz 被拒，需现场 `state/*.json` 或服务端日志，仓库内没有；② 白名单继续手工枚举还是改为现场可配置档位表 —— 待现场负责人裁决（当前 20 Hz 仍不在表内）。

---

## 5. 与 `PRAB_PLAN` 措辞的差异（摘要）

| `PRAB_PLAN` 说法 | 位置 | 裁定 | 证据支持的替换措辞 |
| --- | --- | --- | --- |
| 「国庆前后的对齐逻辑差异」 | 第 14 行 | **不成立** | 「国庆前后**历史检索与时间基准呈现**有差异（2026-10-07 引入 bunchID÷10⁶ 当秒数，2026-10-19 移除并加原始步进预检查）；对齐算法本身自 2026-07-25 起未变。」 |
| 「含国庆后对齐问题根因与修复对比」 | 第 37 行（文档标题） | **需改** | 「含 2026-10-12 真实任务严格交集塌缩（1.44%–3.11%）的根因与 2026-10-19 诊断修复对比」 |
| 「国庆后波形对齐偏移」 | 第 73 行 | **不成立（偏移未证实）** | 「2026-10-12 真实任务跨 25 台严格共同点仅剩 1.44%–3.11%，根因为单台 L1 冷 BPM 的 bunchID 步长 28–76 与其余 24 台的 2000 不相容」 |
| 「彻底查清并整理包括国庆后 Waveform 对齐异常在内的真实历史案例」 | 第 104 行 | **部分成立** | 「整理真实历史案例，其中 2026-10-12 任务的对齐塌缩是最接近『国庆后对齐异常』的现场证据；不得表述为版本回归」 |

完整差异声明与引用要求见核心文档第 6 节。

---

## 6. 遗留缺口（按补证据的性价比排序）

1. ~~**timing PV 的历史序列**~~ —— **2026-10-29 已补齐**：EPICS Archiver（`source_id=TIM_ARCHIVER_URL`）5 个窗口的只读查询已由 Lead 提供、本次审计独立复算一致。结论见 case-09（PV 是可变运行态读数，10 Hz 至少自 2026-08-17 起反复出现）与 case-12（白名单缺口的可触发窗口自 08-17 起即存在）。这条缺口关闭后，**case-09 从「推断」升级为「已证实」，并推翻了「国庆后 PV 才变 10 Hz」的前提**。
2. **2026-10-02 现场服务端二进制的 SHA-256 与源码清单**（case-04）。没有它，国庆前后的行为差异无法与代码版本对齐。
3. **`AC_LA_L1_BI_COLDBPM05` 的设备侧说明**（固件版本 / bunchID 编码语义 / 是否已修复）。决定 case-07 是「设备差异」还是「设备故障」。
4. **`PRAB_PLAN` 「国庆后对齐异常」的外部来源**（会议记录 / 口述 / 设备组反馈）。若存在，必须降级为「转述」补入 evidence-index。
5. **2026-10-07 至 2026-10-18 窗口内的操作员使用记录**（case-06）。决定该显示缺陷是否有真实误读后果。
6. **10 Hz 下的真实采集闭环**（case-08）。当前完全未验证，2100 s 分段与 20000 点目标是否成立未知。
7. **2026-08-17 至 2026-10-25 是否有采集因 10 Hz 被拒**（case-12）。需要现场 `state/*.json` 或服务端日志 —— 仓库内只有 2026-10-02 的三个采集 JSON，覆盖不到这些窗口。
8. **PV 多值性的物理含义与白名单策略**（case-09 / case-12）。Archiver 显示 PV 在 2/5/10/20/50/100/1000 Hz 间跳变，而白名单是枚举式（当前 **20 Hz 仍不在表内**）。是继续手工枚举还是改为现场可配置档位表，需现场负责人裁决。
9. **Archiver 的原始（非降采样）变化序列**。本次 5 个窗口全部 `downsampled=true`（`bin_seconds` 15–2031 s），只能声称「归档记录时刻的读数」；逐次变化需直查 Archiver 原始接口。
