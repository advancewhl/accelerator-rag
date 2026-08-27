# Accelerator RAG

面向 EPICS、HLA、束流诊断和加速器物理资料的 RAG 检索学习项目。

项目目前完成到 Day 8，已经建立从文本块、Embedding、向量存储到
检索评测的最小闭环，并完成首批真实加速器语料的登记与分类。当前重点是
检索层和语料治理，还未包含 LLM 答案生成。

## 已实现功能

- 使用 `BAAI/bge-small-zh-v1.5` 生成中文文本向量；
- 使用 NumPy 实现内存语义检索；
- 使用 Jieba 和 BM25 实现关键词检索，并保留 EPICS PV 名等技术词；
- 使用 Qdrant 持久化向量，支持写入、查询和删除；
- 使用固定问题和 Ground Truth 对 Dense、BM25 检索进行对比评测；
- 使用 registry 管理真实文档的主题、类型、语言、版本和状态；
- 自动核对 registry 与 `data/raw`，并输出 corpus inventory；
- 提供单元测试、演示脚本和基线分析报告。

## 技术栈

- Python 3.11
- NumPy
- Sentence Transformers
- Jieba
- Qdrant
- Pytest
- Ruff

## 项目结构

```text
accelerator-rag/
├── config/                  # 应用配置
├── data/                    # 示例语料与评测问题
├── docs/                    # 学习记录和技术说明
├── reports/                 # 检索基线报告
├── scripts/                 # Day 4 至 Day 7 演示脚本
├── src/accelerator_rag/
│   ├── evaluation/          # Ground Truth 与检索评测
│   ├── corpus/              # 语料分类、登记与一致性校验
│   ├── retrieval/           # Dense、BM25 和 Qdrant 检索器
│   ├── storage/             # Qdrant 向量存储封装
│   ├── config.py
│   ├── embedding.py
│   └── main.py
└── tests/                   # 单元测试
```

## 环境安装

使用 Conda 创建并激活环境：

```bash
conda env create -f environment.yml
conda activate accelerator-rag
python -m pip install -e ".[dev]"
```

如果环境已经存在：

```bash
conda activate accelerator-rag
python -m pip install -e ".[dev]"
```

首次运行真实 Embedding 演示时，Sentence Transformers 可能需要下载
BGE 模型。

## 基础命令

检查配置和应用入口：

```bash
accelerator-rag
```

运行测试和静态检查：

```bash
pytest -q
ruff check .
```

## 检索演示

内存语义检索：

```bash
python scripts/day4_semantic_search_demo.py
```

BM25 与 Dense 检索对比：

```bash
python scripts/day5_bm25_vs_semantic_demo.py
```

需要 Qdrant 的演示先启动服务：

```bash
docker compose up -d
docker compose ps
```

然后运行：

```bash
python scripts/day6_qdrant_smoke.py
python scripts/day6_qdrant_bge_demo.py
python scripts/day7_retrieval_baseline.py
```

Qdrant 默认通过 `http://localhost:6333` 提供 HTTP API，数据保存在
Docker Volume `qdrant_storage` 中。

## Day 7 基线

当前示例语料包含 12 个文本块，评测集包含 20 个问题，其中 19 个问题
参与计分。在 `Top-K=3` 条件下，已保存的基线结果为：

| 检索器 | Top-1 | Top-3 |
| --- | ---: | ---: |
| Dense（BGE + Qdrant） | 19/19 | 19/19 |
| BM25 | 18/19 | 19/19 |

详细结果见：

- [Day 7 检索报告](reports/day7_baseline.md)
- [Day 7 结果分析](reports/day7_analysis.md)
- [Day 6 Qdrant 说明](docs/day06_qdrant.md)

## Day 8 语料登记

首批 13 份 PDF 放在 `data/raw`，登记信息保存在
`data/documents/registry.json`。原始资料不直接提交到 Git，registry 和分类规则
需要纳入版本管理。

运行登记表与原始文件一致性检查：

```bash
python scripts/day8_corpus_inventory.py
```

命令会列出每份文档，并统计类别、主题、格式、语言和状态；如果发现漏登记或
登记文件缺失，将返回非零退出码。

详细规则与本次结果见 [Day 8 语料管理报告](reports/day8_corpus_inventory.md)。

## 当前边界

这是一个检索层原型，而不是完整的问答应用。目前尚未实现：

- PDF 等真实文档的解析与自动切块；
- Dense 与 BM25 的混合召回和重排序；
- 无答案检测与证据充分性判断；
- LLM 上下文组装、答案生成和来源引用；
- 面向用户的 API 或界面。

当前评测集规模较小，且问题与示例语料的词汇重合较高，因此基线结果
主要用于验证检索链路和后续实验回归，不代表真实加速器文档上的最终性能。
