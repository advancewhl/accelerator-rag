# EPICS Archiver 原始证据：timing PV `AC-LA-INJ1-TIM:WRN1:MCFQ8`（2026-10-29）

本文件记录 Lead 用只读 EPICS Archiver MCP 工具取得的原始读数，用于回答 Waveform 审计中的
两个待核实问题：`reports/phase1-m0-20261029/waveform-audit/cases.json` 的 `case-09`
（“定时 PV 何时变为 10 Hz”）以及 `case-08`（10 Hz 采集被拒）的时序前提。

**证据性质**：归档读数是系统外部证据（EPICS Archiver），不是代码推导；它只能说明
“归档记录了什么”，不能说明“操作员为什么那样设置”。

## 1. PV 身份核对（已证实）

| 项 | 值 | 证据 |
| --- | --- | --- |
| PV 名 | `AC-LA-INJ1-TIM:WRN1:MCFQ8` | 见下 |
| Waveform 代码引用 | `src/waveform_storage/acquisition/runtime.py:503`：`TIMING_FREQUENCY_PV = "AC-LA-INJ1-TIM:WRN1:MCFQ8"`；`src/waveform_storage/legacy/gui_capture_adapter.py:12` | `grep -rn MCFQ8`（Waveform 仓库 HEAD `dc50e08`） |
| 归档来源 | `source_id=TIM_ARCHIVER_URL`，`http://10.101.9.19:17668`（kind=new） | `archiver_resolve_pvs` |
| 工具 | MCP `shine_archiver`：`archiver_health`（read_only=true，config_sha256 `1b7c8e54…`）、`archiver_query_series`（strategy=`lastSample`，max_points ≤ 2000） | 本次调用返回 |
| 时区 | 工具返回 UTC；本文同时给出 +0800 换算 | 工具说明 |

因此“代码读的频率 PV”与“本文件查询的 PV”是同一个对象（已证实）。

## 2. 查询与原始点列

### Q1 — 2026-08-17T00:00:00Z … 2026-08-17T08:00:00Z（`max_points=2000`，`lastSample`）

| # | 时间（UTC） | 值（Hz） |
| --- | --- | --- |
| 0 | 2026-08-15T03:44:24.753965Z（窗口外 context） | 2 |
| 1 | 2026-08-17T06:14:50.469014Z | **10** |
| 2 | 2026-08-17T07:04:04.288342Z | 2 |
| 3 | 2026-08-17T07:04:48.727715Z | **10** |
| 4 | 2026-08-17T07:13:20.706811Z | 2 |
| 5 | 2026-08-17T07:18:08.493513Z | **10** |
| 6 | 2026-08-17T07:32:12.955437Z | 2 |

`point_count=7`，`bin_seconds=15`，`downsampled=true`，`complete=true`，`data_state=available`。

### Q2 — 2026-08-15T00:00:00Z … 2026-10-01T00:00:00Z（42 点，节选）

| 时间（UTC） | 值 |
| --- | --- |
| 2026-08-17T06:14:50Z | 10 |
| 2026-08-27T02:31:36Z / 06:03:14Z、2026-08-28T08:11:06Z | 10 |
| 2026-09-04T01:54:55Z、2026-09-04T09:31:10Z | 10 |
| 其余点 | 2 / 5 / 100 / 1000 交替 |

`point_count=42`，`bin_seconds=2031`，`downsampled=true`，`complete=true`。

### Q3 — 2026-10-01T00:00:00Z … 2026-10-02T00:00:00Z

| 时间（UTC） | 值 |
| --- | --- |
| 2026-09-29T20:53:13.709428Z（context） | 5 |
| **2026-10-01T09:59:55.853957Z**（= 2026-10-01 17:59:55 +0800） | **10** |

`point_count=2`，`bin_seconds=44`，`downsampled=true`。

### Q4 — 2026-10-23T00:00:00Z … 2026-10-28T00:00:00Z（16 点，节选）

| 时间（UTC） | 值 |
| --- | --- |
| 2026-10-23T01:39:56Z | 1000 |
| 2026-10-23T12:02:27Z、12:25:31Z、12:46:20Z、13:21:30Z、13:36:41Z | **10**（= 20:02–21:36 +0800） |
| 2026-10-27T02:45:28Z | 10 |
| 2026-10-27T13:02:41Z / 13:05:00Z / 13:09:30Z / 13:25:36Z / 14:21:47Z | 20 / 5 / 10 / 5 / 50 |

`point_count=16`，`bin_seconds=216`，`downsampled=true`。

### Q5 — 实时窗口 `2h`（2026-10-29T03:32:49Z–05:32:49Z）

- `in_range_point_count=0`，`data_state=context_only`，唯一 context 点：
  `2026-10-28T09:28:03.551637Z` = **50 Hz**（= 2026-10-28 17:28 +0800）。
- 含义：自 2026-10-28 17:28 +0800 起至查询时刻**没有新的归档变化**；当前值无法由该窗口证明，只能说“最后一次记录的读数是 50 Hz”。该 series 不是高频采样，不能当作实时状态。

## 3. 可以下的结论（分级）

**已证实（证据来自归档记录本身）**：

1. 该 PV 的读数是**多值可变**的：本次查询范围内出现 2、5、10、20、50、100、200、500、1000 Hz。
2. **10 Hz 至少自 2026-08-17 起就已反复出现**，且在同一天 78 分钟内出现 `10→2→10→2→10→2` 的来回跳变（Q1）。
3. 2026-10-01（国庆当天）17:59:55 +0800 记录到 10 Hz（Q3）——但这只是该日的一次记录，不是“切换”。
4. 2026-10-23 20:02–21:36 +0800 连续记录到 10 Hz（Q4），与 `docs/CURRENT_STATUS.md:28` 所述“PV 返回 10 Hz 但白名单拒绝”相符。

**推断（需要一步未记录的推理）**：

5. 该 PV 反映的是**随运行模式/值班设置变化的机器重复频率**，而非一次性配置；因此任何“固定白名单 + 假定频率稳定”的代码都会间歇性失败。此推断依赖“读数变化 = 操作员/模式变化”这一未记录环节。

**被否证的说法**：

6. ❌ “timing PV 在国庆前后从 5 Hz 一次性变为 10 Hz”——不成立：8 月已有 10 Hz 记录，且该 PV 是持续抖动的多值量。
7. ❌ “10 Hz 白名单缺口是国庆后才出现的新状态导致的”——不成立：10 Hz 在 8 月即存在；`cae6b64`（2026-10-26）是补支持，不是对某个新状态的应急修复。

**不能下的结论（证据不足）**：

8. 不能确定 10 Hz 的**首次**出现时间：查询窗口只回溯到 2026-08-15；更早历史未查。
9. 不能确定读数变化的**原因**（操作员操作、模式切换、EPICS 侧写入、还是 PV 本身抖动），仓库内无值班记录。
10. 不能把该 PV 的时间戳当作“采集请求被拒的时刻”——请求日志与 PV 序列没有逐秒对齐，且归档 `downsampled=true`。

## 4. 复现方式（逐字）

在具备 `shine_archiver` MCP 的会话中调用：

```text
archiver_resolve_pvs(pvs=["AC-LA-INJ1-TIM:WRN1:MCFQ8"])
archiver_query_series(pvs=["AC-LA-INJ1-TIM:WRN1:MCFQ8"],
                      start="2026-08-17T00:00:00Z", end="2026-08-17T08:00:00Z",
                      max_points=2000, strategy="lastSample")
archiver_query_series(..., start="2026-08-15T00:00:00Z", end="2026-10-01T00:00:00Z", ...)
archiver_query_series(..., start="2026-10-01T00:00:00Z", end="2026-10-02T00:00:00Z", ...)
archiver_query_series(..., start="2026-10-23T00:00:00Z", end="2026-10-28T00:00:00Z", ...)
archiver_query_live(pvs=["AC-LA-INJ1-TIM:WRN1:MCFQ8"], window="2h")
```

**限制**：`max_points` 上限 2000（工具报错 `POINT_LIMIT_EXCEEDED` 时按同样窗口/参数减小跨度重查）；
所有返回均 `downsampled=true`，`bin_seconds` 在 15–2031 s 之间，因此**时间戳是归档记录时刻，
不保证是数值变化的精确时刻**，也不能据此做秒级因果推断。
