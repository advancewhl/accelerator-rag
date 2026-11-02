"""Author v2's 50 dev questions and bind exact excerpts; never run to grade results.

Rebinding after a source edit is a new annotation revision, not validation.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from accelerator_rag.evaluation.validity import load_corpus, Pilot, validate_pilot  # noqa: E402
from accelerator_rag.evaluation.retrieval import normalize_evidence  # noqa: E402

# Each record: query, required claims, forbidden inference, (document, excerpt)s.
A = "waveform-alignment-semantics"
S = "waveform-storage-dataflow"
F = "waveform-fault-history"
R = "rag-ingestion-verification-rollback"
CONDITIONS = [
    (
        "strict 对齐成功，是否说明请求中的全部 BPM 都参加了，而且它们物理同步？",
        ["核对 skipped_devices 与实际设备名单", "整数编号匹配不能证明物理时间同步"],
        "对齐成功即可证明全部设备同步",
        [
            (
                A,
                "这里的“所有设备”指通过预处理的设备。重复编号、非法数组等问题可能导致某台设备被跳过。",
            ),
            (A, "仅凭对齐成功，不能证明设备在物理时间上同步。"),
        ],
    ),
    (
        "三台 BPM 允许部分缺点，改成 coverage 却没有增加共同编号，应先检查什么？",
        ["两个覆盖率阈值默认均为 1.0", "按分析需要决定阈值并读取 valid_mask"],
        "只切换模式就必然增加共同点",
        [
            (
                A,
                "两个覆盖率阈值默认都是 `1.0`。仅把模式切换成 `coverage`，保留这些默认值，通常不会增加共同编号。阈值应由分析要求决定，不以“留下更多点”为唯一目标。",
            ),
            (A, "但缺失位置仍然缺失，后续处理必须读取 `valid_mask`。"),
        ],
    ),
    (
        "coverage 导出的 X、Y 矩阵里有很多 0，可以直接全部用于均值和频谱吗？",
        ["占位零与真实零必须用 valid_mask 区分", "统计和频谱前应用掩码"],
        "全部零值都是有效测量",
        [
            (
                A,
                "覆盖率输出中，缺失位置的 X、Y 可能填为 0，只有 `valid_mask` 能区分占位值和真实零值。直接对整个数组求均值、做频谱或比较幅值，会把缺失值当成观测值。",
            )
        ],
    ),
    (
        "对齐输出矩阵能否直接沿用界面最初勾选设备的顺序解释每一行？",
        ["输出按 device_id 排序", "按输出 device_ids 映射矩阵行"],
        "输出顺序必定等于勾选顺序",
        [
            (
                A,
                "输出设备按 `device_id` 排序。使用矩阵时应依据输出的 `device_ids` 对应行，不能沿用最初勾选设备的顺序。",
            )
        ],
    ),
    (
        "两个通道分析后的时间轴都从 0 秒开始，是否可以直接比较跨设备相位？",
        [
            "每通道首个有效点可分别归零",
            "保留 first_valid_offset_seconds 或共同有效区间",
        ],
        "同为零起点证明原始时刻相同",
        [
            (
                A,
                "分析准备阶段会应用每个通道的有效掩码，并把该通道的首个有效点移到 0，同时记录 `first_valid_offset_seconds`。",
            ),
            (
                A,
                "比较跨设备相位、时延或相关性时，应保留偏移信息，或选择共同有效区间，不能只比较各自归零后的横轴。",
            ),
        ],
    ),
    (
        "历史波形缺少任务采样率，今天 timing PV 显示 500 Hz，能否据此建立历史时间轴？",
        [
            "优先使用历史任务频率",
            "缺少记录需要有依据的补充信息",
            "当前 PV 不能替代历史频率",
        ],
        "直接套用今天的 500 Hz",
        [
            (
                A,
                "采样率优先来自历史任务记录。缺少记录时，需要有依据的补充信息，不能拿当前 timing PV 的值解释过去的数据。",
            )
        ],
    ),
    (
        "对齐得到 200 个有效点、1 s 跨度，是否满足默认 high_band 分析条件？",
        ["默认至少 128 个有效点", "默认至少 5 s", "点数满足但跨度不满足"],
        "点数超过 128 就合格",
        [
            (
                A,
                "默认 `high_band` 配置要求至少 128 个有效点和 5 s 的有效跨度；其他分析配置可能要求更长的记录。应以本次分析配置为准。",
            )
        ],
    ),
    (
        "编号中间有缺口，当前加载器是否一律把缺失时间压缩掉？",
        ["推断步长整数倍的缺口可保留间隔", "基本步长本身推断不可靠时仍有歧义"],
        "所有缺口都会被压缩或都能无损恢复",
        [
            (
                A,
                "当编号缺口是所推断步长的整数倍时，加载器可以在时间轴上保留这个间隔。如果数据整体已经稀疏到把较大的间隔当成基本步长，单靠现有编号可能无法识别中间遗漏了多少采样。",
            )
        ],
    ),
    (
        "coverage 结果是不是一律不能导出 legacy HDF5？需要保留缺失掩码时选什么？",
        [
            "legacy 不能表达缺失位置",
            "coverage 全部有值时未必禁止 legacy",
            "保留掩码和参数用 v2 HDF5",
        ],
        "coverage 无论有无缺失都不能写 legacy",
        [
            (
                A,
                "需要保留缺失掩码、对齐参数和质量信息时，使用 v2 HDF5。Legacy 格式不能表达缺失位置，但覆盖率结果如果所有位置都有值，并非一概不能写成 legacy。",
            )
        ],
    ),
    (
        "两份文件日期和时刻相同，可以直接当作同一采集段进行对齐吗？",
        ["需要 request_id、capture_sequence、device_id", "同秒可能有不同任务"],
        "按日期时刻即可唯一确定数据身份",
        [
            (
                S,
                "**定位一份原始波形，要保留任务 ID、段序号和设备 ID。** 日期和时刻适合帮助人查找，但同一天同一秒可能存在不同任务，不能单独充当数据身份。",
            )
        ],
    ),
    (
        "一个采集任务运行了 70 分钟，是否等于得到 70 分钟连续波形？",
        ["任务窗口不同于分析数据跨度", "数据段间可能存在等待下载或失败间隔"],
        "任务时长等于连续波形时长",
        [
            (
                S,
                "长时间运行一个任务，不代表得到同样时长的连续波形；下载耗时也不属于波形采样时长。",
            ),
            (
                S,
                "不同数据段之间可能存在等待、下载或失败造成的间隔。系统按段读取和分析，不自动把多段拼成连续波形。",
            ),
        ],
    ),
    (
        "同段设备的 captured_at 一样，是否证明每个采样点都在同一时刻采集？",
        ["captured_at 是段采集周期开始时刻", "不表示每设备每采样点的时刻"],
        "共享 captured_at 可证明逐点物理同步",
        [
            (
                S,
                "生产文件的 `captured_at` 是该段采集周期开始时刻，同段设备共享这个值。它不表示各设备每个采样点的实际采样时刻。",
            )
        ],
    ),
    (
        "对齐参数 zero_policy 和分析配置 mask_double_zero 是同一种零值处理吗？",
        [
            "对齐 zero_policy 处理 bunchID 零编号",
            "mask_double_zero 处理 X、Y 同时为零",
            "两者属于不同阶段",
        ],
        "丢掉零编号等价于屏蔽 X、Y 双零值",
        [
            (A, "处理 `bunchID == 0`，不是处理 X、Y 的零值"),
            (
                A,
                "分析配置也有名为 `zero_policy` 的参数，其 `mask_double_zero` 处理 X、Y 同时为 0 的记录。它与上表的编号零值策略属于不同阶段。",
            ),
        ],
    ),
    (
        "在 strict 模式下把 min_id_device_coverage 设成 0，可以因为未使用这个阈值而通过吗？",
        ["strict 虽不使用覆盖率筛选，构造仍校验范围", "0 不合法，将抛 ValueError"],
        "strict 可以忽略非法阈值",
        [
            (A, "大于 0 且不超过 1"),
            (
                A,
                "strict 不使用两个覆盖率阈值筛选数据，但参数构造时仍校验其范围。非法模式、策略或阈值会抛出 `ValueError`。",
            ),
        ],
    ),
    (
        "发现两台 BPM 编号相差一点，当前对齐参数能否设置时间容差或自动缩放编号？",
        ["当前没有时间容差、编号容差、自动缩放参数", "转换需先确认依据并独立记录"],
        "虚构 tolerance 或自动编号校正参数",
        [
            (
                A,
                "当前对齐参数没有时间容差、编号容差或自动缩放系数。如果设备编号需要转换，应先确认转换依据，并将转换作为独立处理记录下来。",
            )
        ],
    ),
]
VERSIONS = [
    (
        "2026-10-26 增加 10 Hz 后，已有记录是否证明真实采集到 HDF5 落盘全链路通过？",
        [
            "cae6b64 增加 10 Hz 和 2100 s 等待值",
            "证据只确认接口及相关测试",
            "没有新的完整真实采集验收",
        ],
        "频率接口成功等于完整采集成功",
        [
            (F, "`cae6b64` 增加 10 Hz 档位和 2100 s 等待值。"),
            (F, "现有证据没有完成一次新的 10 Hz 真实采集、下载与 HDF5 落盘验收。"),
        ],
    ),
    (
        "能否把 10 Hz 说成国庆后新出现，进而解释所有国庆后采集问题？",
        [
            "归档至少在 2026-08-17 已有 10 Hz",
            "降采样记录不能穷尽短时状态或证明事故因果",
        ],
        "10 Hz 国庆后才首次出现",
        [
            (F, "至少在 2026-08-17 已出现 10 Hz，后续多个日期也有记录。"),
            (
                F,
                "这些查询采用降采样视图，能证明返回记录中的读数，不能穷尽所有短时变化。",
            ),
        ],
    ),
    (
        "8 月已有 10 Hz，而旧支持表缺少它，能否断言 8 月所有请求都会返回 TIMING_FREQUENCY_FAILED？",
        [
            "89bb146 尚未使用后来的 timing PV 核对路径",
            "需实际部署、执行入口、时间和日志",
            "不能反推事故窗口",
        ],
        "把潜在不支持推断成已确认事故",
        [
            (F, "所查旧服务端 `89bb146` 尚未使用后来引入的 timing PV 核对路径。"),
            (
                F,
                "若要确认某次请求是否被拒，还需同时取得当时的部署版本、实际执行入口、请求时间及错误日志。",
            ),
        ],
    ),
    (
        "2026-10-07 前后的服务端对请求频率核对有什么变化，旧任务是否已经证明存在频率错配？",
        [
            "61b47db 增加读取 PV 与请求核对",
            "此前所查版本无此检查",
            "代码可接受不一致不等于真实任务已错配",
        ],
        "将行为可能性写成真实事故",
        [
            (
                F,
                "提交 `61b47db` 增加了受理新请求前读取 timing PV、核对请求频率的逻辑。不一致时返回 `FREQUENCY_MISMATCH`。此前所查服务端版本直接提交任务，没有这项检查。",
            ),
            (
                F,
                "它说明旧入口可能接受频率不一致的请求，但没有证明此前某个具体任务已经发生过错配。",
            ),
        ],
    ),
    (
        "当前正式前端和服务端都读取 timing PV，能否证明整个任务期间采集频率不变？",
        ["前端启动和采集前读取，服务端受理时检查", "检查提交时频率，非连续监控"],
        "两次检查保证全程恒频",
        [
            (
                S,
                "正式前端在启动和采集前读取 timing PV `AC-LA-INJ1-TIM:WRN1:MCFQ8`，服务端在受理新的采集请求时再次检查。这个机制检查的是提交时的频率，不能证明整个任务期间频率一直不变。",
            )
        ],
    ),
    (
        "旧界面按编号差和固定因子显示秒数，新界面改用分析器跨度后是否就验证了设备物理时基？",
        [
            "旧换算依赖编号计时语义",
            "f7f28fb 改为分析器相对时间跨度",
            "新方式仍依赖采样率及步长模型",
        ],
        "新显示证明物理时基已验证",
        [
            (
                F,
                "这个解释依赖编号具有特定计时语义，但界面没有说明前提，也没有根据设备编号约定进行确认。",
            ),
            (
                F,
                "`f7f28fb` 移除了这一显示方式，改为展示分析器建立相对时间轴后得到的跨度。新显示仍依赖采样率和编号步长模型，所以“来自分析器”不等于已完成物理时基验证。",
            ),
        ],
    ),
    (
        "10 月 2 日现场能接受 5 Hz，但附近 Git 提交不支持，应该怎样描述当时部署版本？",
        [
            "最近提交不能完整解释现场行为",
            "可能有现场未提交变更或记录缺失",
            "不能唯一还原部署",
        ],
        "直接认定最近提交就是现场全部源码",
        [
            (F, "至少可以确认，不能用该提交完整解释现场行为。"),
            (
                F,
                "可能的原因包括未提交的现场修改或缺失的版本记录。现有材料不足以唯一还原当时部署",
            ),
        ],
    ),
    (
        "alignment_algo_hash 相同，是否足以证明两个版本的时间轴和导出行为全部相同？",
        ["hash 只覆盖 processing/alignment.py", "还需相关模块和部署记录"],
        "单模块 hash 等于完整系统版本",
        [
            (
                A,
                "只标识 `processing/alignment.py`。它不覆盖历史查询、时间轴建立、分析预处理或界面显示；比较不同版本的行为时，还需查看相关模块和部署记录。",
            )
        ],
    ),
    (
        "旧 legacy 设备选择顺序敏感，与 2026 年 7 月重构的 strict、coverage 有何区别？",
        [
            "旧路径按顺序收缩交集并可能跳过设备",
            "重构引入独立 strict、coverage 和缺失信息",
            "无交集与算法顺序敏感是不同问题",
        ],
        "把旧顺序选择问题全部归为设备差异",
        [
            (
                F,
                "按输入顺序收缩交集，并在交集下降时跳过设备。这样可能因输入顺序不同而保留不同设备组。",
            ),
            (
                F,
                "2026-07-25 的重构引入独立的 strict、coverage 算法和明确的缺失信息，并隔离旧路径。",
            ),
        ],
    ),
    (
        "现有历史材料能否证明国庆前后修改 alignment.py 算法导致了共同点减少？",
        [
            "所查历史只在 25e6b73 增加 metadata",
            "不支持已查明算法回归",
            "仍需实际部署及相同输入对照",
        ],
        "统一归因为国庆后算法回归或排除所有软件因素",
        [
            (
                F,
                "这不支持“该模块在国庆前后改动算法导致回归”的说法。但结合 case-04，也不能据此排除所有软件、部署和配置因素。",
            ),
            (F, "若要研究版本回归，还需在可确认的版本上使用相同原始输入比较结果。"),
        ],
    ),
]
DIAGNOSIS = [
    (
        "case-07 的 25 台设备各有两万个点，却只剩几百共同点，应怎样定位，能否说目标设备已经损坏？",
        [
            "先查同任务同段、编号范围和步长",
            "COLDBPM05 编号差异限制交集",
            "逐台排除不是硬件根因证明",
        ],
        "共同点减少直接证明设备损坏",
        [
            (A, "确认所有文件来自同一任务、同一数据段。"),
            (
                F,
                "目标设备 `AC_LA_L1_BI_COLDBPM05` 的编号步长为 28–76，其余 24 台为 2000。",
            ),
            (F, "它尚不能解释目标设备为什么产生这种编号，也不能据此判定设备损坏。"),
        ],
    ),
    (
        "f7f28fb 增加预检查后，是否已经让 case-07 全部 25 台恢复约 19500 个共同点？",
        ["增加提示和确认，不修复编号", "约 19500 是排除目标设备的诊断结果"],
        "把改变设备集合说成完整系统修复",
        [
            (
                F,
                "该变更没有自动修复编号，也没有让 25 台设备恢复到约 19500 个共同点；表中最后一列只是改变设备集合后的诊断结果。",
            )
        ],
    ),
    (
        "采集任务显示 failed，就应删除已经生成的全部文件并从对齐参数开始排查吗？",
        [
            "任务失败可能留下可用文件",
            "保存成功文件和失败清单",
            "先查设备产数与下载，再决定分析范围",
        ],
        "failed 等于所有文件均无效",
        [
            (S, "任务失败，也可能已经留下可用文件。"),
            (
                F,
                "先保存成功文件及失败设备清单，再检查设备侧文件生成、完成标记和下载记录。",
            ),
        ],
    ),
    (
        "case-02 中 18 台文件为空、2 台有效，是否已经证明 18 台硬件都有故障？",
        [
            "记录支持没有取得有效文件",
            "设备侧硬件根因未确定",
            "成功数据是否使用取决于分析目标",
        ],
        "零字节文件等于已确认硬件坏",
        [
            (F, "日志支持“18 台没有取得有效文件”，尚不足以确定每台设备的硬件根因。"),
            (F, "后续是否使用剩余 2 台数据，由分析目标决定。"),
        ],
    ),
    (
        "任务完成后历史页查不到，同时出现 METADATA_UNAVAILABLE，是否说明 HDF5 波形丢失？",
        [
            "元数据目录与 HDF5 分开",
            "先检查元数据服务连接和实际文件",
            "目录故障不能直接推断文件丢失",
        ],
        "MongoDB 不可用必然导致 HDF5 丢失",
        [
            (
                S,
                "MongoDB 保存任务及文件目录，HDF5 保存波形数组。元数据写入失败不会阻止已经完成的 HDF5 落盘。",
            ),
            (S, "遇到 `METADATA_UNAVAILABLE`，先检查元数据服务是否启用、是否可连接。"),
        ],
    ),
    (
        "日志写 capture cancelled during service shutdown，能否记为用户主动取消且所有数据都未完成？",
        ["只定位到服务关停", "关停原因未确认", "按实际文件清单判断完成段"],
        "改写成用户主动取消或推断全无产物",
        [
            (
                F,
                "该消息将中断定位到服务关停，但记录未说明关停来自发布、人工重启还是其他原因。也不应将它改写为“用户主动取消”。",
            ),
            (F, "核对任务状态历史与服务日志，按实际文件清单判断哪些段完成。"),
        ],
    ),
    (
        "同样是 TIMING_FREQUENCY_FAILED，应把读取 PV 失败和 unsupported capture frequency 10 Hz 怎么区分？",
        [
            "读完整错误信息",
            "读取失败查连接，未支持档位查支持表及版本",
            "不能只修界面或自行插值等待值",
        ],
        "两种原因一律解释为显示错误",
        [
            (
                F,
                "读取 PV 失败与读到未支持档位需要不同处理。查到新档位也不应自行按比例推导等待值，应结合设备产数规则确定。",
            ),
            (F, "其背后是支持表缺少 10 Hz，不能仅按显示问题处理。"),
        ],
    ),
    (
        "某 BPM 只有编号 0 比其他设备多一点，应否认定这个零编号必然导致非零共同点减少？",
        ["不必然减少非零交集", "先比较实际编号集合", "编号零值策略不同于位置零值"],
        "零编号必然破坏所有非零交集",
        [
            (A, "某台设备多出一个编号 0，不会必然缩小非零编号的交集。"),
            (A, "处理 `bunchID == 0`，不是处理 X、Y 的零值"),
        ],
    ),
    (
        "Markdown 干跑成功且目录有记录，是否已证明向量入库和回答验证全部完成？",
        [
            "干跑不加载 GPU、不写向量",
            "目录或 HTTP 成功不足以证明答案正确",
            "还需检索正确版本、原文引用和语义核对",
        ],
        "本地解析等于生产完成",
        [
            (
                R,
                "这个命令不打开索引、不加载 GPU 模型，也不能证明嵌入和索引写入会成功。",
            ),
            (
                R,
                "入库的完成标准是：目标内容能检索到，引用能回到对应版本的原文，答案能被原文支持。",
            ),
        ],
    ),
    (
        "两路候选索引只更新成功一路，能否把它与旧的另一路混合上线？",
        [
            "两路更新不是事务，不能单独上线",
            "保持旧服务，修复成套候选",
            "原文配置与两路索引一起对应版本",
        ],
        "混用新旧两路索引直接上线",
        [
            (R, "两路更新不是一个事务，一路失败时不能把另一路单独上线。"),
            (R, "不要把旧原文与新索引混搭，也不要一边运行服务一边覆盖其索引目录。"),
        ],
    ),
]
LIMITS = [
    (
        "今天 COLDBPM05 已经修好了吗？请直接给出当前硬件健康结论。",
        ["静态记录不能确定今天状态", "需当前设备和维修验证记录"],
        "编造实时修复或健康结论",
        [(F, "它尚不能解释目标设备为什么产生这种编号，也不能据此判定设备损坏。")],
        "insufficient",
    ),
    (
        "仅凭 case-07 排除设备后交集恢复，请确定故障发生在固件还是采样窗口。",
        ["可确认目标输入影响交集", "不能区分固件、窗口等硬件层解释", "需设备侧材料"],
        "把定位影响说成唯一物理根因",
        [(F, "编号编码、固件、采样窗口和设备运行状态仍需设备侧材料区分。")],
        "partial",
    ),
    (
        "请把这份原始 HDF5 中 X 等于 100 的点精确换算为毫米。",
        ["缺少单位与标定关系", "整数类型不能确定毫米系数", "需设备标定资料"],
        "猜测比例并给出毫米值",
        [
            (
                S,
                "原始 X、Y 是整数数值；只有获得设备对应的单位和标定关系后，才能解释为物理位置。",
            )
        ],
        "insufficient",
    ),
    (
        "请给出 2026-10-02 现场部署的唯一源码提交，并解释它为何接受 5 Hz。",
        ["已知现场接受 5 Hz，最近提交不足解释", "部署记录不足，不能唯一指定源码"],
        "把 89bb146 认定为现场完整版本",
        [
            (
                F,
                "可能的原因包括未提交的现场修改或缺失的版本记录。现有材料不足以唯一还原当时部署",
            )
        ],
        "partial",
    ),
    (
        "10 Hz 频率接口修复后，请给出新真实采集任务的 ID 和 HDF5 文件路径，证明完整修复。",
        [
            "可确认频率档位及接口修复",
            "没有新采集落盘验收记录",
            "不能编造任务 ID 和文件路径",
        ],
        "用合成路径或历史任务冒充修复后验收",
        [(F, "现有证据没有完成一次新的 10 Hz 真实采集、下载与 HDF5 落盘验收。")],
        "partial",
    ),
]
PDF_IDS = [
    "epics-pp",
    "epics-reconnect",
    "epics-cli",
    "xfel-normal-energy",
    "interlock-latency",
    "interlock-platform",
    "cryo-integration",
    "cryo-interlock",
    "timing-jitter",
    "shine-main-linac",
]
PDF_GOLD = [
    ["链接属性为 PP", "目标 SCAN 为 Passive", "输入取值前处理目标"],
    ["IOC 重启后客户端自动重建通信"],
    ["caget 读取", "caput 写入", "camonitor 持续监视"],
    ["2007 设计资料中的常规能量 17.5 GeV", "最高设计能量 20 GeV，不能混为实时运行值"],
    ["单节点响应小于 10 微秒", "节点间响应小于 100 微秒", "保留严格小于及设计要求口径"],
    ["Spartan6 XC6SLX25", "verilog HDL"],
    ["PLC 实现多数控制逻辑与 PID", "Soft IOC 从 PLC 采集信号并转为 EPICS PV"],
    [
        "站点 DI/DO 接主联锁 PLC",
        "主 PLC 执行安全逻辑并交换联锁信号",
        "CPLD 进行微秒级光电双向转换",
    ],
    [
        "Prototype II 束流同步相对外部参考小于 20 ps RMS",
        "节点间小于 10 ps RMS",
        "随机事件相对参考小于 35 ps RMS",
        "区分实测与设计指标",
    ],
    ["初步设计为超导连续波", "最终能量 8 GeV", "不作为当前在线读数"],
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-root", type=Path, default=ROOT)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/evaluation/validity-pilot-v2.json"
    )
    args = parser.parse_args()
    documents, chunks = load_corpus(ROOT, args.pdf_root)
    corpus = {d.record.doc_id: d for d in documents}

    def bind(doc_id, excerpt, page=None):
        document = corpus[doc_id]
        found = [
            p.page_number
            for p in document.parsed.pages
            if (page is None or p.page_number == page)
            and normalize_evidence(excerpt) in normalize_evidence(p.text)
        ]
        if not found:
            raise ValueError(f"source excerpt absent: {doc_id}: {excerpt}")
        page = found[0]
        ids = [
            c.chunk_id
            for c in chunks
            if c.document_id == doc_id
            and c.page_start <= page <= c.page_end
            and normalize_evidence(excerpt) in normalize_evidence(c.text)
        ]
        if not ids:
            raise ValueError(f"excerpt not in eligible chunk: {doc_id}: {excerpt}")
        return dict(
            document_id=doc_id,
            document_version=document.record.version,
            locator_kind="section" if document.record.document_type == "md" else "page",
            page=page,
            excerpt=excerpt,
            chunk_ids=ids,
        )

    items = []
    baseline = {
        q["id"]: q
        for q in json.loads(
            (ROOT / "data/evaluation/retrieval_baseline.json").read_text()
        )["queries"]
    }
    for number, (old_id, must) in enumerate(zip(PDF_IDS, PDF_GOLD, strict=True), 1):
        old = baseline[old_id]
        groups = [
            {
                "alternatives": [
                    bind(t["document_id"], t["excerpt"], t["page"])
                    for t in g["alternatives"]
                ]
            }
            for g in old["evidence_groups"]
        ]
        items.append(
            dict(
                id=f"P50-{number:03d}",
                category="pdf_control",
                query=old["query"],
                expected_status="answered",
                gold_answer="；".join(must) + "。",
                must_cover=must,
                forbidden_claims=[
                    "遗漏必要事实、混淆比较符，或把文档记载说成当前现场状态"
                ],
                evidence_groups=groups,
                cluster=groups[0]["alternatives"][0]["document_id"],
                overlaps_legacy=old_id,
                human_review="pending",
            )
        )
    for category, rows in [
        ("conditions", CONDITIONS),
        ("versions", VERSIONS),
        ("diagnosis", DIAGNOSIS),
        ("limits", LIMITS),
    ]:
        for row in rows:
            query, must, forbidden, evidence, *status = row
            groups = [
                {"alternatives": [bind(doc, excerpt)]} for doc, excerpt in evidence
            ]
            items.append(
                dict(
                    id=f"P50-{len(items) + 1:03d}",
                    category=category,
                    query=query,
                    expected_status=status[0] if status else "answered",
                    gold_answer="；".join(must) + "。",
                    must_cover=must,
                    forbidden_claims=[forbidden],
                    evidence_groups=groups,
                    cluster=evidence[0][0],
                    overlaps_legacy=None,
                    human_review="pending",
                )
            )
    payload = dict(
        schema_version="validity-pilot-v2",
        dataset_revision="2026-10-29-r1",
        purpose="development_only",
        independent_test_allowed=False,
        items=items,
    )
    pilot = Pilot.model_validate(payload)
    validate_pilot(pilot, documents, chunks)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    readable = [
        "# 有效性边界开发验证：50 题",
        "",
        "题集版本：2026-10-29-r1。仅供开发诊断；语义评分和独立人工复核待完成。",
        "",
        "证据原文、版本和块 ID 见同名 JSON；运行规则见 `docs/rag/validity-pilot-50.md`。",
        "",
    ]
    for item in items:
        readable.extend(
            [
                f"## {item['id']}：{item['query']}",
                "",
                f"类别：`{item['category']}`。预期状态：`{item['expected_status']}`。",
                "",
                "必要事实：",
                "",
                *[f"- {fact}" for fact in item["must_cover"]],
                "",
                "禁止推断：" + "；".join(item["forbidden_claims"]) + "。",
                "",
            ]
        )
    args.output.with_suffix(".md").write_text("\n".join(readable))
    print(f"Wrote {len(items)} questions to {args.output}; human review pending")


if __name__ == "__main__":
    main()
