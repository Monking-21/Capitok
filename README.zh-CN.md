# Capitok（中文说明）

Capitok 是一个面向 AI Agent 的开源原始对话归档与恢复层。
它的设计目标是补充主流 memory 框架，而不是替代它们。

先归档，再重建。
Capitok 保存的是 Agent 已经付出 token 成本得到的对话资产，让它们在上下文清空、设备迁移、框架切换之后仍然可以被恢复和再利用。

## 项目定位

Capitok 把已经消耗掉的上下文和 token 视为长期资产：

- 在上下文窗口滑出之前，先把 Agent 原始对话持久化
- 在设备迁移、运行时切换、框架替换时保留独立归档
- 为未来回放、重建索引、重建上层记忆提供母带数据
- 作为 Mem0 等工具之下的归档与恢复层，与上层记忆工作流协同

## 项目状态

- 阶段：MVP 骨架开发中
- 代码实现：已提供 FastAPI 网关与数据库 schema 初版
- 目标用户：Agent 开发者与基础设施工程师

## 项目亮点

- 原始数据优先策略，保障长期可恢复
- 归档优先设计，便于回放、导出与迁移
- Agent 运行时与对话资产存储解耦
- 检索能力作为派生辅助层，而不是项目主目标
- 容器化优先，便于迁移与恢复

## 文档目录

- 架构设计（英文）：[docs/architecture.md](docs/architecture.md)
- 架构设计（中文）：[docs/architecture.zh-CN.md](docs/architecture.zh-CN.md)
- 实施进展与计划（英文）：[docs/implementation-status.md](docs/implementation-status.md)
- 实施进展与计划（中文）：[docs/implementation-status.zh-CN.md](docs/implementation-status.zh-CN.md)
- Hermes 接入指南：[integrations/hermes/README.md](integrations/hermes/README.md)
- 英文 README（默认）：[README.md](README.md)

## 仓库结构

```text
.
├── README.md
├── README.zh-CN.md
├── .env.dev
├── pyproject.toml
├── alembic.ini
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── migrations/
│   ├── env.py
│   └── versions/
├── sql/
│   └── schema.sql
├── scripts/
│   ├── backup.sh
│   ├── dump-schema.sh
│   ├── migrate.sh
│   ├── start-api.sh
│   ├── wait-for-db.sh
│   └── restore.sh
├── src/
│   └── capitok/
│       ├── main.py
│       ├── config.py
│       ├── security.py
│       ├── db.py
│       ├── schemas.py
│       └── queue/
│           ├── interface.py
│           └── inprocess.py
└── docs/
    ├── architecture.md
    ├── architecture.zh-CN.md
    ├── implementation-status.md
    └── implementation-status.zh-CN.md
```

## 快速开始

### 生产环境（默认）

1. 克隆仓库并进入项目目录：

```bash
git clone https://github.com/Monking-21/Capitok.git
cd Capitok
```

2. 安装 uv：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. 准备环境变量：

```bash
cp .env.example .env
```

4. 使用默认 compose 启动生产导向编排：

```bash
docker compose up --build
```

### 开发与测试环境

1. 使用独立 dev/test compose 文件：

```bash
docker compose -f docker-compose.dev.yml up --build
```

该模式默认使用仓库内的 `.env.dev` 文件。

### 基础验证

1. 健康检查：

```bash
curl http://localhost:8000/health
```

2. 写入示例：

```bash
curl -X POST "http://localhost:8000/v1/ingest" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: dev-ingest-search-key" \
    -d '{
        "session_id": "s-001",
        "user_id": "u-001",
        "source": "openclaw",
        "input": "I like Tushare API",
        "output": "Noted, preference stored.",
        "metadata": {"agent": "OpenClaw"}
    }'
```

3. 检索示例：

```bash
curl "http://localhost:8000/v1/search?query=Tushare&top_k=5" \
    -H "X-API-Key: dev-ingest-search-key"
```

### Hermes 接入

一条命令完成 Hermes 插件安装和配置：

```bash
bash scripts/install-hermes-plugin.sh
```

然后验证：

```bash
hermes doctor
curl -i http://localhost:8000/health -H "X-API-Key: dev-ingest-search-key"
```

安装器会把 `integrations/hermes` 复制到 Hermes 插件目录，并优先读取 shell 环境里的 Capitok 配置，然后回退到仓库里的 `.env` 或 `.env.dev`。
如果需要，也可以先导出 `CAPITOK_API_URL`、`CAPITOK_API_KEY`、`CAPITOK_AUTO_SAVE` 或 `CAPITOK_TIMEOUT` 再运行。

当前 MVP 已支持：

1. API Key 鉴权与租户/主体映射
2. 原始日志入库
3. 进程内异步派生文本写入链路
4. 按 tenant 和 principal 作用域的基础检索
5. 以 Alembic migration 作为主数据库组织方式
6. 支持从数据库自动导出 schema 快照
7. 默认使用 uv 进行依赖管理与命令执行
8. 双 compose 模型：默认生产 + 开发测试独立文件

当前 MVP 并不以“完整语义记忆框架”为目标。
`refined_memories` 更适合被理解为原始归档之上的派生层，用于基础 recall 和未来重建流程。

完整的 Hermes 插件说明仍然保留在 [integrations/hermes/README.md](integrations/hermes/README.md)。

schema 快照流程：

1. 先执行 migration。
2. 运行 `./scripts/dump-schema.sh` 刷新 `sql/schema.sql`。

## 路线图

1. 冻结 MVP 架构
2. 发布 API 与 schema 规范
3. 接入持久化队列后端（Redis Streams 或 RabbitMQ）
4. 完善可观测性与可靠性
5. 社区反馈迭代

## 贡献说明

待初版实现发布后，欢迎社区贡献。

优先贡献方向：

1. API 设计评审
2. 存储 schema 优化
3. 性能压测脚本
4. 可靠性与安全增强

## 许可证

许可证尚未最终确定。

候选：

1. MIT
2. Apache-2.0
