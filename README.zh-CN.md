# Capitok（中文说明）

Capitok 的核心意思是：`capitalize your token`。

也就是把 Agent 已经花掉的上下文和 token 成本，沉淀成可长期保存、可迁移、可恢复、可复用的资产。

Capitok 是一个面向 AI Agent 的开源原始对话归档与恢复层。它会在对话从上下文窗口中滑出之前，先把完整交互记录保存下来，方便你之后回放、重建索引、迁移框架，或者在新的记忆系统里继续使用。

## Capitok 是做什么的

- 归档 Agent 的原始对话，避免历史直接丢失
- 把已经消耗的 token 成本转成可复用的对话资产
- 为未来的回放、重建索引、重建记忆提供恢复底座
- 作为上层 memory 框架的补充，而不是替代品

## 为什么值得做

很多 Agent 系统已经花了大量 token 生成有价值的对话，但这些内容往往只存在于某个上下文窗口、某个运行时，或者某个特定框架里。

Capitok 的核心思路是把这些已消耗的 token 当成资产：

- 保留原始对话，而不只是摘要
- 跨上下文重置、设备切换、框架迁移继续可用
- 为后续记忆管线保留原始母带
- 先有归档，再在归档之上做检索和重建

## 快速开始

### 1. 本地启动 Capitok

```bash
git clone https://github.com/Monking-21/Capitok.git
cd Capitok
cp .env.example .env
docker compose up --build
```

### 2. 验证服务是否启动

```bash
curl http://localhost:8000/health
```

### 3. 写入一条交互

```bash
curl -X POST "http://localhost:8000/v1/ingest" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-prod-key" \
  -d '{
    "session_id": "s-001",
    "user_id": "u-001",
    "source": "agent",
    "input": "I like Tushare API",
    "output": "Noted, preference stored.",
    "metadata": {"agent": "OpenClaw"}
  }'
```

### 4. 检索已归档内容

```bash
curl "http://localhost:8000/v1/search?query=Tushare&top_k=5" \
  -H "X-API-Key: replace-with-prod-key"
```

如果是本地开发，也可以直接使用仓库里的开发编排：

```bash
docker compose -f docker-compose.dev.yml up --build
```

这个模式默认读取 `.env.dev`，可直接使用本地测试 key `dev-ingest-search-key`。

## CLI

Capitok 现在还提供一个轻量、session-first 的 CLI，适合直接在源码仓库里使用：

```bash
uv run capitok health
uv run capitok sessions list
uv run capitok sessions show <session_id> --source codex
uv run capitok search "quarterly review"
uv run capitok codex enable
uv run capitok hermes enable
```

CLI 复用和 Codex 集成相同的本地配置解析顺序：

- 显式导出的 `CAPITOK_API_URL` / `CAPITOK_API_KEY`
- 否则读取 `.env`
- 否则读取 `.env.dev`

## 接入方式

### Hermes 接入

如果你已经在使用 Hermes，最快的接入方式是：

```bash
hermes --version
bash scripts/install-hermes-plugin.sh
```

然后验证：

```bash
hermes plugins list
curl -i http://localhost:8000/health -H "X-API-Key: dev-ingest-search-key"
```

当前 Hermes 插件会：

- 通过 `post_llm_call` hook 自动保存已完成回合
- 提供 `capitok_recall` 作为基础 recall 工具
- 提供 `capitok_save` 作为显式保存工具

安装器会把 `integrations/hermes` 复制到 Hermes 插件目录，并优先读取 shell 环境变量，其次读取 `.env` 或 `.env.dev`。
Capitok 当前建议使用 Hermes `0.9.0` 及以上版本。若 Hermes 未安装、版本偏旧，或安装器无法识别版本号，安装器会给出 warning，但不会阻断安装。

如需覆盖配置，可先导出：

- `CAPITOK_API_URL`
- `CAPITOK_API_KEY`
- `CAPITOK_AUTO_SAVE`
- `CAPITOK_TIMEOUT`

完整说明见：[integrations/hermes/README.md](integrations/hermes/README.md)

### Codex 接入

如果你使用 Codex hooks，Capitok 可以归档支持的 hook 事件，方便后续恢复，但不会替代 Codex 自己的记忆行为。
安装 Codex 接入时，会接管 Capitok 支持的这些 Codex 事件槽位：`SessionStart`、`UserPromptSubmit`、`PreToolUse`、`PostToolUse` 和 `Stop`；如果这些事件已配置其他 handler，安装器会直接覆盖它们。
安装命令为 `bash scripts/install-codex-hook.sh`。

完整说明见：[integrations/codex/README.md](integrations/codex/README.md)

### 直接接入 API

如果你在构建自己的 Agent runtime，可以直接对接 Capitok 的 HTTP API：

- `POST /v1/ingest`：归档原始交互
- `GET /v1/search`：查询派生 recall 记录
- `GET /v1/sessions`：列出最近归档的会话或原始记录
- `GET /v1/sessions/{session_id}`：查看某个会话的时间线
- `GET /health`：健康检查

鉴权方式为 `X-API-Key` 请求头。租户与主体身份由服务端根据 API key 映射解析，不由请求体直接声明。

## 适合谁使用

- 希望保留完整对话资产的 Agent 开发者
- 需要独立恢复层的 Agent 基础设施团队
- 想先把原始数据留住，再逐步建设上层 memory 系统的团队

## 项目定位

Capitok 不是一个“主实时语义记忆框架”。

它更适合被理解为：

- 一个原始数据优先的归档层
- 一个面向未来回放与重建的恢复底座
- 一个连接 Agent runtime 与存储资产的中间层
- 一个可供上层 memory 工作流继续扩展的基础设施层

## 当前 MVP 能力

当前 MVP 已支持：

1. API Key 鉴权与租户/主体映射
2. 原始聊天日志持久化
3. 进程内异步派生文本写入链路
4. 基于 tenant 与 principal 作用域的基础检索
5. 以 Alembic migration 作为主 schema 管理方式
6. 从数据库自动导出 schema 快照
7. 默认使用 `uv` 作为依赖管理与命令执行工具
8. 双 compose 模型：默认生产编排加独立 dev/test 配置

当前 MVP 并不以“完整语义记忆框架”为目标。  
`refined_memories` 更适合被理解为原始归档之上的派生层，用于基础 recall 和未来重建流程。

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

## 文档目录

- 架构设计（英文）：[docs/architecture.md](docs/architecture.md)
- 架构设计（中文）：[docs/architecture.zh-CN.md](docs/architecture.zh-CN.md)
- 实施进展与计划（英文）：[docs/implementation-status.md](docs/implementation-status.md)
- 实施进展与计划（中文）：[docs/implementation-status.zh-CN.md](docs/implementation-status.zh-CN.md)
- Hermes 接入指南：[integrations/hermes/README.md](integrations/hermes/README.md)
- Codex 接入指南：[integrations/codex/README.md](integrations/codex/README.md)
- 英文 README（默认）：[README.md](README.md)

## Schema 工作流

1. 先执行 migration。
2. 运行 `./scripts/dump-schema.sh` 刷新 `sql/schema.sql`。

## 路线图

1. 冻结 MVP 架构
2. 发布 API 与 schema 规范
3. 接入持久化队列后端，如 Redis Streams 或 RabbitMQ
4. 完善可观测性与可靠性
5. 根据社区反馈持续迭代

## 贡献说明

待初版实现发布后，欢迎社区贡献。

优先贡献方向：

1. API 设计评审
2. 存储 schema 优化
3. 压测与 benchmark 脚本
4. 可靠性与安全增强

## 许可证

许可证尚未最终确定。

候选：

1. MIT
2. Apache-2.0
