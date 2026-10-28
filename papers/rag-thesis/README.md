# RAG 论文章节材料

资料截止：2026 年 10 月 27 日。正文是中文详细稿，面向最终论文的独立章节。本文依据本地项目记录整理，没有新增模型实验，也没有将本地语料发布到外部服务。

## 阅读入口

- 审阅 PDF：项目根目录下的 `output/pdf/rag-thesis-chapter.pdf`。
- 可编辑正文：`rag-chapter.md`。包含方法、实验、讨论、参考文献及 3 个附录。
- 独立图：`figures/fig01` 至 `figures/fig08`，每图提供 SVG、PDF 和 600 dpi PNG。
- 图表数据：`data/`。包括 11 种方法的指标、231 条问题排名、32 条服务耗时、语料清单及原始问题清单。
- 公式：`equations/`。正文中的全部数学公式均保留有效 LaTeX 源码，同时保存渲染文件。
- 来源指纹：`data/source-manifest.json`。保存引用的报告、评测文件和相关实现的 SHA-256。

## 合并论文时的处理

正文按独立章节编写。合并时统一章节号、图号、表号和参考文献编号，并按学校或期刊模板调整版式。背景中的方法来源使用公开文献编号，实验事实使用 E 编号；附录 A 提供 E 编号与本地文件的对应关系。正式论文可将本地证据映射移入补充材料。

全部图宽为 180 mm。优先使用 SVG 或 PDF 插入正式论文；PNG 适合预览或不支持矢量的工具。字体使用 Arial 兼容的 Liberation Sans，基本字号为 7 pt，面板编号为 8 pt。图形参考 [Nature 图形规范](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)，采用克制配色、无背景网格和直接数值标注。没有使用期刊标识，也不声称已经满足任一具体期刊的全部投稿要求。

## 重要的评价边界

1. 最终检索表统一采用 `evidence-contract-v2`；早期 passage A/B 使用 v1。标注扩充后的分数变化没有写成算法提升。
2. 检索 Hit@5 为 20/21；实际评分片段完整覆盖为 19/21。两者不等价。
3. 2026 年 10 月 26 日完整问答验收使用 `qwen3.8-Flash-Next`。`ds-1017` 仅有后续代表性验证，不能沿用旧模型的全量指标。
4. 生产报告的 `answered` 和 32/33 内部要求支持，不是独立评审的正确率。IOC 启动信息答案缺少冻结要求字段却标为完整；正文第 7.2 节及附录 C 已给出具体反例。
5. 21 条可回答问题和 11 条负例已经用于开发与选择方案；没有独立保留测试。当前结果属于固定小样本诊断。

本次没有修改生成或检索实现，没有重建索引，没有执行 Git 提交或推送。后续修复应单独进行，并在统一评价口径下重新验证。

## 从历史证据重建

在项目根目录执行：

```bash
python3 papers/rag-thesis/scripts/export_evidence.py
python3 papers/rag-thesis/scripts/draw_figures.py
python3 papers/rag-thesis/scripts/build_pdf.py
```

`export_evidence.py` 使用 Python 标准库。它重新执行规范化子串匹配与完整证据组判断，逐项核对报告中的排名及汇总指标。它不会加载模型、访问网络或写入索引。

绘图依赖 NumPy、Matplotlib、Pillow，以及本机 Liberation 字体。PDF 构建另需 ReportLab 和 fontTools。当前环境使用 `python3` 中的 Matplotlib；`build_pdf.py` 在缺少 ReportLab 时使用已安装的 Codex 工作区依赖路径。迁移到其它机器时，应在自己的 Python 环境安装相应依赖，并调整脚本中的字体路径。

真实模型实验需要原始 PDF、冻结权重、签名索引和对应软件环境。论文材料包含重新制图所需的数据快照，没有复制原始 PDF、权重或索引。完整命令及环境条件见现有运行手册。

## 验证记录

本次核验范围及渲染检查结果保存于 `qa/validation.json`。PDF 已逐页渲染，并检查表格、图、页边界和公式。公式另由本地 KaTeX 校验语法。渲染图片是审阅用中间产物，不是额外实验数据。


## 仓库整理说明

2026 年 10 月 28 日整理保留了可编辑正文、公式源码、必要渲染资产、数据、参考文献核验记录、构建脚本和最终 PDF。逐页预览 PNG、编译中间文件及重复归档已移出版本库；生成新预览或编译时会重新产生。历史实验结论未因目录整理而更新。
