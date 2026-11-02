---
applicable_system_version: "waveform-storage-system@dc50e08 (2026-10-26)"
alignment_algo_hash: "不适用（本文不对齐算法负责；系统对齐标识 sha256(processing/alignment.py)=e8db12d7… 见对齐手册与故障历史文档）"
verified_date: "2026-10-29"
owner: "未指派（待项目负责人裁决）"
---

# Waveform 存储与数据流技术说明

本文描述 SHINE 波形存储（`waveform-storage-system`）从采集请求到前端/API 消费的完整数据流、
标识符语义、落盘命名规则与存储边界。所有断言以源码为准，不把设计文档当作已实现事实。

**证据基础**：只读仓库 `/home/whloong/waveform-storage/waveform-storage-system`，
HEAD `dc50e08a2beddff42c297a237b3f3312f5c24ac9`（提交时间 2026-10-26 21:06:55 +0800，
提交说明 `docs: synchronize AOCI after PV frontend release`）。
`git describe --always --tags` 输出 `archive/pre-spectrum-analysis-ui-20261008-13-gdc50e08`
（即该归档标签之后第 13 个提交）。核验日 2026-10-29。

---

## 0. 一句话结论

系统采用**三层分离**：HDF5 文件保存波形数组（唯一的科学数据事实源）；MongoDB 保存可查询的
任务/文件目录（`waveform_files` 只存路径与紧凑格式描述，不存数组）；ZMQ 协议 v2 负责调度与
目录查询。原始数据边界是硬约束：**一次采集请求 → 多个真实 `capture_sequence` → 每段多个
BPM 文件，段之间不默认拼接**。

---

## 1. 字段来源说明（front-matter）

| 字段 | 取值 | 依据 |
| --- | --- | --- |
| `applicable_system_version` | `waveform-storage-system@dc50e08 (2026-10-26)` | `git log -1`：`dc50e08a2beddff42c297a237b3f3312f5c24ac9`，2026-10-26 21:06:55 +0800 |
| `alignment_algo_hash` | 未定义（系统未实现） | 见下 |
| `verified_date` | 2026-10-29 | 本次核验日 |
| `owner` | 未指派（待项目负责人裁决） | 本文档为 Phase 1 交付物，项目内无指派记录 |

**`alignment_algo_hash` 为何是“未定义”**：在仓库内检索
`applicable_system_version`、`alignment_algo_hash` 两个字段名，先做全仓库 `grep -rn`（含
`docs/`、`src/`、`apps/`、`packaging/`、`config/`、`交付/`、`.aoci/`），再做限定后缀的
`grep -rln`，两次均无匹配（后者 rc=1）。该字段属于 Phase 1 为知识库追溯新引入的元数据，
系统并未实现它，也不存在“对齐算法整体”的版本号或哈希字段。

系统内**只存在一个更窄的等价机制**（不能与本字段混用）：`WaveformAgentV2` 在构造时对
`processing/alignment.py` 单个文件做 `sha256` 得到 `alignment_source_hash`
（`src/waveform_storage/application/agent_v2_service.py:WaveformAgentV2.__init__`，第 54 行），
并在对齐任务的 provenance 中同时输出为 `algorithm_source_sha256`，且以
`algorithm_version = "bunch-id-alignment:" + hash[:16]` 暴露
（`src/waveform_storage/application/agent_v2_service.py` 第 618–619 行）。
它覆盖的是**单模块**，且只在 Agent HTTP API v2 的对齐产物里出现，不是系统级字段。
代码作者明确区分了“单模块摘要”与“稳定的源码文件集合”：频谱任务在合并 provenance 时
`provenance.pop('algorithm_source_sha256')`，注释写明
“The analysis manifest defines a spectrum version, not a stable source-file set.
Never label the alignment hash as the spectrum implementation's source identity.”
（`agent_v2_service.py` 第 651–655 行）。这说明系统**没有**“对齐相关源文件集合”的哈希惯例。
本文档不做对齐语义断言，因此该字段留空指向对齐手册。

> 对齐算法本身的可核验标识定义见
> [对齐语义、参数与诊断手册](alignment-semantics-and-diagnostics.md) 第 1 节“字段来源说明”：
> front-matter 的 `alignment_algo_hash` 取**系统既有**单文件摘要
> `sha256(processing/alignment.py) = e8db12d7…`，与 API v2 provenance 的
> `algorithm_source_sha256` 一致；同节另给一个 4 文件集合哈希 `390fd8e9…`，属文档侧补充
> （`alignment_doc_bundle_hash`），系统未定义该口径。

---

## 2. 端到端数据流

### 2.1 数据流表

| 阶段 | 主要实体/符号 | 产物 | 代码位置 |
| --- | --- | --- | --- |
| ① 请求与校验 | `CaptureRequest`（`version`/`request_id`/`frequency_hz`/`duration_seconds`/`area_ids`/`devices`） | 校验通过的请求对象 | `src/waveform_storage/acquisition/protocol.py:CaptureRequest.__post_init__`（第 107–158 行） |
| ② 注册表策略 | `RegistryPolicy.validate`：时长上限、设备数上限、`area_ids`→`devices` 快照一致性 | 拒绝或放行 | `src/waveform_storage/acquisition/server.py:RegistryPolicy.validate`（第 264 行起）；`protocol.validate_area_device_snapshot`（第 486–515 行） |
| ③ 频率一致性闸门 | `read_timing_frequency` 读 timing PV，与 `frequency_hz` 比对 | `FREQUENCY_MISMATCH` / `TIMING_FREQUENCY_FAILED` | `src/waveform_storage/acquisition/server.py:WaveformAcquisitionServer.handle_message`（第 561–588 行） |
| ④ 任务受理 | `PersistentTaskExecutor` + `JsonTaskStore`；同一实例同时只跑一个采集任务 | `accepted → running` 状态与 `request_id` 幂等记录 | `docs/采集协议v2候选.md` §“v2 变化”；`docs/agent-api-v2.md` §“状态与边界” |
| ⑤ 周期循环 | `ProductionCaptureRunner.__call__`：EPICS 触发 → 等待 → SSH 下载 → TXT 解析 → HDF5 落盘；`sequence` 从 0 递增 | 每周期每设备一个 `RAW-*.h5` | `src/waveform_storage/acquisition/runtime.py:ProductionCaptureRunner.__call__`（第 271–405 行） |
| ⑥ 单周期采集 | `CaptureService.capture`：`EpicsGateway.trigger` → `waiter(duration)` → `DeviceSshGateway.download_many` → `parse_waveform_txt` → `write_single_device_hdf5` | 单设备 `DeviceCaptureResult` | `src/waveform_storage/application/capture_service.py:CaptureService.capture`（第 82–188 行） |
| ⑦ 落盘 | `write_single_device_hdf5`：同目录 `.part` 临时文件 + `os.replace` 原子替换 | `.h5` 正式文件 | `src/waveform_storage/io/hdf5_io.py:write_single_device_hdf5`（第 43–85 行）；`_atomic_hdf5_write`（第 373–385 行） |
| ⑧ 元数据登记 | `CaptureMetadataService.record_status` → `_record_files` 读 HDF5 属性 → upsert `waveform_files` | MongoDB 文档 `_id = {request_id}:{device_id}[:S{seq:05d}]` | `src/waveform_storage/metadata/service.py:CaptureMetadataService.record_status`（第 134–170 行）与 `_record_files`（第 202–280 行） |
| ⑨ 历史查询 | `list_capture_runs` / `list_capture_segments` / `find_waveform_files_by_segment`（新）与 `list_capture_times` / `find_waveform_files`（Legacy） | 段列表 + 精确文件路径 | `src/waveform_storage/metadata/mongo_repository.py`（第 177–264 行）；调度 `src/waveform_storage/acquisition/server.py:_handle_metadata_query`（第 648–735 行） |
| ⑩ 取数与消费 | SSH 精确路径下载 → `read_single_device_hdf5` → `align_devices` → 绘图/导出/频谱 | `AlignmentResult`、`*_BPMdata_v2.h5`、频谱产物 | `src/waveform_storage/transport/ssh_storage.py:download_device_series`（第 249–300 行）；`src/waveform_storage/application/retrieval_service.py:RetrievalService` |

### 2.2 时间与采样关系

设请求频率为 $f_s$（Hz，即机器束团重复频率），周期等待常量为 $I(f_s)$（秒，见第 7 节表），
请求总窗口为 $D$（`duration_seconds`，秒），参与采集的设备集合为 $\mathcal{D}$。

采样间隔（名义）：

$$
\Delta t = \frac{1}{f_s}
$$

第 $s$ 个数据段的文件数为成功设备数，因此

$$
1 \le F_s \le |\mathcal{D}|
$$

段数 $S$ 的上界由“每周期开始时刻不早于上一次开始时刻加 $I(f_s)$”推出（第 ⑤ 阶段循环的
`cycle_not_before` 逻辑，`runtime.py` 第 368–374 行）：

$$
S \le \left\lceil \frac{D}{I(f_s)} \right\rceil
$$

该式是**上界而非等式**：每周期还要串行完成触发、等待与下载，实际耗时可能超过 $I(f_s)$，从而
减少段数；逐周期成功与否也各不相同。因此一次请求的落盘文件总数满足

$$
F_{\text{total}} = \sum_{s=0}^{S-1} F_s \le S \cdot |\mathcal{D}|
$$

且 $F_{\text{total}}$ 一般**不等于** $S\cdot|\mathcal{D}|$——这正是“段不默认拼接”的物理依据，
不是实现缺陷。

真实样本佐证（本地只读核验，2026-10-29）：`data/samples/20251112/` 下 10 个
`RAW-110023-*-S00000.h5` 每文件 `BunchIDData` 形状 `(1, 1024)`、`Data` 形状 `(2, 1024)`、
`uint64`/`int64`，相邻 bunchID 差值恒为 500000；10 台设备严格交集为 1023 个公共 ID
（并集 1025）。该数字与 `docs/MongoDB元数据模块设计.md` §5 记录的“10 个文件、严格对齐得到
1023 个公共 bunch ID”一致。

---

## 3. 标识符语义与唯一性约束

### 3.1 标识符表

| 标识符 | 语义 | 类型/格式 | 唯一性约束 | 代码位置 |
| --- | --- | --- | --- | --- |
| `request_id` | 一次采集任务的业务身份，也是幂等键 | 规范小写 UUID 字符串；`str(UUID(x)) == x.lower()` | 主键：`capture_tasks._id = request_id` | 校验 `protocol.py:_validate_request_id`（第 529–541 行）；落库 `metadata/models.py:CaptureTaskMetadata.to_document` 第 143 行；`mongo_repository.py:upsert_task` 第 117–122 行 |
| `capture_sequence` | 同一请求内的真实数据段序号，从 0 起递增 | 非负整数；文件名中固定 5 位 `S00000` 形式 | 与 `request_id`+`device_id` 组成唯一键 | 递增 `runtime.py` 第 295、367 行；校验 `protocol.py` 第 253–256 行；唯一索引 `mongo_repository.py:ensure_indexes` 第 87–91 行 |
| `device_id` | 单一 BPM 设备标识 | 正则 `^[A-Z0-9_]+$` | 同一请求内不重复；注册表内唯一 | `protocol.py:DEVICE_ID_PATTERN`（第 26 行）、`protocol.py:CaptureRequest.__post_init__`（第 137–158 行）；注册表校验 `config/registry.py` 第 278–292 行 |
| `area_ids` | 操作员选择的束线区域，服务端用自带注册表重新展开 | 同 `DEVICE_ID_PATTERN` | 不重复，且每个区域至少要有一台被选设备 | `protocol.py` 第 133–148 行；`validate_area_device_snapshot` 第 486–515 行 |
| `bunchID` | 束团在设备内部编号，**无量纲整数**，不是时间 | `uint64`，非负、非布尔 | 单设备内唯一且严格递增（重采样/取时间轴时强制） | 写入 `hdf5_io.py` 第 76–80 行；读取校验 `hdf5_io.py:read_single_device_hdf5` 第 109–128 行；时间轴前置条件 `analysis/loaders.py:_id_times` 第 153–166 行 |
| `storage_id` | 存储域标识，默认 `shine_data_primary` | 非空字符串 | 与 `file.path` 组成唯一键 | 默认值 `metadata/service.py:CaptureMetadataService.__init__` 第 46 行；唯一索引 `mongo_repository.py` 第 100–104 行 |
| `time_sec` | 段开始时刻的本地 `HHMMSS`，来自文件名 | 恰好 6 位数字 | 不唯一（同一天同一秒可对应多个请求） | 解析 `metadata/service.py:_TIME_FIELD`（第 29 行）、`_record_files` 第 234–241 行；模型校验 `metadata/models.py` 第 218–219 行 |
| `storage_date_local` | 段开始时刻的本地日期 | `YYYY-MM-DD` | 不唯一 | `service.py` 第 242–245 行；协议校验 `protocol.py` 第 194–205 行 |

### 3.2 文件记录主键

`WaveformFileMetadata.record_id` 的定义（`src/waveform_storage/metadata/models.py`
第 233–237 行）：

```python
@property
def record_id(self) -> str:
    if self.capture_sequence == 0:
        return f"{self.request_id}:{self.device_id}"
    return f"{self.request_id}:{self.device_id}:S{self.capture_sequence:05d}"
```

即第 0 段沿用旧版 `{request_id}:{device_id}` 形式，后续段追加 `:S{seq:05d}`。服务启动时
`ensure_indexes` 会先把缺 `capture_sequence` 的旧文档原地补为 0，再把旧的
`(request_id, device_id)` 唯一索引替换为 `(request_id, device_id, capture_sequence)`
（`mongo_repository.py` 第 77–91 行），因此首段在升级前后可幂等覆盖。

### 3.3 时间戳字段

| 字段 | 语义 | 产生位置 | 关键性质 |
| --- | --- | --- | --- |
| HDF5 `capture_metadata_json.captured_at` | 该段**周期开始**的带时区时刻 | `runtime.py` 第 299 行 `datetime.now().astimezone()`，第 339 行写入 | 同一段内所有设备共享同一值（闭包内同一 `cycle_started`） |
| Mongo `waveform_files.captured_at` | 同上，从 HDF5 元数据回读 | `service.py:_file_captured_at`（第 282–301 行） | 元数据缺失/无时区时**回退**为任务受理时刻，而非猜测 |
| Mongo `waveform_files.created_at` | 元数据文档写入时刻 | `metadata/models.py` 第 197 行 `utc_now()` | 与 `captured_at` 不同，不可混用 |
| Mongo `capture_tasks.created_at/started_at/completed_at` | 任务生命周期 | `service.py:record_created` 第 106 行、`mongo_repository.py:update_task_status` 第 139–142 行 | 全部要求带时区（`metadata/models.py:_aware`，第 37–40 行） |
| `time_sec` / `storage_date_local` | 段开始时刻的本地时刻/日期 | `service.py` 第 234–245 行 | 时区取自 `timezone_name`，默认 `Asia/Shanghai`（第 55–56 行） |

**重要边界**：系统内**没有逐采样点时间戳**。每个文件只有一个段级 `captured_at`；bunchID 到
相对时间的换算属于分析层（见第 6.3 节），不属于存储层。

---

## 4. 目录结构与文件命名

### 4.1 生产落盘路径

`ProductionCaptureRunner` 内的 writer 闭包决定最终路径
（`src/waveform_storage/acquisition/runtime.py` 第 319–341 行）：

```
{local_data_root}/{YYYYMMDD}/raw/BIData/RAW-{HHMMSS}-{device_id}-S{sequence:05d}.h5
```

- `local_data_root` 默认 `/SHINE_Data/AC/LA`，环境变量 `WAVEFORM_LOCAL_DATA_ROOT`
  （`runtime.py:AcquisitionServerSettings.from_env` 第 72–74 行）。
- `YYYYMMDD` 与 `HHMMSS` 均取自该周期的 `cycle_started`（本地时区，`astimezone()`）。
- 目录由 `_atomic_hdf5_write` 的 `destination.parent.mkdir(parents=True, exist_ok=True)`
  隐式创建（`hdf5_io.py` 第 374 行）。

### 4.2 暂存路径

设备侧 TXT 先落到暂存区再解析（`runtime.py` 第 422 行）：

```
{staging_root}/{request_id}/S{sequence:05d}/{device_id}.txt
```

`staging_root` 默认 `{local_data_root}/.waveform-staging`（第 101–107 行）。设备侧源文件名由
注册表 `file_pattern` 决定，默认 `*.txt`（`config/registry.py` 第 128、213 行）。

### 4.3 对齐产物与导出命名

| 产物 | 命名 | 代码位置 |
| --- | --- | --- |
| v2 对齐文件 | `{run_id}_{time_sec}_S{seq:05d}_{request_id}_BPMdata_v2.h5` | `retrieval_service.py:RetrievalService.export` 第 235–247 行 |
| legacy 合并文件 | `{run_id}_{time_sec}_BPMdata.h5` | 同上第 239–243 行 |
| Agent v2 对齐附件 | `alignment-v2.h5`、`alignment-legacy.h5` | `application/agent_v2_service.py` 第 625–629 行 |

### 4.4 文件名被反向解析的位置（改名前必须同步）

| 使用方 | 正则/模式 | 位置 |
| --- | --- | --- |
| 元数据登记 | `^RAW-(?P<time>\d{6})-.+-S(?P<sequence>\d{5})\.h5$` | `metadata/service.py:_TIME_FIELD`（第 29 行） |
| Legacy 时间段列表 | `find {remote_path} -name '*.h5'`，取 `basename.split("-")[1]` | `transport/ssh_storage.py:list_time_fields`（第 149–163 行） |
| Legacy 精确文件查找 | `find ... -name '*{time_sec}*.h5'`，再匹配 `RAW-\d+-(.*?)-S\d+\.h5` | `transport/ssh_storage.py:find_h5_files`（第 166–184 行） |
| 历史回填 | 从 `YYYYMMDD` 目录与 `RAW-HHMMSS-<device>-S00000.h5` 解析日期/时间/设备 | `docs/MongoDB元数据模块设计.md` §5 |

真实交付目录核验（只读）：`data/samples/20251112/RAW-110023-AC_LA_INJ1_BI_SBPM08-S00000.h5`
等 22 个文件符合 `RAW-{HHMMSS}-{device_id}-S{seq}.h5`，但**缺少** `raw/BIData` 两级目录，
说明样本目录是扁平的历史搬运目录，不是生产写入路径的直接产物。

---

## 5. HDF5 与元数据的分工

### 5.1 单设备 raw HDF5 schema（生产格式）

`write_single_device_hdf5`（`src/waveform_storage/io/hdf5_io.py` 第 43–85 行）：

| 位置 | 内容 | 类型 |
| --- | --- | --- |
| 根属性 `Device` | 设备 ID | 字符串 |
| 根属性 `Data_0` / `Data_1` | 固定 `"bpm_x"` / `"bpm_y"` | 字符串 |
| 根属性 `capture_metadata_json` | 采集元数据 JSON（紧凑、键排序） | 字符串 |
| 数据集 `BunchIDData` | `(1, N)` 束团编号 | `uint64` |
| 数据集 `Data` | `(2, N)`，第 0 行 X、第 1 行 Y | `int64` |

写入前强校验：数组一维、长度相等、bunchID 整数、X/Y 整数；否则 `Hdf5SchemaError`
（第 52–66 行）。`.part` 临时文件 + `os.replace` 保证不会出现半写文件（第 373–385 行）。

`capture_metadata_json` 的字段由调用方写入，生产 runner 写入：
`protocol_version`、`request_id`、`frequency_hz`、`duration_seconds`、`capture_sequence`、
`captured_at`（`runtime.py` 第 333–340 行）。**注意**：该 JSON 里没有 `device_id`，
设备身份取自根属性 `Device`。

### 5.2 元数据文档（MongoDB）

三个集合（`mongo_repository.py:MongoMetadataRepository` 第 34–36 行）：

| 集合 | `_id` | 保存内容 | 不保存 |
| --- | --- | --- | --- |
| `capture_tasks` | `request_id` | 频率、时长、区域、设备、注册表版本、状态与状态历史、成功/失败计数、软件版本与 git commit | 波形数组 |
| `waveform_files` | `record_id`（见 3.2） | 存储域、路径、schema 名/版本、字节数、可选 sha256、数据集 shape/dtype、点数、`x_unit`/`y_unit`/`scale_factor` | 波形数组 |
| `device_registry_versions` | `registry_id` = `sha256:<注册表文件内容哈希>` | 非敏感设备字段快照 | 密码/私钥/URI |

`registry_id` 的算法在 `metadata/service.py:_registry_id`（第 303–305 行），这是仓库内既有的
“内容派生标识”先例（与 `alignment_source_hash` 同类做法）。

### 5.3 MongoDB 是可选件

`MongoSettings` 默认 `enabled=False`（`metadata/settings.py` 第 42 行）。未启用时：
`connect()` 直接抛 `MetadataRepositoryError("MongoDB metadata is not enabled")`
（`mongo_repository.py` 第 46–48 行），服务端元数据查询返回 `METADATA_UNAVAILABLE`
（`server.py` 第 652–660 行），历史检索退回 Legacy SSH 目录扫描路径
（`docs/MongoDB元数据模块设计.md` §1）。写入失败**不阻塞** HDF5 落盘
（`service.py:_best_effort` 第 307–311 行）。

---

## 6. 历史查询：Legacy 日期时刻接口 vs 段身份接口

### 6.1 两套接口并存

协议 v2 同时提供五个元数据命令（`protocol.py` 第 20–25 行常量定义）：

| 类别 | 命令 | 选择键 | 服务端实现 |
| --- | --- | --- | --- |
| Legacy | `list_capture_times` | `storage_date_local` | `server.py:_handle_metadata_query` 第 673–683 行 → `mongo_repository.py:list_capture_times` |
| Legacy | `find_waveform_files` | `storage_date_local` + `time_sec` + `devices` | `server.py` 第 704–709 行 → `mongo_repository.py:find_waveform_files` |
| 新 | `list_capture_runs` | `storage_date_local` | `server.py` 第 662–672 行 → `mongo_repository.py:list_capture_runs` |
| 新 | `list_capture_segments` | `capture_request_id` | 同上 → `mongo_repository.py:list_capture_segments` |
| 新 | `find_waveform_files_by_segment` | `capture_request_id` + `capture_sequence` + `devices` | `server.py` 第 698–703 行 → `mongo_repository.py:find_waveform_files_by_segment` |

`CaptureSegmentQueryRequest` 的注释明确了设计意图：目标采集 ID 与本次查询的关联 ID 相互独立
（`protocol.py` 第 232–235 行），即 `request_id` 字段只是查询信封的关联 ID，
`capture_request_id` 才是查询目标。

### 6.2 新旧接口的关系与真实差别

Legacy 的 `(date, time_sec)` 是**时刻级**键，不是任务级键：

- `time_sec` 只有 6 位 `HHMMSS`（`protocol.py:TIME_FIELD_PATTERN` 第 28 行；校验第 212–215 行），
  且来自文件名节选（`service.py:_TIME_FIELD` 第 29 行）。
- `find_waveform_files` 的查询条件只有 `storage_date_local`、`status=completed`、可选
  `time_sec` 与 `device_id`（`mongo_repository.py` 第 246–253 行），**不含 `request_id`**。
- 因此同一天同一秒若有两个请求（或一个请求的多个段在同一秒内开始），Legacy 查询会同时返回
  多个任务的记录，返回结果里也不会出现段身份提示（`server.py` 第 710–719 行只投影
  `request_id`/`capture_sequence`/`device_id`/`path`/`storage_id`）。

新接口用完整 `request_id + capture_sequence` 唯一确定一段（`AGENTS.md` §“架构边界”：
“历史查询使用完整 `request_id + capture_sequence`”），并把段号显式返回给客户端
（`CaptureSegment.capture_sequence`，`metadata/history.py` 第 65–103 行）。

**结论**：Legacy 接口保留是为兼容旧客户端，不是等价能力；新客户端必须使用段身份接口才能
无歧义取到“某一个真实数据段”。

### 6.3 采样率与时间轴不在存储层

存储层只存 `frequency_hz`（请求频率）与段级 `captured_at`。把 bunchID 换算成相对时间发生在
分析层：`analysis/loaders.py:_id_times`（第 153–166 行）以“最多见的相邻 ID 差值”为基准步长，
按 $t_k = (\mathrm{ID}_k-\mathrm{ID}_0)/(\mathrm{step}\cdot f_s)$ 建相对时间轴。
`docs/spectrum-analysis-design.md` §“时间轴与质量规则”明确：“bunchID 数值不能直接推断为 Hz”、
“HDF5 保留相对时间；采集轮次开始时间只记为来源信息”。该换算的完整语义、参数与误判排除见
[对齐语义、参数与诊断手册](alignment-semantics-and-diagnostics.md) 第 4.5、4.6 节。

---

## 7. 关键常量与参数（存储/数据流相关）

| 参数 | 默认值 | 单位 | 合法范围 | 越界行为 | 代码位置 |
| --- | --- | --- | --- | --- | --- |
| `frequency_hz` | 请求必填（GUI 默认 100） | Hz | 协议层：有限正数；服务端白名单：$\{1000,500,100,50,10,5,2\}$ | `ServerSettingsError: unsupported capture frequency ... Hz` | `protocol.py` 第 114–122 行；`runtime.py:_CAPTURE_INTERVAL_SECONDS` 第 491–501 行、`capture_interval_seconds` 第 539–549 行 |
| 周期等待 $I(f_s)$ | 按频率查表 | s | 精确字典命中，无插值 | 同上，直接拒绝 | `runtime.py` 第 491–501 行 |
| `duration_seconds` | 请求必填 | s | $>0$；$\le$ 服务端上限 | `ProtocolValidationError` → `REGISTRY_VALIDATION_FAILED` | `protocol.py` 第 123–130 行；`server.py:RegistryPolicy.validate` 第 265–269 行 |
| `max_capture_seconds` | 4200 | s | 1–86400（环境变量） | 启动期 `ServerSettingsError` | `runtime.py` 第 56、156–162 行 |
| `max_capture_devices` | 32 | 台 | 1–1000（环境变量） | 启动期 `ServerSettingsError` | `runtime.py` 第 57、163–169 行 |
| `RegistryPolicy.max_duration_seconds` | 3600 | s | 构造参数 | `ProtocolValidationError` | `server.py` 第 243 行、第 265–269 行 |
| `RegistryPolicy.max_devices` | 32 | 台 | 构造参数 | `ProtocolValidationError` | `server.py` 第 244 行、第 270–273 行 |
| `remote_file_settle_seconds` | 2 | s | 0–300 | 启动期 `ServerSettingsError` | `runtime.py` 第 54、144–150 行 |
| `expected_points`（注册表） | 1024 | 点 | 正整数 | `TxtParseError: expected N points, found M` | `config/registry.py` 第 55、129 行；`io/txt_parser.py` 第 22、48–51 行 |
| `MongoSettings.server_selection_timeout_ms` | 3000 | ms | 100–300000 | 启动期 `MongoSettingsError` | `metadata/settings.py` 第 54–60 行 |

设备侧下载等待超时按设备计算（`runtime.py` 第 436–439 行）：

$$
T^{\text{wait}}_d = \min\left(T_{\max},\ \max\left(15,\ \frac{\text{expected\_points}}{f_s} + 12\right)\right)\ \text{s},
\quad T_{\max} = \texttt{max\_capture\_seconds}
$$

该式来自代码：

```python
wait_timeout_seconds=min(
    float(getattr(self.settings, "max_capture_seconds", 4200)),
    max(15.0, item.expected_points / frequency_hz + 12.0),
)
```

---

## 8. 存储边界（硬约束）

| 约束 | 内容 | 证据 |
| --- | --- | --- |
| 一段一文件/设备 | 一个 `capture_sequence` 内每台设备恰好一个 HDF5 | `runtime.py` 第 320–341 行；`metadata/models.py:record_id` |
| 一请求多段 | 同一 `request_id` 下 `capture_sequence` 从 0 递增，数量由总窗口与周期等待决定 | `runtime.py` 第 295、367 行 |
| 段不默认拼接 | 不把不连续段拼成一条连续波形 | `AGENTS.md` 第 23 行；`docs/CURRENT_STATUS.md` §“架构与范围”（第 276 行）；`docs/agent-api-v2.md` 第 135 行“算法不会拼接不同数据段” |
| 整任务分析未实现 | 整任务频谱应先逐段计算再按明确方法汇总，本阶段不做 | `AGENTS.md` 第 23 行；`docs/CURRENT_STATUS.md` 第 278 行 |
| 段内有失败不隐藏 | 每设备每周期独立成败，失败原因带阶段名（EPICS 触发 / 设备文件等待与下载 / TXT 解析 / HDF5 写入） | `capture_service.py` 第 114、153、162、173 行；汇总 `runtime.py` 第 376–405 行 |
| 空/半文件不入目录 | 只有原子替换完成后的正式文件才被元数据登记 | `hdf5_io.py:_atomic_hdf5_write`；`docs/MongoDB元数据模块设计.md` §4 第 3 步 |

---

## 9. 文档-代码差异

以代码为准。下列差异均可用给定位置复核。

| # | 文档说什么 | 代码实际做什么 | 证据 |
| --- | --- | --- | --- |
| D1 | `docs/MongoDB元数据模块设计.md` §2：`waveform_files._id` 为 `<request_id>:<device_id>` | 首段确实是该形式；**非首段**为 `<request_id>:<device_id>:S<seq:05d>` | 文档 §5（第 84–86 行）已自我更正；代码 `metadata/models.py:record_id` 第 233–237 行。同文档 §2 与 §5 表述不一致，以 §5 与代码为准 |
| D2 | `docs/MongoDB元数据模块设计.md` §4：HDF5 原子替换为正式文件后“才写入 `waveform_files.status=completed`” | 登记发生在任务状态为 `succeeded` **或 `failed`** 时，逐文件写 `status="completed"`。即“部分设备失败”的任务也会产生 `completed` 文件记录 | `metadata/service.py:record_status` 第 166–167 行；`metadata/models.py` 第 188 行默认 `status="completed"` |
| D3 | `docs/数据对齐v2设计.md` §6：导出支持 `auto/legacy/v2`，`auto` 在有缺失单元时选 v2 | 只要 `StorageQuery.request_id` 非空（即带真实段身份），代码**强制** `selected = "v2"`，显式 `legacy` 被覆盖 | `retrieval_service.py:RetrievalService.export` 第 231–238 行。该强制规则只在 `docs/agent-api-v2.md` 第 137 行有记述，设计文档未记 |
| D4 | `docs/数据对齐v2设计.md` §2：X/Y 为 0 是合法数据，通过 `valid_mask` 与缺失区分 | 对齐层参数 `zero_policy` 实际作用于 **bunchID == 0**，与 X/Y 零值无关；X/Y 零值处理在分析层（`AnalysisConfig.zero_policy: keep / mask_double_zero`） | 代码 `processing/alignment.py:_prepare_records` 第 203 行 `np.count_nonzero(bunch_ids == 0)`；分析层 `analysis/models.py` 第 54、77–78 行；`analysis/engine.py` 第 32–36 行 |
| D5 | `docs/采集协议v2候选.md` §“v2 变化”未说明频率白名单归属层 | 协议层只校验“有限正数”，白名单在运行层 `capture_interval_seconds` 内；因此“协议接受但服务拒绝”是正常路径 | `protocol.py` 第 114–122 行 vs `runtime.py` 第 539–549 行；`docs/CURRENT_STATUS.md` 第 29–34 行记录了该分层导致的 10 Hz 事故 |
| D6 | `docs/MongoDB元数据模块设计.md` §5 称历史回填解析 `RAW-HHMMSS-<device>-S00000.h5` | 回填/登记使用的正则是 `^RAW-(\d{6})-.+-S(\d{5})\.h5$`，`sequence` 可为任意 5 位而非固定 `00000` | `metadata/service.py:_TIME_FIELD` 第 29 行；`_record_files` 第 245–247 行 |

---

## 10. 适用版本与核验范围

### 已核验（2026-10-29，只读）

| 类别 | 文件 |
| --- | --- |
| 引导与状态 | `AGENTS.md`；`docs/CURRENT_STATUS.md` |
| 协议与采集 | `src/waveform_storage/acquisition/protocol.py`、`runtime.py`、`server.py`；`application/capture_service.py` |
| 落盘与 IO | `src/waveform_storage/io/hdf5_io.py`、`io/txt_parser.py`；`transport/ssh_storage.py`（第 145–300 行） |
| 元数据 | `src/waveform_storage/metadata/models.py`、`service.py`、`mongo_repository.py`、`history.py`、`settings.py` |
| 检索与导出 | `src/waveform_storage/application/retrieval_service.py`（第 1–260 行） |
| 分析入口 | `src/waveform_storage/analysis/loaders.py`（第 136–166 行）；`analysis/models.py`；`analysis/engine.py`（第 1–90 行） |
| 注册表 | `src/waveform_storage/config/registry.py`（字段与默认值） |
| 既有文档 | `docs/采集协议v1候选.md`、`docs/采集协议v2候选.md`、`docs/数据对齐v2设计.md`、`docs/MongoDB元数据模块设计.md`、`docs/agent-api-v2.md`、`docs/spectrum-analysis-design.md`、`docs/设备注册表.md`、`docs/diagrams/waveform-storage.dataflow.json` |
| 真实数据 | `data/samples/20251112/` 22 个 HDF5 的 shape/dtype/bunchID 步长/严格交集（本地只读计算） |

### 未核验（不得据此推断）

- **未运行任何测试**（`tools/run_quality.py` 未执行），未做发布验收、SHA-256 manifest 校验、
  二进制身份核验或真实桌面 smoke。
- 未连接现场服务器、EPICS、MongoDB 实例、systemd 或 dashboard；现场运行状态未复核。
- 未读取 `apps/`、`packaging/`、`legacy/` 全部代码（仅按需查阅 `apps/operator_gui` 的少量片段）。
- `HA`/`capture_sequence` 跳号、部分成功段的生产实例行为未在真实数据上复现。
- 10 Hz 下 2100 s 等待值的口径（`runtime.py` 第 496–498 行注释“20000 triggers / 10 Hz = 2000 s
  plus the 5 Hz margin”）**待核实**：注释的“20000 触发”与“每周期一个文件”的对应关系未能从代码
  唯一确定，现场实测未取得。
- 采集任务执行器 `PersistentTaskExecutor` / `JsonTaskStore` 的源码位置本次未逐行核对，
  仅通过 `docs/agent-api-v2.md` 与 `server.py` 调用点间接确认存在（待核实具体文件与行号）。
