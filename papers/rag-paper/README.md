# 证据契约驱动的加速器文档检索增强问答

该目录保存中文系统与评测论文的完整 LaTeX 工程。正文为 8 页，参考文献和附录另列。正式 PDF 位于 仓库根目录的 `output/pdf/rag-paper.pdf`。

## 文件

- `main.tex`、`sections/*.tex`：主文件和 8 节正文、摘要及 2 个附录。
- `refs.bib`：39 条已在正文引用的真实参考文献。
- `figures/`：4 张中文图，宽 180 mm，标签至少 8 pt；PDF、SVG 和 600 dpi PNG。
- `tables/`：由统计脚本生成的 LaTeX 表体。
- `data/paper-statistics.json`：新增统计、逐案候选原文、输入 SHA-256。
- `data/reference-verification.json`：出版社、Crossref 和 arXiv 核验记录。
- `CHANGES.md`：23 组 before→after、主张映射、全部新增统计的计算约定。
- `qa/self-check.txt`、`qa/validation.json`：命令回执与最终检查结果。

## 编译

工程中的图、表和 BibTeX 均为本地文件。已安装 XeLaTeX 和 latexmk 时，在本目录执行：

```bash
latexmk -xelatex main.tex
```

本次环境使用官方 Tectonic 0.15.0 完成原生 LaTeX、BibTeX 与 xdvipdfmx 编译。也可执行：

```bash
tectonic --keep-logs --keep-intermediates --reruns 2 main.tex
```

编译器需要标准中文 LaTeX 宏包及 Fandol 字体。首次使用 Tectonic 时需要下载其标准宏包缓存；此后可离线编译。`scripts/build_paper.sh` 自动选择 latexmk 或 Tectonic，并复制到最终 PDF 路径。可用环境变量 `TECTONIC_BIN` 指定编译器。

构建脚本在编译后执行 `scripts/embed_cjk_map.py`，为 Fandol 字体嵌入 Adobe-GB1 的 Unicode 映射，解决部分 PDF.js 预览器省略中文的问题。此步骤依赖 `pypdf`；可用 `PYTHON_BIN` 指定 Python。手动执行上述编译命令后，也须执行 `python3 scripts/embed_cjk_map.py main.pdf`。映射文件及 Adobe 许可保存在 `fonts/Adobe-GB1-UCS2`，不依赖预览器下载字体资源。

## 重算统计与图

以下命令从项目根目录运行。统计重算需要保留原项目的只读输入：`papers/rag-thesis/data/`、对应 `reports/rag-*.json`、冻结评测文件及原始候选缓存；这些输入没有为论文改写而改变。单独编译论文不依赖这些外部数据。

```bash
python3 papers/rag-paper/scripts/paper_stats.py --check
python3 papers/rag-paper/scripts/draw_figures.py
python3 papers/rag-paper/scripts/check_paper.py
```

配对 bootstrap 重复 1,000 次，固定 PCG64 seed 为 20261027。图使用 Noto Sans CJK SC；Python 绘图脚本依赖 NumPy、Matplotlib、Pillow 和 fontTools。新增统计没有增加模型推理、人工盲审或测试集；所有未实施的评价在论文第 7 节集中说明。


## 仓库整理说明

2026 年 10 月 28 日整理保留了可编辑正文、公式源码、必要渲染资产、数据、参考文献核验记录、构建脚本和最终 PDF。逐页预览 PNG、编译中间文件及重复归档已移出版本库；生成新预览或编译时会重新产生。历史实验结论未因目录整理而更新。
