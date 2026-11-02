# K6 生产切换记录

日期：2026-11-02　｜　新生产：`kb-2.0.0-rc.1`（`kb2-prod-20261102`）
状态：**已切换并验证健康**。旧生产保留为回滚容器。人工语义验收与观察期仍未完成，manifest 仍为 `candidate`。

## 1. 切换结果

| 项目 | 切换前 | 切换后 |
| --- | --- | --- |
| 8003 容器 | `accelerator-rag`（发布 `md-20261030`） | `accelerator-rag`（发布 `kb-2.0.0-rc.1`） |
| 旧容器 | — | `accelerator-rag-md-rollback-20261102`（已停止，保留） |
| 候选容器 | `kb2-candidate`（8013，已删除） | — |
| GPU | GPU2 | GPU2 |
| 发布目录 | `/opt/accelerator-rag-releases/md-20261030` | `/opt/accelerator-rag-releases/kb-2.0.0-rc.1` |

新容器参数：`--network host --ipc host --restart unless-stopped`，只读挂载发布目录，`/workspace/tmp` 单独可写，`--env-file /opt/rag-production.env`，健康检查 `GET /health`。

## 2. 切换过程

1. 预检：旧 8003 健康；候选 8013 健康；GPU2 显存充足；回滚容器名未被占用。
2. 停止旧 `accelerator-rag`，重命名为 `accelerator-rag-md-rollback-20261102`。
3. 启动新 `accelerator-rag`（8003 / GPU2）。
4. **首次启动失败**：`RuntimeError: Storage folder .../kb2-prod-20261102/e5/qdrant is already accessed by another instance of Qdrant client`。原因是 8013 候选容器仍持有同一份本地 Qdrant 索引的锁。
5. 停止并删除 `kb2-candidate`，删除失败的新容器后重启。第二次启动成功，约 60 s 内转为 `healthy`。

## 3. 切换后验证

```json
GET /health
{"status":"ok"}

GET /v1/rag/releases/current
{"release_id":"kb-2.0.0-rc.1","build_id":"unknown","document_count":207,
 "revision_count":207,"family_count":72,"indexed_section_count":8431,
 "read_only_attachment_count":0,"source":"runtime-config"}

GET /v1/rag/documents
{"document_count":207,"indexed_section_count":8431, ...}
```

冒烟题（旧 50 题中的 P50-002，英文）：

> What happens to Channel Access client connections when an IOC server crashes and restarts?

结果：HTTP 200，`answered`，2 条引用；回答包含“客户端在服务器重启后自动重建通信”，与题集 gold answer 一致。

`build_id` 仍为 `unknown`：运行时只从配置读取 `release_id`，尚未接入 release manifest 的 `build_id`。这是已知缺口，不影响检索，但发布身份展示不完整。

### 3.1 新格式与版本范围

- **DOCX 检索**：问题“SHINE 快联锁对单节点和节点间的响应时间分别有什么要求？”返回 200 `answered`，引用 `shine-prototype-fast-interlock-acceptance-rev-a0ac5b09`，定位 `paragraph-22`，原文为“单节点…小于10 μs；节点间…小于100 μs”。新格式文档在生产可检索、可引用。
- **版本范围**：同一问题加 `scope.mode=version`、`family_ids=["shine-accelerator-fast-interlock-2024"]`、`release_id=kb-2.0.0-rc.1`，返回 200 `answered`，引用只来自该 family，未混入其他版本。K3 的服务端范围过滤在生产生效。

## 4. 回滚

旧容器与旧发布目录均保留，未覆盖：`accelerator-rag-md-rollback-20261102` 仍为原镜像、GPU2、`unless-stopped`，挂载 `/opt/accelerator-rag-releases/md-20261030`（3.6 GB，含原索引与请求 trace）。

```bash
docker stop accelerator-rag
docker rm accelerator-rag
docker rename accelerator-rag-md-rollback-20261102 accelerator-rag
docker start accelerator-rag
curl -fsS http://127.0.0.1:8003/health
```

注意：新旧容器使用 host 网络且同为 8003，必须先停新容器再启动旧容器。旧索引与旧请求 trace 均未修改。

**回滚演练尚未执行**（需要短暂停服），只验证了回滚目标存在且镜像一致。

## 5. 切换后仍需完成

- 人工语义评分（旧 50 题 + 新 60 题；至少一位业务审核人）。manifest 保持 `candidate` 直到人工接受。
- 回滚演练计时与记录。
- K7 观察期 2 个工作日，记录接口失败、超时、引用失效和版本误用。
- P95 26.6 s vs 旧 19.5 s（1.36×）的瓶颈分析。
- OCR 关键参数逐页人工复核；当前 OCR 文本不能独立支撑精确数值结论。
