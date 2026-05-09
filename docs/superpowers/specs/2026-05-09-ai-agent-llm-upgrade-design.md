# AI 客服 Agent — LLM 升级设计

## 目标

将 ai-customer-service-agent 从规则引擎/关键词匹配的 demo 升级为真正接入大模型的 AI Agent 系统，用于简历展示和暑期实习求职。

## 背景

现有项目已实现完整的工单管理、前端界面、Agent 工作流编排，但 AI 层全部使用规则引擎模拟：
- 情绪/分类/优先级分析 → 关键词规则
- 知识库检索 → 关键字权重打分
- 回复生成 → 字符串模板拼接

本次升级用真实 LLM 替代这三层，并增加流式输出和 Tool Calling。

## MVP 分期

### 第一阶段（本次实现，1-2 个月）

- DeepSeek / openai-compatible chat client
- LLM 工单分析（Structured Output JSON mode）
- LLM 流式回复（POST + fetch stream）
- RAG：keyword + embedding-lite（SQLite 存 embedding JSON，内存索引）
- Tool Calling：tool_registry.py + mock 数据 + 结构化 tool_calls 响应字段
- 完整成本控制安全阀
- 规则引擎/关键词检索保留为 fallback
- main.py 内新增端点，不拆分路由文件
- Vercel + Railway 部署

### 第二阶段（后续，不在本次范围）

- ChromaDB / Milvus Lite 向量数据库
- Claude / OpenAI 多 provider 适配
- 路由文件拆分重构

## 架构变更

```
                    现有                          升级后
分析层  ticket_analyzer.py (规则引擎)    →  llm_analyzer.py (LLM Structured Output)
检索层  knowledge_base.py (关键词匹配)    →  embedding_service.py (内存向量检索 + 关键词 fallback)
回复层  build_reply_text() (模板拼接)     →  reply_generator.py (LLM 流式生成)
编排层  _run_agent_workflow()             →  保留增强，接入 Tool Calling
新增                                        →  services/llm_client.py (统一 LLM 调用)
新增                                        →  services/tool_registry.py (工具注册与执行)
```

策略：新增文件，保留旧文件。通过环境变量切换新旧实现，不拆分路由文件。

## LLM 接入

### Provider 策略

MVP 只实现 openai-compatible 协议（DeepSeek），利用其与 OpenAI SDK 的兼容性。后续阶段再扩展 Claude 等非 openai-compatible provider。

```
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com/v1    # 默认，可覆盖为任意 openai-compatible 端点
LLM_MODEL=deepseek-chat
LLM_ENABLED=true                             # false 时降级为规则引擎
LLM_TIMEOUT=30                               # 请求超时（秒）
LLM_MAX_RETRIES=2                            # 失败重试次数
LLM_MAX_INPUT_CHARS=4000                     # 单次调用最大输入字符数
LLM_MAX_OUTPUT_TOKENS=1024                   # 单次调用最大输出 token 数
```

### 三个调用场景

| 场景 | 策略 | 原因 |
|------|------|------|
| 工单分析 | Structured Output (JSON mode / response_format) | 强制返回固定 schema |
| 自动回复 | Streaming API | 流式输出，用户体验好 |
| 工单总结 | 普通 completion | 一次性生成，无需流式 |

### 错误处理与降级

1. JSON 解析失败 → 重试一次，仍失败则降级到规则引擎分析结果
2. API 超时 → 重试一次，仍超时则降级
3. API Key 未配置/无效 → 前端工单分析面板显示"未配置 LLM API Key"，后端返回明确错误信息
4. 网络错误 → 降级到规则引擎，写入 system 消息记录降级原因

### 成本控制

- 主力模型用 DeepSeek，100万 token 几块钱
- 每条 LLM 调用限制 context 长度（知识库只传 top 3，输入截断到 LLM_MAX_INPUT_CHARS）
- LLM_ENABLED=false 可关闭所有 LLM 调用，开发调试时不烧钱
- 最大输出 token 限制 1024，防止异常长回复

## RAG 检索升级

### 从关键词到语义检索

现有关键词匹配无法处理同义表达（"我的钱能退吗" vs "退款政策"）。升级为 Embedding + 相似度检索。

### MVP 技术方案：SQLite + 内存索引

不引入 ChromaDB，避免额外依赖和文件系统持久化问题（Render/Railway 文件系统不保证持久化）：

1. 调用 openai-compatible embedding API（跟随 LLM provider）获取文档向量
2. 向量序列化为 JSON 存入 SQLite 的 embedding 列
3. 启动时加载所有启用的知识条目向量到内存
4. 检索时计算余弦相似度，返回 top 3

知识库新增/修改时即时更新向量，无需全量重建。

### 检索模式切换

```
RAG_MODE=hybrid   # hybrid | embedding | keyword
```

- `keyword`：保留原有关键词检索
- `embedding`：纯向量语义检索
- `hybrid`（默认）：两者结果合并去重，交集优先 + 各自 top 结果补足至 3 条

## 流式输出

### 端点设计

新增 `POST /api/tickets/{id}/stream-reply`。因为是 POST，前端使用 `fetch` + `ReadableStream` 读取 SSE 流，不支持浏览器原生 `EventSource`（EventSource 仅支持 GET）。

前端实现要点：
- `fetch(url, { method: 'POST' })` 获取 response.body
- `response.body.getReader()` 逐块读取
- 解析 SSE 格式（`data: {...}\n\n`）
- 每个 data chunk 追加到回复区域，实现打字机效果
- 收到 `[DONE]` 后标记完成，展示 Tool 调用链路

前端回复区域改为打字机效果，逐 token 显示 AI 回复。

## Tool Calling

### 设计

MVP 实现 tool_registry.py，工具返回 mock 数据（当前模型中没有真实的订单/物流/商品表，mock 数据已足够展示 Agent 的推理-行动能力）。

### 工具列表

| Tool | 功能 | 实现方式 |
|------|------|----------|
| lookup_order(order_id) | 查询订单状态/物流 | mock 数据 |
| check_refund_policy() | 查退款规则 | 查询 KnowledgeBase 表 |
| get_product_manual(sku) | 查产品说明 | 查询 KnowledgeBase 表 |
| escalate_to_human(reason) | 升级人工 | 修改 ticket 状态 |

### 响应结构

Agent 工作流响应中新增 `tool_calls` 字段：

```json
{
  "ticket_id": 1,
  "action": "replied_with_tool",
  "tool_calls": [
    {"tool": "lookup_order", "input": {"order_id": "12345"}, "output": {"status": "已发货", "tracking": "SF12345678"}},
    {"tool": "check_refund_policy", "input": {}, "output": {"policy": "7天无理由退货"}}
  ],
  "reply": "您的订单已发货，快递单号 SF12345678..."
}
```

前端 Agent 工作台展示 Tool 调用链路，让 Agent 行为透明可解释。

## 部署

- 前端：Vercel（免费）
- 后端：Railway 或 Render（免费额度足够 demo）
- 数据库：Railway 提供 PostgreSQL（生产环境用 PostgreSQL，开发环境可继续用 SQLite）
- 可选：Docker Compose 一键启动脚本

## 文件清单

新增文件：
```
backend/services/llm_client.py        # LLM 统一调用客户端（openai-compatible）
backend/services/llm_analyzer.py      # LLM 版工单分析（Structured Output）
backend/services/embedding_service.py # 向量化 + 内存余弦相似度检索
backend/services/reply_generator.py   # LLM 流式回复生成
backend/services/tool_registry.py     # Tool 注册、mock 数据、执行调度
```

修改文件：
```
backend/main.py              # 新增 stream-reply 端点、Tool Calling 编排逻辑
backend/models.py            # 可选：新增 tool_call 记录模型
backend/requirements.txt     # 新增 openai, sse-starlette
frontend/app/...             # 打字机效果、Tool 调用链路展示
```

不变文件（保留兼容）：
```
backend/services/ticket_analyzer.py   # 规则引擎保留，作为 LLM 降级 fallback
backend/services/knowledge_base.py    # 关键词检索保留，hybrid 模式使用
backend/services/ticket_summarizer.py # 模板总结保留，作为 LLM 降级 fallback
```

## 非目标（本次不做）

- 用户认证/登录系统
- 多知识库隔离
- 对话记忆（多轮上下文管理）
- ChromaDB / 外部向量数据库
- 多 provider 全适配（Claude、Anthropic SDK）
- 路由文件拆分重构
- 生产级监控/日志
- 高并发优化
