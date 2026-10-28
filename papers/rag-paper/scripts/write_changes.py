"""Generate the paper's change/effect ledger using the same reviewed statistics."""
import json,re
from pathlib import Path

OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parents[1]
S=json.loads((OUT/'data/paper-statistics.json').read_text())
old=(ROOT/'papers/rag-thesis/rag-chapter.md').read_text()
pattern=r'不能|不应|不代表|尚未|未测量|不足以|无法'
lines=sum(bool(re.search(pattern,l)) for l in old.splitlines());occurrences=len(re.findall(pattern,old))
changes=[
('论文类型','独立学位论文章节，按阶段材料组织','系统与评测论文；8节主线，以3条贡献组织','全篇'),
('标题','面向加速器技术文档的可追溯检索增强问答系统','证据契约驱动的加速器文档检索增强问答','main.tex'),
('摘要','较长摘要中重复说明多项评价边界','250字符摘要：问题、三机制、语料与四组核心结果、意义','abstract.tex'),
('引言','从知识服务需求与边界介绍开始','从预算错配、父块/片段错配、复合问题漏答三个失效模式提出主张','introduction.tex'),
('贡献','分散在讨论中的四项工程工作','三条带数字贡献：证据契约、互补重排、可追溯问答','引言'),
('相关工作','原稿仅简述若干方法','四簇相关工作；39条真实文献；每簇明确差别','related-work.tex'),
('形式化','多个分散公式解释指标','来源三元组、组内OR、组间all/any、完整首次排名形成统一契约','evidence-contract.tex'),
('输入安全','消除截断没有自动解决语义选择问题','4,950片段零超限；完整命中8→9；将输入有效性与表示收益分离','结果6.2'),
('标注治理','变化不能解释为检索算法改善','相同排名下E5由16→18，识别可分离标注效应并统一v2','结果6.2'),
('主要效果','固定小样本上的描述性差别','配对bootstrap量化差值区间，McNemar给出p=0.500','结果6.1'),
('互补机制','方案选择证据，尚不形成普遍证明','15共同、3个E5独有、2个Qwen3独有；逐案解释净增2条','结果6.3'),
('逐问题结果','大量阶段日志与完整排名列表','2条翻转表+3条原始候选轨迹，解释装置和对象错配','表4、结果6.3'),
('证据粒度','parent命中不保证模型已经看到全部证据','将20/21与19/21差异定位到主加速器评分片段','图4a'),
('语言结果','跨语言切片不足以外推','英文13/13保持；中文5/8→7/8；跨语言目标2/3','表5；推断边界集中§7'),
('多查询','未带来稳定收益','E5 18→15；91/32=2.844倍调用，最终选择原始查询','图4b、结果6.5'),
('延迟','仅保留平均和可回答中位数','增补各组P50/P95/max及分阶段占比，保留两类分母','表6、图4c'),
('IOC反例','内部标记不能等同于独立完整性','明确报告过度完整标记：20条answered中至少1条字段缺口','结果6.6'),
('低温反例','检索不保证生成充分利用','将检索完整而回答partial定位为证据利用环节','结果6.6'),
('表格语气','表4包含“结论边界”专栏','删除该列，服务结果进入结果部分；效度四分法集中§7','结果与threats.tex'),
('范围清单','反复排除Agent、Waveform、OCR等未做项目','引言用一句限定静态问答；展望只保留独立评审、证据恢复、性能三方向','引言、结论'),
('图形','8张英文图，部分图内有免责声明小字','取舍为4张中文矢量图，180mm、标签至少8pt、直接数值与灰阶冗余','figures/'),
('公式','PDF内公式为高分辨率数学图像','6个编号公式及行内数学全部为原生LaTeX矢量字形','式1～6'),
('附录','阶段工作日志、文件长清单、个案对照','仅保留复现与数据说明、主张—证据映射','appendix.tex'),
]
def table(headers,rows):
 return '| '+' | '.join(headers)+' |\n|'+'|'.join(' --- ' for _ in headers)+'|\n'+'\n'.join('| '+' | '.join(str(c).replace('|','／').replace('\n',' ') for c in row)+' |' for row in rows)+'\n'

txt='''# 系统论文重写与统计变更记录

## 1 定位与标题

采用：**证据契约驱动的加速器文档检索增强问答**。

候选：**面向加速器知识服务的可追溯检索增强问答与完整性评测**。

定位为中文核心期刊风格的单栏系统与评测论文。原始详细材料、CSV、SVG/PDF、公式源、历史报告和候选缓存全部只读；没有重新运行模型、追加实验、改动样本或改写测量记录。新版内容均位于 `papers/rag-paper/`，最终 PDF 为 `output/pdf/rag-paper.pdf`。

## 2 Before → After

'''+table(['项','Before','After','位置'],changes)
txt+=f'\n按指定自否定词族 `{pattern}` 对原稿逐行统计，共 {lines} 行、{occurrences} 处匹配。重写后的全部 TeX 为 0 处同词族匹配；这表示改写/删除了旧表达，并把有效边界集中为 §7 的肯定式陈述，而非删去事实。完整禁用词表另由校验脚本检查。\n'
txt+='''
## 3 三条贡献 → 主要证据锚点

'''+table(['贡献或发现','主要锚点','数据来源／重算位置'],[
 ['引用与编码解耦的证据契约','图1','corpus.csv；evidence-snapshot.json；系统与契约源实现'],
 ['异构互补带来2条完整命中','表2','query-ranks-v2.csv；paper_stats.py / methods'],
 ['需求到PDF的可追溯问答链','图2','RAG源码；rag-production-readiness-20261026.json'],
 ['不确定性与配对效应','图3','同一21问数组；paired与methods/*_ci95'],
 ['具体翻转机制','表4','query-ranks-v2.csv；original-query-candidates.json'],
 ['语言切片','表5','benchmark.csv；query-ranks-v2.csv'],
 ['父块与评分片段差异','图4a','rag-stage-two-eight-two-reranking.json'],
 ['多查询成本与负收益','图4b','rag-stage-two-eight-multilingual-retrieval.json / query_candidates'],
 ['服务耗时分布','表6','production-latency-20261026.csv'],
 ['IOC过度完整标记','结果6.6','生产保存答案；冻结字段清单；internal_review'],
 ])
txt+='''
## 4 新增数字的算式、分母与随机性

### 4.1 共同计算约定

全部结果由 `scripts/paper_stats.py` 生成到 `data/paper-statistics.json`，表体由脚本同步生成。`--check` 从输入重新计算并逐字比较结果，同时核对输入哈希。没有复制报告里的旧成对胜负来代替新方案比较。

- 查询顺序：`benchmark.csv` 中21条可回答问题的原始顺序。
- 命中变量：排名非空为1，空为0；倒数排名：有排名取其倒数，否则为0。
- 重采样：`numpy.random.default_rng(20261027).integers(0, 21, size=(1000, 21))`。所有方法和差值共享同一索引矩阵。
- 95%区间：对1,000个重采样均值取 `np.quantile(..., [0.025, 0.975], method="linear")`。
- 确定性统计不使用随机数，seed不适用。表中点估计和区间四舍五入到3位小数；摘要的95.2%、+9.5 pt及2.51 s遵循用户指定精度。

### 4.2 四种方法的Hit@5与MRR@5区间

分母均为21；点估计是21个查询贡献的均值。全部区间使用上述1,000次、seed=20261027的配对重采样。

'''
rows=[]
for m in ['BM25','E5','Qwen3','Dual + reranker']:
 v=S['methods'][m]
 rows.append([m,f"{v['Hit@5']:.3f}",f"[{v['hit_ci95'][0]:.3f}, {v['hit_ci95'][1]:.3f}]",f"{v['MRR@5']:.3f}",f"[{v['mrr_ci95'][0]:.3f}, {v['mrr_ci95'][1]:.3f}]"])
txt+=table(['方法','Hit@5','95%区间','MRR@5','95%区间'],rows)
P=S['paired']
txt+=f'''
### 4.3 E5与重排的配对分析

- 完整命中差值：`(20 - 18) / 21 = {P['hit_difference']:.12f}`，即9.524个百分点；区间 `[{P['hit_difference_ci95'][0]:.3f}, {P['hit_difference_ci95'][1]:.3f}]`。seed=20261027，1,000次。
- MRR差值：逐问题 `rr_reranker - rr_E5` 的均值为 `{P['mrr_difference']:.12f}`，区间 `[{P['mrr_difference_ci95'][0]:.3f}, {P['mrr_difference_ci95'][1]:.3f}]`。相同seed和索引。
- 精确双侧McNemar：正向2、反向0；`min(1, 2 * sum(comb(2,k) for k in range(0+1)) / 2**2) = 0.500`。分母为2个不一致问题，确定性，无seed。
- 翻转：`xfel-normal-energy`、`cryo-interlock`；反向列表为空。共同命中18，共同失败1，来自同一v2逐查询CSV。
- 指定的Stage 2.7报告只包含BGE-small、E5和BGE-base，时间上没有Qwen3或重排方案。故新配对直接从 `query-ranks-v2.csv` 对齐计算；历史报告仅作来源核查，不套用其v1成对统计。

### 4.4 语言分层

英文、中文按问题语言筛选；跨语言按 `language_relation == cross_language` 筛选，是重叠切片。每个值为组内命中数除以组内n，确定性，无seed。

'''
rows=[]
for k,title in [('en','英文'),('zh','中文'),('cross_language','跨语言目标')]:
 g=S['language'][k];rows.append([title,g['n']]+[f"{g['methods'][m]['hits']}/{g['n']} = {g['methods'][m]['Hit@5']:.3f}" for m in ['BM25','E5','Qwen3','Dual + reranker']])
txt+=table(['切片','n','BM25','E5','Qwen3','重排'],rows)
txt+='''
### 4.5 延迟分布与阶段占比

各组从保存的请求行筛选。均值使用算术均值；P50/P95使用 `np.quantile(t, 0.5/0.95, method="linear")`；max取最大值。某阶段占比为该阶段耗时之和除以总耗时之和，剩余部分为编排开销。没有随机性。

'''
rows=[]
for group in ['all','answerable','negative']:
 v=S['latency'][group];rows.append([group,v['n']]+[f'{v[k]:.3f}' for k in ['mean','p50','p95','max']])
txt+=table(['组','n','均值/s','P50/s','P95/s','max/s'],rows)
rows=[]
for group in ['all','answerable','negative']:
 v=S['latency'][group]['component_shares'];rows.append([group]+[f'{100*v[k]:.3f}%' for k in ['retrieval_seconds','rerank_seconds','generation_seconds','orchestration']])
txt+=table(['组','稠密检索','重排','生成流程','编排余量'],rows)
txt+='''
### 4.6 多查询调用成本与收益

每条问题的调用数是保存的 `query_candidates[query]` 列表长度；它包括原始查询和去重后的改写。全32问求和为91，可回答21问求和为69。调用倍率分别为 `91/32=2.84375` 和 `69/21=3.285714...`，不是示例中的固定3倍。每模型的调用数分布为：1次的1问、2次的11问、3次的12问、4次的8问；这些数由列表长度的Counter计算。

'''
rows=[]
for m in ['E5','Qwen3']:
 c=S['multi_query_cost'][m];rows.append([m,c['multi_query_calls'],f"{c['call_multiplier']:.3f}",f"{c['hit_delta']*100:.3f}",f"{c['mrr_delta']:.3f}",f"{c['measured_evaluation_seconds']:.3f}",f"{c['measured_evaluation_seconds_per_query']:.3f}"])
txt+=table(['模型','32问调用数','倍率','Hit差/百分点','MRR差','查询评测总耗时/s','总耗时/32'],rows)
txt+='''
改写规划耗时与同环境单查询延迟没有完整记录，脚本将两项显式保存为null。报告已有的2.004 s单模型评测来自不同阶段和搜索路径，故不用于估计同条件延迟增量。没有补算或估算规划耗时，也没有写成因果加速比。

### 4.7 语料聚合、互补性与IOC字段反例

- 表1按 `document_id` 前缀分组，文档数去重计数，页数和规范块/合格块逐行求和。总数仍为13、2,178、4,537、4,532。
- 四种互补情况对E5/Qwen3的命中布尔数组做交集及差集：共同15、E5独有3、Qwen3独有2、共同失败1。
- 父块/评分片段20/19等覆盖数直接读入历史重排JSON，不是新增模型推理。
- IOC是预先指定的已知反例。脚本保存原答案，并按启动时间、CA server端口、CA repeater端口的中英文别名检查保存答案中的字段缺失，得到3个缺项。20条answered由冻结请求状态计数；至少1/20的已知反例是确定性的观察下界，不是人工盲审发生率估计。
- 内部32/33沿用原记录；没有把其改写为答案准确率，也没有从单个反例推出总体系统性偏差。
- 失败轨迹里的排名、物理页、分数和原文均逐字段复制自输入缓存，数据节点为 `failures`，无随机性和额外算式。`matched_candidate_ranks_by_group`使用同一NFKC/空白/断词规范化，对全部前10父块逐一匹配冻结三元组；两条新增问题在E5候选中各组匹配列表均为空，而Qwen3的匹配排名分别为XFEL组[2]、低温三组[5]/[1]/[1]。该计算直接验证了候选补充机制，无seed。

## 5 未生成的统计与证据决策

没有规划端到端延迟、同环境多查询增量、独立保留集或人工盲审结果，所以相应数字保持缺失。所有限制在论文§7集中处理；正文把已完成的控制实验、负结果和失败机制改写为明确发现。候选缓存包含32问，其中失败分析按冻结集ID选择3个已保存案例；没有扩大为新实验。

## 6 参考文献与版式

39条BibTeX记录均被正文引用，无重复key、无重复DOI、无未引用条目。出版社/Crossref/arXiv元数据保存在 `data/reference-metadata/` 与 `data/reference-verification.json`；JACoW、DESY和《核技术》的部分DOI由出版社原始PDF或正式记录验证，不把Crossref返回404视为文献不存在。EPICS开发文档使用官方URL和已登记本地PDF核对。

图形采用Noto Sans CJK SC、180 mm、至少8 pt，并提供PDF/SVG/600 dpi PNG。Noto的CFF轮廓以矢量Type 3字形嵌入图PDF，以消除错误的TrueType包装；图中没有位图字形。正文公式是原生XeTeX数学字体，PDF不包含公式PNG。表格均为三线表；点估计及新增统计按3位小数显示，整数计数与摘要约定精度保留。

## 7 命令与实际输出

见随附 `qa/self-check.txt`。该文件保存禁用词grep、统计重算、LaTeX编译、引用/标签与页数检查的原始输出。系统未安装latexmk/XeLaTeX，按要求改用官方Tectonic 0.15.0；经终端缓存完成真实TeX、BibTeX和xdvipdfmx编译，不采用ReportLab回退。应用内编译器使用另一套独立缓存，其自动下载被当前网络设置阻断；终端已下载的标准宏包与完整编译日志保留为实际交付依据。
'''
receipt=OUT/'qa/self-check.txt'
compatibility=OUT/'qa/pdfjs-font-compatibility.json'
if compatibility.exists():
 txt+='''
## 8 PDF 预览兼容性修复

用户反馈内置预览仅显示拉丁字符、数字与公式。检查发现，3个Fandol字体子集已经嵌入，但缺少ToUnicode，Adobe/GB1字形到Unicode的映射依赖查看器外部资源。PDF.js 5.6.205关闭外部CMap资源时复现同样症状；补入字体映射后，首页可提取中文由0变为1,151字，全文可提取中文由265变为6,881字。原文件中仍可提取的265字来自自带映射的图形字体。

修复由 `scripts/embed_cjk_map.py` 实现，构建脚本自动执行；`fonts/Adobe-GB1-UCS2` 保留Adobe许可。字体程序、内容流与页面尺寸保持不变。MuPDF对12页的修复前后渲染逐像素一致；PDF.js无外部CMap的修复版首页、架构/公式、状态图及结果页已视觉检查。独立回执为 `qa/pdfjs-font-compatibility.json` 与 `qa/font-fix-pixel-comparison.json`。应用相关公开复现记录：https://github.com/openai/codex/issues/51051。

交付PDF及源码包已同步更新，全文数值和统计脚本保持原值。
'''
if receipt.exists():
 txt+='\n以下为上述命令的实际回执；grep 的退出码 1 表示零匹配。\n\n```text\n'+receipt.read_text().rstrip()+'\n```\n'
(OUT/'CHANGES.md').write_text(txt)
print(f'CHANGES.md: {len(changes)} before/after groups; {lines} source lines / {occurrences} expressions replaced.')
