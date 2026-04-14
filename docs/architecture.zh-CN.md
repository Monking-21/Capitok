# 架构设计文档

本文档描述 Capitok 的设计目标、系统架构、存储模型与运维策略。

Capitok 的定位是 Agent 系统的原始对话归档与恢复底座。
它通过保留源对话，为未来回放、重建索引、迁移到其他 memory 框架提供母带数据，而不是试图替代这些上层框架。

## 设计原则（避免过度设计）

Capitok 采用“边界先行、实现渐进”的策略：

- 先定义可扩展边界，避免未来推倒重来
- 当前仅实现 MVP 必需能力，降低开源初期开发负担
- 生产级能力以可插拔形式预留，不在首版强制落地

## 分阶段范围

### MVP（首版必须）

- 基础鉴权（API Key 或 JWT）
- 原始日志入库与归档边界
- 基于派生记录的基础检索
- 备份与恢复脚本

### 预留能力（首版可不实现）

- 完整多租户 RBAC
- 持久化队列、重试与死信
- 完整审计链路与合规删除流程
- 可视化运营面板与高级告警

## 设计目标

- 把 Agent 原始对话保存为长期资产
- 通过独立归档层降低迁移与恢复成本
- 为回放、重建索引、重建上层记忆提供基础
- 提供基础检索能力，但不把自己定义为主记忆框架

## 逻辑架构

```text
[ Agent 层 ]          OpenClaw (Plugin) / Hermes (Provider)
                              |
                              v
[ 中间件层 ]          FastAPI Gateway (Archive / Recovery MaaS)
                    /         |         \
      (同步存原文) /   (异步派生记录)   \ (同步检索)
                  /          |           \
[ 存储层 ]       Raw Postgres  可选上层 Memory  Derived Postgres
                 (JSONB)        (Mem0 等)      (FTS / 未来向量)
```

## 存储模型（PostgreSQL 16+）

使用单实例 PostgreSQL，通过逻辑分表实现冷热分离。

### 表 A：raw_chat_logs

用途：
- 永久保存每条对话原始 JSON
- 作为恢复、回放与未来重建的源数据母带

关键字段：
- id (uuid)
- tenant_id (text)
- principal_id (text)
- session_id (text)
- user_id (text)
- agent_id (text)
- source (text)
- content (jsonb)
- created_at (timestamptz)

### 表 B：refined_memories

用途：
- 存储基于原始归档生成的可检索派生记录

技术要点：
- 全文列：tsvector，用于基础关键词和专有词召回
- 向量列：为未来下游集成预留
- 当索引策略变化时，派生记录应可从 raw 重新生成
- MVP 中数据耐久性优先于复杂检索质量

建议补充字段：
- tenant_id (text)
- principal_id (text)
- embedding_version (text)
- updated_at (timestamptz)

性能说明：
- 性能目标应视部署环境而定，不应写成产品承诺。

## 接入方案

### 身份与租户边界（必须约束）

为避免越权读写，身份字段不应由业务请求体直接决定：

1. 客户端只提交 token（API Key/JWT）。
2. 网关从 token 解析 tenant_id、principal_id 与 scope。
3. 服务端强制将 tenant_id/principal_id 写入存储与查询条件。
4. 请求体中的 user_id 仅作为业务属性，不作为鉴权依据。

数据隔离建议层级：

- L1：tenant 隔离（必须）
- L2：principal/user 隔离（按产品需求）
- L3：agent 通道标识（审计用途，不作为主隔离边界）

### OpenClaw 插件 Hook 示例

```ts
onResponseGenerated: async (context) => {
  const payload = {
    user_id: "weiling",
    input: context.message.content,
    output: context.response.content,
    metadata: { agent: "OpenClaw", model: context.model },
  };

  fetch("http://localhost:8000/v1/ingest", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": "${MEMORY_API_KEY}" },
    body: JSON.stringify(payload),
  }).catch(() => {
    // 生产环境建议增加重试或本地队列兜底。
  });
};
```

### Hermes Provider 配置

1. 选择 PostgreSQL 作为后端。
2. 将归档或记忆接入端点指向 FastAPI 中间件。
3. trace 日志仅在排障期间开启。

## FastAPI 归档 + 可选 Memory 接入流程

```py
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()

@app.post("/v1/ingest")
async def ingest_memory(data: dict, bg: BackgroundTasks):
    save_to_raw_db(data)

    text = f"{data.get('input', '')}\n{data.get('output', '')}"
    bg.add_task(save_derived_record, text, user_id=data["user_id"])
    # 后续如有需要，可把 raw 数据重放到 Mem0 或其他 memory 引擎。

    return {"status": "queued"}

@app.get("/v1/search")
async def search_memory(query: str, user_id: str):
    return search_derived_records(query, user_id=user_id)
```

可靠性说明：
- 原始归档链路是最关键的耐久性边界。
- 当派生索引成为生产关键路径时，建议把进程内后台任务替换为可靠队列。

### 队列抽象（预留接口）

为控制复杂度，首版可保留进程内异步；但需预留统一队列接口，便于后续切换：

- enqueue_ingest_task(payload)
- enqueue_refine_task(payload)
- handle_retry(task_id)
- move_to_dead_letter(task_id)

后续可替换实现：Redis Stream、RabbitMQ 或 Postgres 队列表。

## 部署与安全

1. 容器化：
- 通过 docker compose 启动 PostgreSQL（含 pgvector）与 FastAPI。
- 数据目录挂载到加密磁盘或 NAS。

2. 备份：
- 恢复保证应优先围绕 raw 表设计。
- 当派生检索状态对业务同样重要时，再同时备份 raw 与 refined 表。

```bash
pg_dump -t raw_chat_logs -t refined_memories memory_db > memory_backup.sql
```

3. 安全：
- 启用 API Key 或 JWT。
- 增加 TLS、密钥轮换与审计日志。

## 可观测性与 Dashboard（渐进实现）

### 首版（无前端也可）

- 暴露指标接口（如 Prometheus metrics）
- 结构化日志（含 trace_id、tenant_id）
- 基础告警规则（错误率、归档写入失败、队列积压、检索延迟）

### 增强版（可视化）

- 使用 Grafana 等现成工具搭建 dashboard
- 仅在需要业务运营视图时，再开发自定义前端控制台

## 抗风险分析

- 上层 memory 框架替换风险：数据仍在 PostgreSQL
- 模型迁移风险：可从原始日志重建派生记录或向量
- Agent 故障风险：归档中间件独立可恢复
