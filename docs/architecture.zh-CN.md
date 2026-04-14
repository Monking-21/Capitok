# 架构设计文档

本文档描述 Capitok 的设计目标、系统架构、存储模型与运维策略。

## 设计原则（避免过度设计）

Capitok 采用“边界先行、实现渐进”的策略：

- 先定义可扩展边界，避免未来推倒重来
- 当前仅实现 MVP 必需能力，降低开源初期开发负担
- 生产级能力以可插拔形式预留，不在首版强制落地

## 分阶段范围

### MVP（首版必须）

- 基础鉴权（API Key 或 JWT）
- 原始日志入库与基础检索
- 向量检索 + 全文检索的最小可用融合
- 备份与恢复脚本

### 预留能力（首版可不实现）

- 完整多租户 RBAC
- 持久化队列、重试与死信
- 完整审计链路与合规删除流程
- 可视化运营面板与高级告警

## 设计目标

- 极致数据安全（母带级备份）
- 工业级检索性能（混合搜索）
- 极低迁移与恢复成本（容器化）

## 逻辑架构

```text
[ Agent 层 ]          OpenClaw (Plugin) / Hermes (Provider)
                              |
                              v
[ 中间件层 ]          FastAPI Gateway (Memory MaaS)
                    /         |         \
      (异步存原文) /   (异步提炼事实)   \ (同步检索)
                  /          |           \
[ 存储层 ]       Raw Postgres  Mem0 Logic  Refined Postgres
                 (JSONB)     (处理逻辑)    (pgvector + tsvector)
```

## 存储模型（PostgreSQL 16+）

使用单实例 PostgreSQL，通过逻辑分表实现冷热分离。

### 表 A：raw_chat_logs

用途：
- 永久保存每条对话原始 JSON

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
- 存储提炼后的原子事实，服务检索

技术要点：
- 向量列：vector(1536) 或与模型维度一致
- 全文列：tsvector，用于关键词和专有词召回
- 混合检索：向量相似度 + FTS 排名融合
- ANN 索引：HNSW 支撑低延迟

建议补充字段：
- tenant_id (text)
- principal_id (text)
- embedding_version (text)
- updated_at (timestamptz)

性能说明：
- 100k 规模下 p95 < 20ms 可作为目标，不应写成绝对保证。

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
2. 将记忆端点指向 FastAPI 中间件。
3. trace 日志仅在排障期间开启。

## FastAPI + Mem0 核心流程

```py
from fastapi import BackgroundTasks, FastAPI
from mem0 import Memory

app = FastAPI()

m = Memory.from_config({
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "connection_string": "postgresql://postgres:pass@localhost:5432/memory_db"
        },
    }
})

@app.post("/v1/ingest")
async def ingest_memory(data: dict, bg: BackgroundTasks):
    bg.add_task(save_to_raw_db, data)

    text = f"{data.get('input', '')}\n{data.get('output', '')}"
    bg.add_task(m.add, text, user_id=data["user_id"])

    return {"status": "queued"}

@app.get("/v1/search")
async def search_memory(query: str, user_id: str):
    return m.search(query, user_id=user_id)
```

可靠性说明：
- 生产环境建议将进程内后台任务替换为可靠队列，避免宕机丢任务。

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
- 每晚备份 raw 与 refined 表。

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
- 基础告警规则（错误率、队列积压、检索延迟）

### 增强版（可视化）

- 使用 Grafana 等现成工具搭建 dashboard
- 仅在需要业务运营视图时，再开发自定义前端控制台

## 抗风险分析

- Mem0 替换风险：数据仍在 PostgreSQL
- 模型迁移风险：可从原始日志重建向量
- Agent 故障风险：中间件独立可恢复