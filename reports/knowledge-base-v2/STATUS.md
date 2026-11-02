# kb-2.0.0 阶段状态

更新：2026-11-02　｜　目标：`kb-2.0.0`（候选，尚未发布）

| 阶段 | 状态 | 已完成 | 未完成 / 阻塞 |
| --- | --- | --- | --- |
| K0 基线与范围 | 本地完成，生产待核对 | 代码/测试/环境基线、旧库 17 份迁移、218 文件路径核对 | 生产实际运行版本、原文与索引核对需授权 |
| K1 元数据与版本 | 本地完成 | Schema v2、五类身份、状态规则、统一 IR、v2 切块、旧库迁移、218 条处置合并、21 个族、6 项冲突 | release manifest、责任人确认 |
| K2 解析与样本 | 全批预跑完成 | DOCX/PPTX/DOC/表格解析器；190 份公开候选：159 成功、16 待 OCR、15 DOC 环境失败；3,844 父块、3,671 可索引；V6/控制章/PPTX/XLSX 专项验证 | OCR、DOC 转换环境、人工内容抽查 |
| K3 版本检索与阅读 | 代码完成，生产待验证 | `RetrievalScope` 贯穿 BM25/双路 dense/同页/重排/补检索；API/目录/发布身份端点；365 测试通过（当时） | `compare` 未实现、release manifest 未接入、无生产索引验证 |
| K4 全批治理与构建 | **生产候选已构建** | 207 公开修订全部解析（含 15 DOC 转换、16 扫描件 OCR）；8,622 父块、8,431 可索引；E5 10,608 / Qwen3 8,431 points，两路哈希一致；候选 8013 健康 | 正式 K6 切换需明确授权；回滚演练未做 |
| K5 验收与修复 | 工程回归完成，语义评分未做 | 旧 50 题：候选 49/50 成功（唯一 502 为旧库既有）、45 answered / 4 partial、引用定位完整、无受限命中；P95 26.6 s vs 19.5 s | 人工语义评分、新 60 题冻结、版本/边界裁决、回滚演练 |
| K6 生产上线 | **已切换** | 2026-11-02 8003 切到 `kb-2.0.0-rc.1`；健康、207 文档/8,431 段、冒烟题 200 answered；旧容器保留为 `accelerator-rag-md-rollback-20261102` | manifest 仍为 candidate；回滚演练未做；人工语义验收未做 |
| K7 观察与交接 | **待开始（2 个工作日）** | 观察清单已列 | 记录接口失败、超时、引用失效、版本误用；依赖业务使用 |

最终本地测试：**454 passed, 2 skipped**（skip 为真实 DOC 转换/OCR 环境缺失）。

## 当前可复现命令

```bash
/home/whloong/miniconda3/envs/accelerator-rag/bin/python -m pytest -q
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/migrate_registry_v2.py
/home/whloong/miniconda3/envs/accelerator-rag/bin/python scripts/kb2_sample_build.py
```

## 不得宣称完成的事项

- 未做 OCR，不能宣称 17 份扫描件已可检索。
- 未解析全批 218 个文件，不能宣称资料已入库。
- 未构建双路索引，不能宣称候选可问答。
- 未做人工语义评分，不能宣称准确率。
- 未连接生产、未切换入口，不能宣称 `kb-2.0.0` 已上线。
