# 独立 RAG 部署与使用

## 运行环境

服务面向组内加速器与控制工程人员。网页、RAG API、文档引用与 PDF 查看器由同一个进程提供。每次提问独立处理，不把页面历史拼接到后续问题中。

- GPU 主机：`10.101.9.190`。
- 稳定目录：`/opt/accelerator-rag`。
- 容器：`accelerator-rag`。
- 运行镜像：`accelerator-rag-runtime:20261026`。
- Web 与 API：`http://10.101.9.190:8003/`。
- 模型：`ds-1017`，同机默认地址为 `http://127.0.0.1:8000/v1`。

本服务供受信任的组内网络使用。浏览器只访问 RAG API；模型凭据与索引路径留在服务器。服务不读取实时控制数据，也不调用 Agent 或 Waveform。

2026 年 10 月 28 日起，问答使用需求约束的证据闭环：先拆题，再按子需求进行 BM25 与双路语义召回，执行覆盖、冲突和证据预算检查，缺项时定向补检索。实现与边界见 [证据闭环设计](../architecture/rag-evidence-workflow.md)。

## 启动与检查

启动前读取 `nvidia-smi`、`docker ps` 和监听端口。确认选定 GPU 的显存余量，不停止其它服务。2026 年 10 月 26 日部署使用 GPU 2；该选择不代表后续时刻仍有相同余量。

凭据放在仓库外、权限为 `600` 的环境文件中。当前主机使用 `/opt/rag-production.env`。文件由运维配置，禁止加入 Git、日志或网页。支持以下环境覆盖：

```text
ACCELERATOR_MODEL_BASE_URL
ACCELERATOR_MODEL_NAME
ACCELERATOR_MODEL_API_KEY
```

在 GPU 主机执行：

```bash
RAG_ENV_FILE=/opt/rag-production.env \
  bash /opt/accelerator-rag/deploy/rag-start.sh
curl -fsS http://127.0.0.1:8003/health
```

脚本只管理挂载目录与名称匹配的独立 RAG 容器。配置文件为 `config/rag-production.json`。可通过 `RAG_GPU_DEVICE`、`RAG_WORKSPACE` 和 `RAG_RUNTIME_IMAGE` 覆盖部署资源。首次加载需要等待模型与索引核验完成。

索引沿用已签名的数据与目录，启动时完整核验一次。运行时禁止索引写入，不重复扫描整库。不要同时启动第二个进程持有同一组本地 Qdrant 索引。

## 使用接口

本机浏览器通过 `http://127.0.0.1:18003/` 访问时，需保持 SSH 转发运行。用户级服务 `accelerator-rag-tunnel.service` 将本机回环端口 `18003` 转发到 GPU 主机的 `8003`，断线后自动重连。首次在开发机安装：

```bash
install -Dm644 deploy/systemd/user/accelerator-rag-tunnel.service \
  ~/.config/systemd/user/accelerator-rag-tunnel.service
systemctl --user daemon-reload
systemctl --user enable --now accelerator-rag-tunnel.service
curl --noproxy '*' -fsS http://127.0.0.1:18003/health
```

该服务依赖已有 SSH 别名 `waveform-zyf-oneclick` 的免交互认证。若浏览器提示本机拒绝连接，先检查 `systemctl --user status accelerator-rag-tunnel.service` 和 `journalctl --user -u accelerator-rag-tunnel.service -n 30`，再区分隧道与远端服务故障。登录后会自动启动；访问时本机需要保持开机且网络可达。

```bash
curl -s http://127.0.0.1:8003/v1/rag/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"SHINE 主加速器采用什么工作模式？"}'
```

请求只接受 `query`。响应包含 `status`、`answer`、`requirements`、`citations`、`latency` 和 `request_id`。`requirements[].supported` 表示最终完整性；全部完整为 `answered`，仍有缺项但存在已核查事实为 `partial`，没有可展示事实为 `insufficient`。`coverage` 区分完整、部分和无证据，`reason`、`missing` 说明原因。不存在的证据 ID 或无法核验的模型输出返回 HTTP 502，网页提供重试提示。

`GET /v1/rag/documents/{document_id}` 返回登记的原始 PDF。`GET /v1/rag/documents/{document_id}/view#page=N` 打开本地 PDF 查看器，`N` 为物理页。接口不接受文件路径。引用中的 `quote` 是被选中的原文，真实服务器路径不进入响应。

网页支持 Enter 发送、Shift+Enter 换行、当前页面问答历史、新建会话、引用定位和复制答案。刷新会开始新的页面会话。Markdown、KaTeX、PDF.js 均使用本地资源，运行时不访问公网 CDN。

## 验收与故障处理

当前框架验收使用 `scripts/rag_framework_check.py`，直接调用正式 HTTP 接口。问题标签只留在测试客户端，实际请求只发送 `query`。在开发机具备服务访问通道后执行：

```bash
python scripts/rag_framework_check.py \
  --base-url http://127.0.0.1:18003 \
  --output reports/rag-framework-http.json
```

服务端配置 `trace_dir=tmp/rag-request-traces`，按响应中的 `request_id` 查找记录。文件权限为 `600`，保留最近 100 份。记录包含各轮候选、子集预算、冲突、补检索、核查原因和最终结果，不包含模型认证请求头。

旧版 Top-5 捕获与 Stage 3 启动脚本已清理；历史报告保留执行当时的结果。当前复核使用 `scripts/rag_framework_review.py`，召回统计使用 `scripts/rag_framework_metrics.py`，不沿用旧捕获工具的状态判断。

- 模型返回 401：核对仓库外凭据与当前模型服务配置。不要输出密钥。
- 模型未就绪：检查容器日志与 `/v1/models`，不要据旧报告推断服务状态。
- PDF 返回 404：检查文档是否登记，以及 `data/l0_raw` 下的原始文件是否完整。
- 索引核验失败：停止启动，核对冻结 contract 与数据。不要重建或覆盖索引。
- 回答耗时较长：检查模型负载和少量并发。服务只串行执行共享 GPU 检索，需求提取、综合与核查可并行处理不同请求。

旧版验收记录保存在 `reports/rag-production-readiness-20261026.md`；新框架结果另行记录，不能直接沿用旧版指标。
