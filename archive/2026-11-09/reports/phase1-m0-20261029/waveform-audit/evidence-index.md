# 证据索引（Waveform 取证审计）

每条证据给出**稳定定位**：commit sha / `文件:行` / 日志路径 / 交付目录（含目录内文件）。所有路径以 Waveform 仓库根 `/home/whloong/waveform-storage/waveform-storage-system` 为基准（标注 `[prab]` 的除外，那是 `accelerator-rag-prab` 根）。

- **只读声明**：本审计对 Waveform 仓库仅执行 `git log` / `git show` / `cat` / `grep` / `sha256sum` / 读取 `.npz`，未写入任何文件、未 commit、未重启服务。
- **审计基线**：`dc50e08a2beddff42c297a237b3f3312f5c24ac9`（2026-10-26 21:06:55 +0800）。工作树有 1 个未提交修改：`src/waveform_storage/application/agent_v2_service.py`（不属于对齐路径，本审计不依赖其内容）。

---

## 1. 审计基线

| 项 | 值 | 取值命令 |
| --- | --- | --- |
| HEAD 长 sha | `dc50e08a2beddff42c297a237b3f3312f5c24ac9` | `git rev-parse HEAD` |
| HEAD 短 sha | `dc50e08` | `git rev-parse --short HEAD` |
| HEAD 日期 | 2026-10-26 21:06:55 +0800 | `git log -1 --date=iso --format='%ad'` |
| HEAD 标题 | `docs: synchronize AOCI after PV frontend release` | `git log -1 --format='%s'` |
| 提交总数 | 42 | `git rev-list --count HEAD` |
| 未提交修改 | `M src/waveform_storage/application/agent_v2_service.py` | `git status --short` |
| 对齐算法源码 SHA-256 | `e8db12d72a0ad553130f0823a88b508ab0ec2a6b223fe90ad2b1abd8843d5346` | `sha256sum src/waveform_storage/processing/alignment.py` |
| 该文件 git blob | `d829d3232f9e91979a7bd9f9f7ce93d1e4819442` | `git rev-parse HEAD:src/waveform_storage/processing/alignment.py` |

---

## 2. 提交时间线（含零提交区间 —— case-10 的核心证据）

完整命令：`git log --all --date=iso --format='%h|%ad|%an|%s' --reverse`

### 2.1 国庆前后关键区间

```text
89bb146 | 2026-08-26 15:32:11 +0800 | feat: add one-minute capture option        ← 国庆前最后提交
   ⋮      （41 天 23 小时零提交，git rev-list 在此区间为空）
61b47db | 2026-10-07 16:30:43 +0800 | feat: complete waveform operations ...    ← 假期内首个提交
```

复现：
```bash
git log --all --date=iso --format='%h|%ad|%s' --reverse | sed -n '/89bb146/,/61b47db/p'
git log --all --since='2026-08-26 15:32:11 +0800' --until='2026-10-07 16:30:43 +0800' --oneline   # 空输出
```

### 2.2 与本审计相关的全部提交（11 条）

| commit | 日期（+0800） | 标题 | 关联案例 |
| --- | --- | --- | --- |
| `36a927b` | 2026-07-25 22:22:29 | chore: checkpoint local refactor safety baseline | case-01（对齐纯函数落盘）、case-10 |
| `0b5870c` | 2026-07-25 22:44:49 | refactor: separate storage plotting and legacy overlap | case-01 |
| `3a76c39` | 2026-07-25 22:48:33 | refactor: introduce retrieval application service | case-01 |
| `89bb146` | 2026-08-26 15:32:11 | feat: add one-minute capture option | case-04/05/08/10（国庆前基线） |
| `61b47db` | 2026-10-07 16:30:43 | feat: complete waveform operations and separate log dashboard | case-04/05/06/11 |
| `dbbc0d6` | 2026-10-08 17:28:49 | chore: archive state before spectrum analysis update | r4 构建上下文 |
| `2be9026` | 2026-10-12 15:22:56 | ui: refine history retrieval layout | case-06 |
| `368a9aa` | 2026-10-13 12:09:14 | chore(aoci): use host-safe overview chunk budget | case-07（r1 `source_revision`） |
| `f7f28fb` | 2026-10-19 10:14:52 | chore: checkpoint accepted history UI updates | case-06/07（修复） |
| `25e6b73` | 2026-10-20 10:43:00 | feat: freeze waveform agent HTTP API v1 | case-06/10（alignment.py 唯一后改） |
| `5f17b67` | 2026-10-22 16:47:37 | feat: add and harden scoped waveform agent API v2 | case-08（r1 源码基线） |
| `cae6b64` | 2026-10-26 20:24:54 | fix: follow timing PV and support 10 Hz acquisition | case-08/09（修复） |

### 2.3 `-S` 检索记录（用于证伪）

| 检索内容 | 命令 | 结果 |
| --- | --- | --- |
| 对齐算法是否变更 | `git log --all --format='%h\|%ad\|%s' -- src/waveform_storage/processing/alignment.py` | 仅 `36a927b`（2026-07-25）、`25e6b73`（2026-10-20） |
| `25e6b73` 对对齐算法的实际改动 | `git show 25e6b73 -- src/waveform_storage/processing/alignment.py` | 仅 `+metadata: dict = field(default_factory=dict, compare=False)` |
| 频率一致性校验引入时间 | `git log --all -S'FREQUENCY_MISMATCH'` | 唯一命中 `61b47db`（2026-10-07） |
| 5 Hz 等待值引入时间 | `git log --all -S'4200' -- src/waveform_storage/acquisition/runtime.py` | 唯一命中 `61b47db` |
| `WAVEFORM_CAPTURE_FREQUENCY_HZ` 变更 | `git log --all -S'WAVEFORM_CAPTURE_FREQUENCY_HZ'` | `dc3db91`（2026-08-26）、`61b47db`、`cae6b64` |
| bunchID 差值当秒数 | `git log --all -S'bunch ID 之差'` | `61b47db`（引入）、`cae6b64`（删除说明） |
| 「偏移」 | `git log --all -S'偏移'` | 仅 `36a927b`（基线快照）→ 无对齐偏移相关提交 |
| 「对齐异常」 | `grep -rn '对齐异常' docs/` | **零命中** → case-10 的直接反证 |

---

## 3. 源码定位（HEAD 行号）

| 定位 | 内容 | 关联案例 |
| --- | --- | --- |
| `src/waveform_storage/acquisition/runtime.py:491-501` | `_CAPTURE_INTERVAL_SECONDS`，含 `10.0: 2100`（`:498`）与 `Field-confirmed on 2026-10-26` 注释（`:495-497`） | case-08/09 |
| `src/waveform_storage/acquisition/runtime.py:503-505` | `TIMING_FREQUENCY_PV = "AC-LA-INJ1-TIM:WRN1:MCFQ8"` / `TIMING_EPICS_ADDRESS = "10.101.2.1:6310"` | case-08 |
| `src/waveform_storage/acquisition/runtime.py:507-533` | `read_timing_frequency()`：`:524` 调用 `capture_interval_seconds(frequency)` 做白名单校验 | case-08 |
| `src/waveform_storage/acquisition/runtime.py:539-550` | `capture_interval_seconds()`：`KeyError` → `unsupported capture frequency {value:g} Hz; supported: …` | case-08 |
| `src/waveform_storage/acquisition/runtime.py:292` | 采集循环内 `interval = capture_interval_seconds(plan.frequency_hz)` | case-08 |
| `src/waveform_storage/acquisition/server.py:561-589` | 提交时 `_read_frequency_bounded()` 读 PV + `math.isclose(rel_tol=1e-6, abs_tol=1e-6)` → `FREQUENCY_MISMATCH`（`:586`） | case-05/08 |
| `src/waveform_storage/acquisition/server.py:621-640` | `_read_frequency_bounded()`：独立线程 + 事件超时，避免 EPICS 卡死 REP socket | case-08 |
| `apps/acquisition_server/main.py:146` | `frequency_reader=lambda: read_timing_frequency(...)` | case-05/08 |
| `apps/operator_gui/candidate_backend.py:79-100` | `start_capture()`：先读 PV（`:85`），请求频率与之不符则 `RuntimeError` 且不发请求（`:86-91`） | case-05 |
| `apps/operator_gui/experimental_backend.py:79-90` | HEAD 仍读取 `WAVEFORM_CAPTURE_FREQUENCY_HZ`（实验 GUI 路径） | case-05 未决 |
| `src/waveform_storage/processing/alignment.py:1-10` | 模块 docstring：*does not guess scale factors or convert between incompatible device timebases* | case-01 |
| `src/waveform_storage/processing/bunch_id_diagnostics.py:1-6` | 模块 docstring：*never converts bunchID values to time* | case-06/07 |
| `src/waveform_storage/processing/bunch_id_diagnostics.py:40-47` | `RawStepReport.majority_step / has_clear_majority / raw_step_compatible` | case-07 |
| `src/waveform_storage/analysis/loaders.py:153-166` | `_id_times()`：`step = Counter(differences).most_common(1)[0][0]`，`slots=(id-id[0])/step`，`times=slots/sample_rate` — 众数步长 ≡ 一个采样周期 | case-06 未决 / case-07 |
| `src/waveform_storage/analysis/engine.py:22-35` | `_prepare()`：`times` 来自调用方；`rate = series.sample_rate_hz or 1/median_dt` | case-06 |
| `src/waveform_storage/analysis/engine.py:58-64` | `result.duration_seconds = float(times[-1])` — 「跨度」由此得出 | case-06 |
| `src/waveform_storage/analysis/engine.py:82` | `grid = np.arange(count, dtype=float) / rate` | case-06 |
| `src/waveform_storage/gui/operator_window.py:1047-1058` | `_duration_status_text()` — HEAD 显示「分析器推算跨度」，取 `_analysis_quality_preview` 的 `duration_seconds` | case-06 |
| `src/waveform_storage/gui/operator_window.py:1315,1333` | `_set_frequency_display("暂不可用", available=False)` — 故障表象文案 | case-08 |
| `src/waveform_storage/application/agent_v2_service.py:45-54` | `alignment_source_hash = sha256(alignment.__file__ 源码)` — **系统既有的对齐算法源码哈希机制** | front-matter |
| `src/waveform_storage/application/agent_v2_service.py:618-619` | `algorithm_version='bunch-id-alignment:'+hash[:16]` / `algorithm_source_sha256=hash` | front-matter |
| `src/waveform_storage/gui/spectrum_panel.py:350-369` | `use_alignment()`：采样率来自历史任务记录，缺失时要求人工填写 | case-07 影响 |

---

## 4. 历史提交内定位（已删除代码的证据）

这些内容在 HEAD 已不存在，只能通过 `git show <sha>:<path>` 引用。**引用时必须带 sha，不得写成当前代码。**

| 定位 | 内容 | 关联案例 |
| --- | --- | --- |
| `git show 61b47db:src/waveform_storage/gui/operator_window.py` 第 **1243-1248** 行 | `_set_data_duration()`：`seconds = (int(ids[-1]) - int(ids[0])) / 1_000_000` | case-06 |
| 同上 第 **572-574** 行 | `data_duration_label` tooltip：「最后一个 bunch ID 减第一个 bunch ID，换算为秒」 | case-06 |
| `git show 2be9026:src/waveform_storage/gui/operator_window.py` 第 **791-796** 行 与 第 **1690** 行 | 重构后仍保留 `… / 1_000_000`（两处） | case-06 |
| `git show 51afde8:src/waveform_storage/gui/operator_window.py` 第 **1271** 行 | r4 的 `source_revision` 仍含该除式 | case-06 |
| `git show f7f28fb:src/waveform_storage/gui/operator_window.py` | 新 tooltip「来自分析器建立的相对时间轴；不是 bunchID 数值换算结果」；「相邻采样点的 bunchID 差值，不是时间间隔」 | case-06 |
| `git show 89bb146:src/waveform_storage/acquisition/runtime.py` 第 **477-482** 行 | `_CAPTURE_INTERVAL_SECONDS` 仅 `1000.0:2 / 100.0:12 / 50.0:22 / 2.0:512` | case-04/08 |
| `git show 89bb146:src/waveform_storage/legacy/acquisition_agent_adapter.py` 第 **367-380** 行 | legacy 代理仅 `100 / 50 / 1000 / 2` 四分支 | case-04/08 |
| `git show 61b47db:src/waveform_storage/acquisition/server.py` | 首次出现 `FREQUENCY_MISMATCH` | case-05 |
| `git show 25e6b73 -- src/waveform_storage/processing/alignment.py` | 唯一改动：`DeviceSeries` 增加 `metadata` 字段 | case-10 |

---

## 5. 日志（真实运行事故原始记录）

目录：`logs/`

| 路径 | 关键字段 | 关联案例 |
| --- | --- | --- |
| `logs/capture-BI-5Hz-20000-70min-20261002-230306-24fbc7de-eec1-4e25-a50f-6f4f29fd6c46.json` | `request_id=24fbc7de-…`；`frequency_hz=5.0`；`expected_points=20000`；`duration_seconds=4200`；`final_response.status=failed`；`error_code=PARTIAL_DEVICE_FAILURE`；`message="18 of 20 device(s) failed"`；`device_results` 20 条；`verified_hdf5_points={SBPM01:20000, SBPM02:20000}`；`failed_source_files_zero_bytes` 18 条（SBPM03–SBPM20）；`completed_at_utc=2026-10-02T16:13:10.876625+00:00` | case-02 |
| `logs/capture-BI-20261002-221633-5c9321c5-35d8-4075-80b3-4b3111afebf4.json` | `frequency_hz=100.0`；`duration_seconds=1800`；`checks[1]={checked_at: 2026-10-02T22:20:27, status: cancelled, message: "capture cancelled during service shutdown"}`；`latest_status=cancelled` | case-03 |
| `logs/capture-BI-5Hz-20000-20261002-225334-3d53c87f-f81e-46a7-b2fc-c9c5e7ba909a.json` | `frequency_hz=5.0`；`response.accepted=true` ← **与 `89bb146` 白名单矛盾** | case-04 |
| `logs/operator-launcher.log`、`logs/operator-ui.jsonl`、`logs/waveform-dashboard.log` | 前端/仪表盘运行日志（本审计未作为案例证据） | — |
| `logs/spectrum-runs/`（40 个子目录）、`logs/spectrum-preview-validation/`、`logs/spectrum-ui-validation/` | 频谱任务产物（与对齐案例无关，未使用） | — |

> 注：`logs/` 下 3 个 `capture-BI-*.json` 是仅有的采集级原始记录。**2026-10-07 之前没有保存其他采集任务的完整 JSON**，这是 case-05 无法回溯的直接原因。

---

## 6. 交付目录（发布与验收记录）

根：`交付/`

### 6.1 `交付/20261026-timing-10hz-r1/` — case-08 主证据

| 目录内文件 | 内容 |
| --- | --- |
| `README.md` | 故障现象、完整链路、线上错误原文、根因、改动表、发布状态、验证明细、未验证清单、回滚命令 |
| `release-pair.json` | 版本对（operator + server）元数据 |
| `evidence/quality.log` | 尾部：`Ran 286 tests in 36.161s` / `OK` / `local quality gate: OK` |
| `evidence/live-timing-frequency.json` | `accepted:true`、`payload:{frequency_hz:10.0, source:"timing_pv"}` |
| `evidence/protocol-smoke.json` | `status:"passed"`、`run_count:1`、`segment_count:5`、`exact_file_count:125` |
| `evidence/deploy.json` | `MainPID:"1991109"`、`ActiveState:"active"`、`binary_sha256:35ba6d12…`、`BUILD-INFO.source_revision:5f17b67a…`、`status:"DEPLOYED; PROTOCOL VERIFIED; GUI SMOKE PENDING"` |
| `evidence/deploy.deploy.sh` | 部署事务（含未完成任务守卫、`--check`、回滚） |
| `evidence/server-build.log`、`evidence/operator-build.log` | 构建日志 |

### 6.2 `交付/20261026-pv-frequency-r2/` — 前端去掉频率下拉框

| 目录内文件 | 内容 |
| --- | --- |
| `README.md` | 改动、验证、版本与部署、验证边界、AOCI 收尾、回滚 |
| `BUILD-INFO-local.json`、`BUILD-INFO-desktop.json` | 本机与桌面构建身份 |
| `release-pair.json` | 版本对 |
| `evidence/targeted-tests.log` | 41 项定向回归 |
| `evidence/capture-submission-test.log` | 1 项采集提交补测（确认 GUI 不传频率覆盖值） |
| `evidence/connected-pv-page.png`、`remote-pv-page.png` | 打包/远程界面显示实际 PV `10 Hz` |
| `evidence/capture-page.png`、`packaged-capture-page.png` | 下拉框已移除 |
| `evidence/local-activation.json`、`remote-activation.json`、`remote-activation.log`、`activate-desktop.sh`、`deploy-desktop.sh`、`remote-deploy.log`、`remote-precheck.json` | 激活与部署记录 |
| `evidence/local-build.log`、`desktop-build.log`、`desktop-build-mirror.log`、`desktop-build-retry.log` | 构建日志 |
| `evidence/aoci-closure.json` | AOCI 维护记录 |
| `evidence/ui-preview.log`、`packaged-ui.log`、`upload.log` | 界面与上传记录 |

### 6.3 `交付/20261016-history-quality-r1/` — case-06 / case-07 主证据

| 目录内文件 | 内容 |
| --- | --- |
| `README.md` | 「2026-10-12 历史数据核验」表（422/621/455/375/288 与 19528～19570）、留一检查结论、「bunchID 数值不换算为秒」、截图数据来源声明、验证状态、AOCI 收尾、桌面 smoke |
| `evidence/full-quality.log` | 241 项完整质量门 |
| `evidence/gui-history.json`、`gui-history-verification.json`、`gui-history.png` | 真实桌面 smoke（PID 3120745，二进制 SHA-256 `c88b8213…`） |
| `evidence/ui-validation-summary.json` | 每张截图的数据来源逐项声明 |
| `evidence/preflight-anomaly-1280x800.png`、`preflight-anomaly-1600x1000.png` | 预检异常态（真实 bunchID + 示例 X/Y） |
| `evidence/aligned-anomaly-1280x800.png`、`aligned-anomaly-1600x1000.png` | 对齐后异常态 |
| `evidence/zero-intersection-1280x800.png`、`zero-intersection-1600x1000.png` | 空交集态（合成 ID） |
| `evidence/normal-1280x800.png`、`normal-1600x1000.png`、`single-device-1280x800.png`、`single-device-details-1280x800.png` | 正常态与单设备详情 |
| `evidence/operator-activation.json` | 本机激活记录（r6 → r1） |
| `evidence/aoci-maintain-blocked.json` | AOCI maintain `status=stopped / result=blocked` 快照 |
| `evidence/archive-verification.json` | 8,368 项清单、8,289 普通文件哈希、79 符号链接 |
| `evidence/desktop-smoke-raw.h5`、`desktop-smoke-export-v2.h5` | smoke 的原始与导出 HDF5 |
| `BUILD-INFO`、`SOURCE-MANIFEST.json`、`MANIFEST.sha256`、`version-pair.md` | 构建身份 |

### 6.4 `交付/20261008-history-release-r4/` — 段身份与「无部分成功段」声明

| 目录内文件 | 内容 |
| --- | --- |
| `README.md` | 版本对、二进制 SHA-256、2026-10-06 协议查询（3 任务/87 段/1740 文件）、真实桌面验收（`1000 Hz \| 10 分钟 \| 21 段`）、**「现场所选任务没有部分成功段」** |
| `operator/BUILD-INFO` | `source_revision:51afde8…`、`source_state:working-tree`、`binary_sha256:8e50fd5e…` |
| `operator/SOURCE-MANIFEST.json` | 源码清单：`src/waveform_storage/gui/operator_window.py → 077e0aa4add65f10c5e8388b9bf62b80ced5f8837aa4180f8757685a77d6bab6`（≠ `51afde8` 的 blob SHA-256，见 case-04 未决） |
| `server/BUILD-INFO`、`server/SOURCE-MANIFEST.json` | 服务端身份与清单 |
| `evidence/final-quality.log` | 206 项质量门 |
| `evidence/protocol-smoke.json`、`gui-history.json`、`gui-history.png`、`partial-integration.log` | 协议、GUI、部分成功段链路 |
| `operator-activation.json`、`infrastructure.json`、`server-deployment.json` | 部署与基础设施记录 |
| `SHA256SUMS`、`artifacts.json`、`release-pair.json` | 校验与元数据 |

### 6.5 `交付/20261017-*-local/`（5 个）— 仅文字/布局变更

`20261017-history-ui-layout-r2-local/`、`-controls-r3-local/`、`-display-r4-local/`、`-compact-r5-local/`、`-wording-r6-local/`。

关键文件：`evidence/wording-change.diff`（r6：「步进」→「相邻数据编号的间隔」，仅文字）、`evidence/display-change.diff`（r4）、`evidence/operator-activation.json`。

---

## 7. 真实数据与 fixture（case-07 主证据）

根：`outputs/history-ui-validation-20261016/`

| 路径 | 内容 |
| --- | --- |
| `real-data-20261012-all-segments.json` | 5 段汇总：`strict_common_bunch_id_count`、`leave_one_out_target`、`target.step_min/max/mode`、`sampling_rate_fields.frequency_hz=500.0` |
| `real-data-20261012-sequence-0.json` … `-sequence-4.json` | 逐段 25 台设备的完整报告（约 35 KB/段） |
| `real-data-20261012-loader-diagnostics.json` | loader 诊断 |
| `bunch-id-fixtures/22833275-5e77-41c5-b703-f306accde164_S00000.npz` … `S00004.npz` | 每段 25 台设备的原始 `uint64` bunchID 序列（各 20000 点）+ `common_bunch_ids` + `device_ids_json` + `fixture_sha256` |
| `offscreen-preview-final-r5/` | 最终 8 张状态截图（README 声明的证据目录） |
| `offscreen-preview-r0/`、`-r0-waveform-env/`、`-r1/`、`-final/`、`-final-r2..r4/` | 迭代过程截图 |

**fixture SHA-256（来自 `real-data-20261012-all-segments.json`）**：

| 段 | fixture_sha256 |
| ---: | --- |
| 0 | `57b5e63d2395b14de6ea500267d9827998c369461ce0457981271a94ccf88a21` |
| 1 | `54bcd3d8db2faad34cb47707fb0024708dc6312498827cfeb8123e19d7e7c297` |
| 2 | `ee8f0c300d6d83051e538305f44578cab5c4e732afbf62e0c3cbb521dec57db4` |
| 3 | （见同文件 segments[3].fixture_sha256） |
| 4 | （见同文件 segments[4].fixture_sha256） |

**独立复算命令**（本次审计执行，全部通过）：

```bash
cd [prab]/reports/phase1-m0-20261029/waveform-audit
/home/whloong/miniconda3/envs/waveform-storage/bin/python verify_fixtures.py
# RESULT: ALL CHECKS PASSED
# 保留率： S0=2.11%, S1=3.10%, S2=2.27%, S3=1.88%, S4=1.44%
# 分析器推算跨度： S0=0.842s, S1=1.240s, S2=0.908s, S3=0.748s, S4=0.574s
# 主流设备原始跨度（1 MHz 计时钟换算）： 全部 39.998s
```

> 说明：系统 `python3` 与仓库 `.venv` 都**没有 numpy**；必须用 `/home/whloong/miniconda3/envs/waveform-storage/bin/python`（numpy 2.2.6）。

---

## 8. 文档与交接记录

| 路径 | 引用内容 | 关联案例 |
| --- | --- | --- |
| `docs/history/2026-07/线上运行基线调查.md` | 调查日期 2026-07-25；只读 h5dump 真实文件、SHA-256 `49c0f6ab…`；`/SHINE_Data` 目录规则；`nohup.out` 两次请求（2 Hz/600 s）；「取得原始请求帧前仍不能确认换算位置」 | case-01/11 |
| `docs/问题清单与改进路线.md:95-180` | WF-005（HDF5 schema）、WF-006（bunchID 对齐边界）、WF-007（元数据错位）| case-01 |
| `docs/数据对齐v2设计.md:1-20,40,22-60` | 2025-11-12 12:07:21 批次 36 台严格交集为 0；两种步长空间；coverage 阈值待现场确认 | case-01 |
| `docs/CURRENT_STATUS.md:25-49` | 10 Hz 故障现象、根因、2100 s 由操作员确认、未验证清单 | case-08 |
| `docs/CURRENT_STATUS.md:121` | 「步进」→「相邻数据编号的间隔」；诊断与对齐规则保持原有行为 | case-06 |
| `docs/CURRENT_STATUS.md:169` | 2026-10-12 任务的 5 段数字、COLD BPM 步长 28–76、分析器推算跨度 0.574–1.240 s、「不把 bunchID 当作时钟」 | case-07 |
| `docs/CURRENT_STATUS.md:214-217` | 当前版本与部署状态表 | case-08 |
| `docs/handoffs/TASK_HANDOFF_2026-08-28_17-17-38_UTC+0800.md` | `[Constraint]`：`interval=10` 表示 10 分钟不是 10 Hz；`attempted_cycles=19` 不是采样点数 | case-11 |
| `docs/handoffs/TASK_HANDOFF_2026-08-28_16-31-43_UTC+0800.md` | 设备侧 `cfg_flag3/result_capture` 跨线程数据竞争 `[Inference]`；47 台全失败；五区抽样 0 字节 | case-02 |
| `docs/handoffs/TASK_HANDOFF_2026-08-27_14-17-05_UTC+0800.md` | `fpga_test()` 无条件 `return 0` 而 `task4()` 仍打印 `Data Save Done` | case-02 |
| `docs/采集协议v2候选.md:42-48` | 1000/500/100/50/10/5/2 Hz 等待值 2/4/12/22/2100/4200/512 s；10 Hz 于 2026-10-26 现场确认；禁止插值 | case-08 |
| `docs/agent-api-v2.md:187`（`cae6b64` diff） | 支持频率档位增加 10 Hz | case-08 |
| `docs/RELEASE_CHECKLIST.md` | 固定发布规范（发布纪律，用于评估证据可信度） | 全局 |
| `packaging/OPERATOR_FORMAL_PACKAGE.md`（`cae6b64` diff） | 「Bunch IDs are opaque identifiers and do not establish elapsed time or sampling frequency」；历史页改为按任务+段查询 | case-06/07 |
| `AGENTS.md`（HEAD） | 发布与验证纪律、AOCI 规则 | 全局 |
| `[prab]/PRAB_PLAN.md:14,37,73,104` | 「国庆前后的对齐逻辑差异」「含国庆后对齐问题根因」「国庆后波形对齐偏移」「国庆后 Waveform 对齐异常」 | case-10 |

---

## 9. 明确排除的「假证据」（测试构造 / 设计设想）

**引用时必须标注为构造物，不得当作真实事故。**

| 路径 | 构造内容 | 排除理由 |
| --- | --- | --- |
| `tests/test_alignment.py:34-42` | 步长 500,000 / 1,000,000 的合成设备序列 | 合成 `uint64` 序列，非真实数据 |
| `tests/test_spectrum_analysis.py:27` | `ids = np.arange(points, dtype=np.uint64) * int(1_000_000 / fs) + 100000007` | 按 1 MHz 计时钟假设合成 |
| `tests/test_partial_history_integration.py` | 「请求 2 台、实际 1 台、sequence 0/3 跳号」 | r4 明确写「现场所选任务没有部分成功段」 |
| `tests/test_formal_history_bpm_selection.py` | BPM 选择 / 段身份回归 | 测试代码 |
| `tests/test_gui_alignment_adapter.py`、`tests/test_history_smoke_preflight.py`、`tests/test_bunch_id_diagnostics.py` | GUI 适配、smoke 预检、诊断 | 测试代码 |
| `交付/20261016-history-quality-r1/evidence/preflight-anomaly-*.png`、`aligned-anomaly-*.png` | 真实 bunchID + **示例合成** X/Y | README 自述「不能称为多设备原始波形验收」 |
| `交付/20261016-history-quality-r1/evidence/zero-intersection-*.png` | 合成 ID + 示例 X/Y | 同上 |
| `docs/数据对齐v2设计.md` 第 6 节 | 覆盖率阈值、HDF5 v2 物理单位、GUI 点击流验证 | 文档自述「尚未做 GUI 点击流或现场验证」 |
| `docs/采集协议v1候选.md` | 旧协议设计 | 仅设计，未现场部署 |
| `交付/*/release-pair.json` 中的 `source_state: working-tree` | 「版本对」不等于「git 提交」 | 见 case-04 未决 |

---

## 10. 一键复现本索引的全部关键检查

```bash
W=/home/whloong/waveform-storage/waveform-storage-system
PY=/home/whloong/miniconda3/envs/waveform-storage/bin/python

# 1) 基线
git -C "$W" rev-parse HEAD && git -C "$W" log -1 --date=iso --format='%ad %s'

# 2) 零提交区间（case-10）
git -C "$W" log --all --since='2026-08-26 15:32:11 +0800' --until='2026-10-07 16:30:43 +0800' --oneline   # 空

# 3) 对齐算法未变（case-10）
git -C "$W" log --all --format='%h|%ad|%s' --date=iso -- src/waveform_storage/processing/alignment.py
git -C "$W" show 25e6b73 -- src/waveform_storage/processing/alignment.py

# 4) 频率校验引入（case-05）与 10 Hz 修复（case-08）
git -C "$W" log --all --format='%h|%ad|%s' --date=iso -S'FREQUENCY_MISMATCH'
git -C "$W" log --all --format='%h|%ad|%s' --date=iso -S'4200' -- src/waveform_storage/acquisition/runtime.py

# 5) bunchID 当秒数（case-06）
git -C "$W" show 61b47db:src/waveform_storage/gui/operator_window.py | sed -n '1243,1248p'

# 6) 国庆前白名单（case-04）
git -C "$W" show 89bb146:src/waveform_storage/acquisition/runtime.py | sed -n '477,482p'

# 7) 真实数据复算（case-07）
cd [prab]/reports/phase1-m0-20261029/waveform-audit && "$PY" verify_fixtures.py
```

---

## 11. 证据可信度分级（供引用时套用）

| 级别 | 定义 | 本索引中的例子 |
| --- | --- | --- |
| **A0 外部一手** | 仓库之外的一手数据源，只读查询、参数可复述 | **第 12 节** EPICS Archiver（`source_id=TIM_ARCHIVER_URL`，5 次查询逐点复算一致）—— 支撑 case-09 / case-12 |
| **A1 一手可复算** | 原始数据 + 本次审计独立复算通过 | case-07 的 5 个 `.npz` fixture → `verify_fixtures.py` 全部一致 |
| **A2 一手不可复算** | 原始记录存在但依赖已销毁的现场对象 | case-02/03 的采集日志（`/SHINE_Data` 现场文件已不在本地）；case-01 的 h5dump（原始 HDF5 已清理） |
| **A3 发布证据** | 交付目录内的构建/部署/验收记录，含二进制 SHA-256 与 PID | case-08 的 `deploy.json` + `quality.log` + `live-timing-frequency.json` |
| **B1 代码事实** | HEAD 或指定 commit 的 `文件:行`，可 `git show` 复核 | case-06 的 `1_000_000` 除式；case-05 的 `FREQUENCY_MISMATCH` |
| **B2 文档记录** | 仓库内的设计/状态/交接文档，反映记录当时的事实 | `docs/CURRENT_STATUS.md:169`；`docs/handoffs/…2026-08-28…` |
| **C1 计划措辞** | `PRAB_PLAN.md` 等规划文件中的说法，**本身不是证据** | case-10 |
| **C2 测试构造** | 测试代码或合成 fixture | 第 9 节全部 |

---

## 12. EPICS Archiver 证据（2026-10-29 补入，支撑 case-09 / case-12）

**用途**：判定「timing PV 是否在国庆后一次性从 5 Hz 切到 10 Hz」。结论是**否** —— PV 是可变的运行态读数，10 Hz 至少自 2026-08-17 起反复出现。

### 12.1 数据源身份

| 项 | 值 | 取值方式 |
| --- | --- | --- |
| PV | `AC-LA-INJ1-TIM:WRN1:MCFQ8` | MCP `archiver_resolve_pvs` |
| `source_id` | `TIM_ARCHIVER_URL` | 同上 |
| `archiver_url` | `http://10.101.9.19:17668` | 同上 |
| `source_kind` | `new` | 同上 |
| 时区 | 全部 UTC（工具声明 `timezone: "UTC"`） | `archiver_capabilities` |
| 只读性 | `read_only: true` | `archiver_capabilities` |
| 与软件 PV 的一致性 | 与 `src/waveform_storage/acquisition/runtime.py:503` 的 `TIMING_FREQUENCY_PV` 字面一致；另见 `src/waveform_storage/legacy/gui_capture_adapter.py:12` | 人工核对 |

> 工具链为该 MCP server 的 v1 API：`archiver_capabilities` / `archiver_resolve_pvs` / `archiver_query_series` / `archiver_query_live`。

### 12.2 五次精确查询（全部 `strategy=lastSample`）

| # | start（UTC） | end（UTC） | max_points | strategy | 返回 `point_count` | `in_range` / `context` | `bin_seconds` | `downsampled` | `data_state` |
| --- | --- | --- | ---: | --- | ---: | --- | ---: | --- | --- |
| 1 | `2026-08-15T00:00:00Z` | `2026-10-01T00:00:00Z` | 2000 | lastSample | 42 | 41 / 1 | 2031 | true | `available` |
| 2 | `2026-08-17T00:00:00Z` | `2026-08-17T08:00:00Z` | 500 | lastSample | 7 | 6 / 1 | 58 | true | `available` |
| 3 | `2026-10-01T00:00:00Z` | `2026-10-02T00:00:00Z` | 500 | lastSample | 2 | 1 / 1 | 173 | true | `available` |
| 4 | `2026-10-23T00:00:00Z` | `2026-10-28T00:00:00Z` | 2000 | lastSample | 16 | 15 / 1 | 216 | true | `available` |
| 5 | `2026-10-26T00:00:00Z` | `2026-10-27T00:00:00Z` | 500 | lastSample | 1 | **0** / 1 | 173 | true | `context_only` |
| 6 | live `2h`（2026-10-29T03:36:55Z → 05:36:55Z） | — | 200 | lastSample | 1 | 0 / 1 | 36 | true | `context_only` |

所有查询 `complete: true`、`truncated: false`、`data_state` 为 `available` 或 `context_only`，**没有** `error`。第 5/6 次带 warning：`No points fall inside the requested range; returned points are context from outside the range`。

### 12.3 关键点列（UTC，逐点在本次审计中独立复算一致）

**窗口 1（42 点，节选）—— 10 Hz 在国庆前即有记录**

```text
2026-08-14T11:11:28.704108Z = 2      2026-08-15T03:44:24.753965Z = 2
2026-08-17T06:14:50.469014Z = 10  ← 国庆前 45 天
2026-08-17T07:13:20.706811Z = 2      2026-08-17T07:32:12.955437Z = 2
2026-08-25T17:18:53.338870Z = 2
2026-08-27T02:31:36.103140Z = 10     2026-08-27T06:03:14.830203Z = 10
2026-08-28T08:11:06.830204Z = 10     2026-08-28T08:46:30.865926Z = 2
2026-08-30T07:53:58.973274Z = 5      2026-08-31T03:07:15.732775Z = 5
2026-08-31T14:16:54.729096Z = 5
2026-09-04T01:54:55.619560Z = 10     2026-09-04T09:02:34.533956Z = 1000
2026-09-04T09:31:10.691215Z = 10     2026-09-04T09:50:35.416318Z = 100
2026-09-04T10:57:11.809901Z = 5      （其后 09-06…09-22 多为 5 / 2）
2026-09-18T11:27:46.284732Z = 100
2026-09-29T20:53:13.709428Z = 5
```

**窗口 2（7 点，全列）—— 78 分钟内 10/2 交替**

```text
2026-08-15T03:44:24.753965Z = 2   (context)
2026-08-17T06:14:50.469014Z = 10
2026-08-17T07:04:04.288342Z = 2
2026-08-17T07:04:48.727715Z = 10
2026-08-17T07:13:20.706811Z = 2
2026-08-17T07:18:08.493513Z = 10
2026-08-17T07:32:12.955437Z = 2
```

**窗口 3（2 点，全列）—— 国庆假期首日读数**

```text
2026-09-29T20:53:13.709428Z = 5   (context)
2026-10-01T09:59:55.853957Z = 10  (= 2026-10-01 17:59:55 +0800)
```

**窗口 4（16 点，全列）—— 10-23 与 10-27 的密集跳变**

```text
2026-10-22T09:01:25.490845Z = 100   (context)
2026-10-23T01:39:56.098584Z = 1000
2026-10-23T12:02:27.767979Z = 10    2026-10-23T12:17:30.650561Z = 100
2026-10-23T12:25:31.951082Z = 10    2026-10-23T12:38:51.326852Z = 1000
2026-10-23T12:46:20.066366Z = 10    2026-10-23T12:48:19.895814Z = 1000
2026-10-23T13:21:30.271680Z = 10    2026-10-23T13:36:41.419348Z = 10
2026-10-27T02:45:28.069522Z = 10    2026-10-27T13:02:41.497781Z = 20
2026-10-27T13:05:00.699117Z = 5     2026-10-27T13:09:30.980527Z = 10
2026-10-27T13:25:36.805871Z = 5     2026-10-27T14:21:47.047689Z = 50
```

**窗口 5（1 点，context）—— 修复当天（2026-10-26）归档值未变**

```text
2026-10-23T13:36:41.419348Z = 10   （2026-10-26T00:00–10-27T00:00Z 内零变化点）
```

**窗口 6（live 2h，context）—— 当前读数**

```text
2026-10-28T09:28:03.551637Z = 50   (= 2026-10-28 17:28:03 +0800)
```

### 12.4 由这份证据可以 / 不可以声称什么

| 可以声称（已证实） | 不可以声称（越界） |
| --- | --- |
| 10 Hz 在 2026-08-17、08-27、08-28、09-04、10-01、10-23、10-27 有归档记录 | 「PV 在原始逐次变化中只有这些时刻是 10 Hz」—— 返回体全部 `downsampled=true` |
| PV 在 2 / 5 / 10 / 20 / 50 / 100 / 1000 Hz 之间跳变 | 「机器的实际束流频率就是这些值」—— PV 值的物理含义未确认 |
| 2026-10-26 当天归档值保持 10 Hz（零变化点 + 前一记录为 10） | 「2026-10-26 全天 PV 逐秒读数为 10」—— 只能说明归档状态未变 |
| 不存在「国庆后一次性 5→10 切换」 | 「所有窗口内都没有采集被拒」—— 采集拒绝记录不在 Archiver 里 |
| 当前（2026-10-28T09:28Z）读数为 50 Hz | 「10 Hz 问题已永久消失」—— PV 仍在跳变 |

### 12.5 复核命令（只读）

```text
archiver_resolve_pvs(pvs=["AC-LA-INJ1-TIM:WRN1:MCFQ8"])
archiver_query_series(pvs=["AC-LA-INJ1-TIM:WRN1:MCFQ8"],
                      start="2026-08-15T00:00:00Z", end="2026-10-01T00:00:00Z",
                      max_points=2000, strategy="lastSample")
archiver_query_series(..., start="2026-08-17T00:00:00Z", end="2026-08-17T08:00:00Z", max_points=500)
archiver_query_series(..., start="2026-10-01T00:00:00Z", end="2026-10-02T00:00:00Z", max_points=500)
archiver_query_series(..., start="2026-10-23T00:00:00Z", end="2026-10-28T00:00:00Z", max_points=2000)
archiver_query_series(..., start="2026-10-26T00:00:00Z", end="2026-10-27T00:00:00Z", max_points=500)
archiver_query_live(pvs=["AC-LA-INJ1-TIM:WRN1:MCFQ8"], window="2h", max_points=200)
```

> **与 Waveform 仓库的关系**：该 Archiver 数据不在 Waveform 仓库内，属外部只读数据源。引用时须同时给出 `source_id` 与查询窗口，**不能**写成「Waveform 仓库记录」。

### 12.6 这条证据改变了哪些结论

| 位置 | 变化 |
| --- | --- |
| case-09 | `推断` → **`已证实`**；标题由「PV 何时变为 10 Hz」改为「PV 是可变的运行频率读数，不存在一次性切换」 |
| case-12 | **新增**（`已证实`）：10 Hz 白名单缺口的可触发窗口自 2026-08-17 起即存在 |
| case-08 | 未决项中「起始时间无记录」被替换为 archiver 界定结果；`root_cause_evidence` 增补 2026-10-26 当天窗口 |
| `docs/waveform/fault-history-and-version-changes.md` | §1 时间线读法、case-08 / case-09 段、§5 缺口、§6.2/6.4 措辞同步 |
| 未受影响 | case-01…case-07、case-10、case-11 —— **不因这份证据升级或降级** |
