# Day 6 - Qdrant 核心概念与向量存储

## 1. 学习目标

今天的目标是把 Day 4 中基于 NumPy 的内存向量检索替换为 Qdrant，完成一个可持久化的语义检索闭环：

```text
DocumentChunk -> Embedding -> Qdrant Point
query -> Embedding -> Qdrant Top-K -> SearchResult
```

完成后应能：

- 理解 Collection、Point、Vector、Payload 和 Distance 等概念；
- 创建 Collection，并写入、查询和删除 Point；
- 使用真实 BGE 模型生成向量；
- 通过 `QdrantVectorStore` 隔离 Qdrant 的存储细节；
- 通过 `QdrantSemanticRetriever` 完成文本到检索结果的转换。

## 2. 核心概念

### Collection

Collection 类似关系数据库中的表，是一组使用统一向量配置的 Points。同一个 Collection 中的向量必须符合创建时声明的维数和距离算法。

本项目默认使用的 Collection 名称来自 `config/settings.json`；Day 6 的 BGE 演示会在其后附加 `_day6_demo`，避免影响正式数据。

### Point

Point 是 Qdrant 中最基本的存储单元，由以下三部分组成：

- `id`：Point 的唯一标识；
- `vector`：用于相似度计算的向量；
- `payload`：与向量关联的业务数据。

本项目不会直接把任意字符串 `chunk_id` 作为 Point ID，而是使用 UUID v5 将其稳定映射为 Qdrant 支持的 UUID。相同的 `chunk_id` 总会得到相同的 Point ID，因此重复 upsert 会更新同一个 Point，而不会产生重复数据。

### Vector

Vector 是 Embedding 模型产生的浮点数数组。Collection 的 `vector_size` 必须与模型输出维数一致。

Day 6 的 BGE 演示通过一次探测调用自动读取模型输出维数，当前 `BgeSmallZhEmbedder` 的输出为 512 维。

### Payload

Payload 是与向量绑定的结构化业务数据。本项目写入以下字段：

```json
{
  "chunk_id": "pv",
  "title": "PV",
  "text": "EPICS PV 示例文本。",
  "metadata": {
    "system": "EPICS"
  }
}
```

查询命中后，`QdrantVectorStore` 使用 Payload 还原 `DocumentChunk`，再包装成统一的 `SearchResult`。

### Distance

Distance 决定两个向量如何比较。本项目使用 Cosine（余弦相似度），它更关注向量方向而不是长度，常用于文本语义检索。

分数越高，表示向量方向越接近；但分数只适合在同一模型、同一 Collection 和同一次检索配置下比较，不应直接将它理解为概率。

### Top-K

Top-K 表示返回与 query vector 最相关的前 K 个 Points。`top_k` 必须大于 0；当 Collection 中的 Point 数少于 K 时，只返回实际存在的结果。

## 3. Day 4 与 Day 6 的区别

Day 4 的检索流程：

```text
文本 -> Embedding -> NumPy 数组 -> 相似度计算 -> Top-K
```

Day 6 的检索流程：

```text
文本 -> Embedding -> Qdrant 持久化与索引
查询 -> Embedding -> Qdrant 相似度查询 -> Top-K
```

NumPy 方案适合学习算法和小规模原型，但数据通常只存在于当前进程中。Qdrant 提供持久化、向量索引、Payload、过滤、更新和删除能力，更适合作为 RAG 系统的向量存储层。

需要注意：Qdrant 不负责生成 Embedding。写入向量和查询向量必须由兼容的 Embedding 模型产生。

## 4. 项目实现

### 组件职责

`BgeSmallZhEmbedder`：

```text
text -> vector
```

`QdrantVectorStore`：

- 确保 Collection 存在；
- 校验向量形状和维数；
- 将 `DocumentChunk + vector` 转换为 Point 并 upsert；
- 执行 Top-K 查询，并将 Payload 还原为 `SearchResult`；
- 根据业务 `chunk_id` 删除 Point。

`QdrantSemanticRetriever`：

- 索引时拼接 `title` 和 `text`，批量生成文档向量；
- 查询时生成 query vector；
- 调用 Vector Store，向上层返回统一的 `SearchResult`。

### 索引流程

```text
DocumentChunk 列表
  -> title + "\n" + text
  -> embed_documents
  -> ensure_collection
  -> upsert_chunks
  -> Qdrant Points
```

### 查询流程

```text
query
  -> embed_query
  -> QdrantVectorStore.search
  -> query_points
  -> Payload 反序列化
  -> list[SearchResult]
```

### 输入校验

当前实现会主动拒绝以下无效输入：

- 空 Collection 名称或非正数 `vector_size`；
- 空 chunks；
- chunks 数量与向量行数不一致；
- 文档向量不是二维矩阵；
- query vector 不是一维向量；
- 向量维数与 Collection 配置不一致；
- 空查询或非正数 `top_k`；
- 查询结果中缺失或类型错误的 Payload 字段。

## 5. 运行准备

进入项目目录并激活环境：

```bash
conda activate accelerator-rag
```

启动 Qdrant：

```bash
docker compose up -d
docker compose ps
```

Qdrant 默认使用以下端口：

- `6333`：HTTP API，本项目通过该端口连接；
- `6334`：gRPC API。

连接地址和 Collection 名称配置在 `config/settings.json` 中。

## 6. 测试记录

以下结果于 2026-08-18 在仓库当前代码上实测。

### Docker

命令：

```bash
docker compose ps
```

结果：

```text
NAME                     IMAGE                   SERVICE   STATUS
accelerator-rag-qdrant   qdrant/qdrant:v1.18.1  qdrant    Up
```

容器正常运行，宿主机的 `6333` 和 `6334` 端口已映射到容器。

### Smoke test

命令：

```bash
python scripts/day6_qdrant_smoke.py
```

该脚本使用 4 维手工向量验证创建 Collection、upsert、Top-K 查询和删除。它会先删除同名测试 Collection，以保证每次执行结果一致。

结果：

```text
Collection 创建成功
Points 写入成功

查询结果
1 1 1.0 {'title': 'EPICS', 'system': 'EPICS'}
2 2 0.9701425 {'title': 'IOC', 'system': 'EPICS'}

Point 1 删除成功

删除后的查询结果
1 2 0.9701425 {'title': 'IOC', 'system': 'EPICS'}
```

查询向量与 Point 1 完全一致，因此其余弦分数为 1.0；删除 Point 1 后只剩 Point 2。

### BGE + Qdrant

命令：

```bash
python scripts/day6_qdrant_bge_demo.py
```

首次运行可能需要下载 BGE 模型。演示检测到 Embedding 维数为 512，三组查询的第一名如下：

| Query | Top-1 | Score |
| --- | --- | ---: |
| `EPICS IOC PV` | EPICS | 0.7354 |
| `束测 BPM` | BPM | 0.7117 |
| `MBA 光源物理` | MBA | 0.7566 |

三组查询均把对应主题排在第一位，说明真实 Embedding、Qdrant 写入和语义查询链路正常。浮点分数可能因模型版本或运行环境产生轻微差异，应重点检查排序是否符合预期。

### pytest

命令：

```bash
pytest -q
```

结果：

```text
............                                                             [100%]
12 passed in 1.11s
```

其中 Qdrant 相关单元测试使用 `QdrantClient(":memory:")`，不依赖 Docker，覆盖了索引与查询、删除以及非法 `top_k`。其余两个演示脚本需要正在运行的 Qdrant 服务。

## 7. 今日问题与排查

### `pytest: command not found`

原因：命令在 Conda 的 base 环境中执行，项目依赖安装在 `accelerator-rag` 环境中。

处理：

```bash
conda activate accelerator-rag
pytest -q
```

也可以不切换当前 shell，直接执行：

```bash
conda run -n accelerator-rag pytest -q
```

### 无法连接 Qdrant

先检查容器和地址：

```bash
docker compose ps
curl http://localhost:6333/healthz
```

如果容器未启动，执行 `docker compose up -d`；如果项目配置发生变化，确认 `config/settings.json` 中的 `qdrant_url` 与端口映射一致。

### 向量维数不一致

Collection 创建后，其向量维数是固定的。更换 Embedding 模型可能改变输出维数，此时不能继续向旧 Collection 写入新维度向量。

开发阶段可以删除并重建演示 Collection；生产环境应创建新 Collection，并规划数据迁移和别名切换，避免直接破坏现有索引。

### 模型与向量不一致

索引文档和查询必须使用同一个 Embedding 模型及兼容的预处理方式。否则即使维数相同，两个向量空间也可能不兼容，检索结果会失真。

## 8. 今日结论

Qdrant 不负责生成 Embedding：

```text
Embedding 模型：text -> vector
```

Qdrant 负责向量数据的生命周期：

```text
vector + payload -> 保存、索引、查询、更新、删除
```

Retriever 负责组织完整的检索流程：

```text
query -> embedding -> Top-K SearchResult
```

通过职责拆分，上层检索逻辑不需要了解 Point 构造、UUID 映射和 Payload 反序列化等 Qdrant 细节，后续可以继续加入 Payload 过滤、批量索引、Collection 迁移以及真实文档数据。
