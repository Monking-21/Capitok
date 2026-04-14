# 实施进展与下一步计划

本文档用于记录当前已完成工作、下一阶段开发计划，以及关键结构决策。

## 1. 已完成工作

### 1.1 API 与服务骨架

- 已完成 FastAPI 应用启动与路由。
- 已提供接口：
  - `GET /health`
  - `POST /v1/ingest`
  - `GET /v1/search`

对应文件：
- [src/capitok/main.py](../src/capitok/main.py)
- [src/capitok/schemas.py](../src/capitok/schemas.py)

### 1.2 安全边界（MVP）

- 已实现 API Key 鉴权。
- 身份由服务端 API Key 映射解析，不由请求体声明。
- 通过 scope 检查控制 ingest/search 权限。

对应文件：
- [src/capitok/security.py](../src/capitok/security.py)
- [src/capitok/config.py](../src/capitok/config.py)

### 1.3 存储与数据模型

- 已创建 PostgreSQL schema：
  - `raw_chat_logs`
  - `refined_memories`
- 已准备全文检索索引与向量扩展。
- SQL schema 已补充维护备注，明确租户隔离、embedding_version 与搜索行为约束。
- Alembic migration 现已成为数据库演进的主方式。
- 已增加 schema 快照导出脚本，可从数据库自动刷新 `sql/schema.sql`。
- 已明确 `raw_chat_logs` 为源数据归档层，`refined_memories` 为派生检索层。

对应文件：
- [sql/schema.sql](../sql/schema.sql)
- [src/capitok/db.py](../src/capitok/db.py)

### 1.4 队列抽象（预留设计 + MVP 实现）

- 已定义队列抽象接口。
- 已提供进程内异步适配器用于 MVP。

对应文件：
- [src/capitok/queue/interface.py](../src/capitok/queue/interface.py)
- [src/capitok/queue/inprocess.py](../src/capitok/queue/inprocess.py)

### 1.5 运维基础

- 已拆分 Docker Compose 运行模型：
  - `docker-compose.yml` 默认生产导向部署
  - `docker-compose.dev.yml` 开发/测试专用
- 已增加环境模板。
- 已增加开发环境文件（`.env.dev`）。
- 已增加备份与恢复脚本。
- 已增加迁移执行脚本。
- 已增加数据库就绪等待脚本，供 compose 启动时使用。
- 已增加 schema 导出脚本。
- 已增加统一 API 启动脚本（`scripts/start-api.sh`）。
- 已增加 OpenAPI 契约文件。
- 已切换为默认使用 uv 管理依赖与执行命令。
- 文档侧已补充实施进展文件，并更新为 src 布局说明。

对应文件：
- [docker-compose.yml](../docker-compose.yml)
- [docker-compose.dev.yml](../docker-compose.dev.yml)
- [Dockerfile](../Dockerfile)
- [.env.example](../.env.example)
- [.env.dev](../.env.dev)
- [scripts/backup.sh](../scripts/backup.sh)
- [scripts/restore.sh](../scripts/restore.sh)
- [scripts/start-api.sh](../scripts/start-api.sh)
- [openapi.yaml](../openapi.yaml)

## 2. 进行中

- 继续对齐架构文档与“归档优先”的项目定位。
- 增加 ingest/search 路径的基础测试。
- 评估当前派生记录写入链路是否先保持文本优先，再补齐外部 memory 集成。

## 3. 下一步开发计划

### Phase A（当前 -> v0.1.1）

1. 增加测试
- 鉴权与 scope 单元测试
- ingest/search 集成测试

2. 完善错误处理
- 统一错误响应结构
- 增强 DB 与队列失败可观测性

3. 增加指标暴露
- ingest 成功/失败计数
- search 延迟分布

4. 复核 SQL 迁移安全性
- 检查 schema 是否与目标 PostgreSQL + pgvector 版本兼容
- 决定 ANN 索引是否保留在首个 migration，还是拆到后续 migration

5. 补充 migration 使用说明
- 记录 revision 命名规则与 upgrade/downgrade 用法
- 明确 `schema.sql` 只是参考快照，不是主变更路径

6. 增加 CI 漂移检查
- 在临时数据库执行 migration
- 导出 schema 后比对 `sql/schema.sql` 是否存在差异

### Phase B（v0.2）

1. 持久化队列适配器
- 首选 Redis Streams
- 补齐重试与死信

2. 检索能力升级
- 保持检索能力作为派生辅助层来设计
- 仅在有助于原始归档 recall 时增加检索策略开关

3. Mem0 适配完善
- 完善向 Mem0 等系统的重放或导出路径
- 对齐 `embedding_version` 策略

### Phase C（v0.3+）

1. 多租户安全强化
- 在 API Key scope 基础上增强策略模型
- 增加审计导向事件记录

2. 运维可观测性增强
- Prometheus + Grafana dashboard
- 仅在必要时开发自定义前端控制台

## 4. 结构决策：仓库名与 `capitok/` 代码目录

问题：项目根目录已经叫 Capitok，再创建 `capitok/` 目录是否合理？

结论：合理，这是 Python 项目常见结构。

原因：
- 根目录是仓库身份与工程容器。
- 内层 `capitok/` 是可导入包命名空间。
- 这样可避免导入歧义，便于模块化。

当前建议：
- 保持根目录为 `Capitok`。
- 保持代码包目录为 `capitok`。

可选后续方案：
- 在后续版本升级为 `src/capitok/` 布局，进一步强化打包隔离。
