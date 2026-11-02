# Runbooks

本目录保存 RAG 数据导入、检索、评测与故障处理手册。

- [独立 RAG 生产服务](rag-production.md)：HTTP、PDF、模型配置及本机常驻转发。
- [Markdown 双路索引发布](rag-markdown-release.md)：当前发布目录、GPU 连接方式、索引核对及旧容器回滚。
- [RAG 文件导航](../rag/README.md)：当前实现与历史记录。
- [Knowledge Retrieval](knowledge-retrieval.md)：PDF 数据入口、清洗、BM25 和 Dense 查询。
- [Corpus baseline](corpus-baseline.md)：全量导入、资格策略和证据级基线。
- [Dense passage](dense-passages.md)：token 预算、parent 聚合和固定查询比较。
- [Embedding comparison](embedding-comparison.md)：模型契约、离线指纹与受控比较。
- [Evidence audit](evidence-audit.md)：人工审核、重判和索引契约。
- [Dense reranking](dense-reranking.md)：Stage 2.8 至 2.8.2 的实验入口、结果与回滚。
- [RAG 知识入库、验证与回滚](rag-ingestion-verification-rollback.md)：准备文档、检查解析、构建候选索引、验证回答、切换与回滚；包含 Markdown 操作流程。
