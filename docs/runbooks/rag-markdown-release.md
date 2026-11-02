# Markdown 双路索引发布与回滚

本页记录 2026 年 10 月 30 日完成的实际发布。文档范围为 13 份既有 PDF 和 4 份 Markdown。详细证据见[线上验证报告](../../reports/validity-pilot-online-20261030/README.md)。

## 1. 连接 GPU 主机

主项目 `accelerator-rag` 的 `docs/runbooks/GPU_SERVER_DEPLOYMENT.md` 已记录密码认证路径。开发机通过 zyf 跳板机连接 GPU 主机 `10.101.9.190`，目标账号为 `root`。SSH 别名 `waveform-zyf-oneclick` 本身只登录跳板机。

现有凭据加载器位于 `/home/whloong/projects/data_analysis/gpu-monitor/tunnel.py`。调用 `connection_settings()` 获取连接参数，再使用 Paramiko 建立跳板机连接和 `direct-tcpip` 通道。沿用已登记的主机密钥及 `RejectPolicy`。密码只在内存中用于认证，不复制进脚本、报告或仓库。

本机常驻 HTTP 隧道仍使用 `127.0.0.1:18003`，目标为 GPU 主机的 `8003`。HTTP 隧道可用与 GPU SSH 公钥认证成功是不同条件；公钥失败不能据此断定无法管理 GPU 主机。

## 2. 本次发布过程

1. 检查容器、磁盘和 GPU。生成服务占用 8 张卡的大部分显存，RAG 使用 GPU 2。
2. 创建独立目录 `/opt/accelerator-rag-releases/md-20261030`，上传本次代码及 Markdown 快照，复制既有 PDF。
3. 在同一文件系统中硬链接已有模型文件。模型文件按不可变资源使用；后续更换模型时应另建目录，不能原地覆盖这些文件。
4. 短暂停止旧 RAG 容器，使本地 Qdrant 释放 SQLite 文件；复制两路索引后立即恢复旧容器。没有复制运行中的索引文件。
5. 在无网络、无 GPU 的独立容器中使用 CPU 和 FP32 构建 Markdown 向量。模型、tokenizer、passage 契约与原集合一致；运行时仍使用 GPU 检索。
6. 检查两路父块集合完全一致，逐块比对新增 Markdown 的正文、章节和版本。确认后更新配置中的点数。
7. 停止旧容器，重命名为 `accelerator-rag-pdf-rollback-20261030`。新容器沿用 `accelerator-rag` 名称、GPU 2 和端口 `8003`，挂载新发布目录。模型认证环境从旧容器内存读取并继承，不输出密钥。
8. 检查健康状态、17 份文档目录、4 份 Markdown 原文和章节接口，再执行 50 题线上验证。

原目录及其两路索引未被新构建覆盖。生成模型容器和 Open WebUI 未重启。

## 3. 当前资源与证据

| 资源 | 路径或状态 |
| --- | --- |
| 当前容器 | `accelerator-rag` |
| 当前目录 | `/opt/accelerator-rag-releases/md-20261030` |
| 回滚容器 | `accelerator-rag-pdf-rollback-20261030`，已停止 |
| 回滚目录 | `/opt/accelerator-rag` |
| 上传源码快照 | 当前目录下的 `release-source.tar.gz` |
| 实际运行配置 | 当前目录下的 `config/rag-production.json` |
| 构建与核对结果 | 当前目录下的 `tmp/md-index-build.log`、`tmp/md-index-verification.json` |
| 部署身份 | 当前目录下的 `tmp/deployment.json`，不含密钥 |
| 请求记录 | 当前目录下的 `tmp/rag-request-traces/` |

源码压缩包保留构建前上传内容；实际点数以核对后配置为准。代码来自未提交工作区，因此本轮不是冻结代码实验。

## 4. 回滚

只在需要恢复旧 PDF 版本时执行以下命令。当前 Markdown 版本会停止，但其目录、索引和请求记录保留。

```bash
docker stop accelerator-rag
docker rename accelerator-rag accelerator-rag-md-retained-20261030
docker rename accelerator-rag-pdf-rollback-20261030 accelerator-rag
docker start accelerator-rag
curl -fsS http://127.0.0.1:8003/health
```

启动需要等待模型加载。旧版目录应返回 13 份 PDF；不要把它误认为 Markdown 版本仍在运行。回滚后如需再次发布，先核对实际容器名称和挂载目录，再执行[生产运行手册](rag-production.md)中的启动命令。
