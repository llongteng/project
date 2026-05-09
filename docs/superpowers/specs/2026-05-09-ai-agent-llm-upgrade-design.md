# AI 客服 Agent — LLM 升级设计

## 目标

将 ai-customer-service-agent 从规则引擎/关键词匹配的 demo 升级为真正接入大模型的 AI Agent 系统，用于简历展示和暑期实习求职。

## 背景

现有项目已实现完整的工单管理、前端界面、Agent 工作流编排，但 AI 层全部使用规则引擎模拟：
- 情绪/分类/优先级分析 → 关键词规则
- 知识库检索 → 关键字权重打分
- 回复生成 → 字符串模板拼接

本次升级用真实 LLM 替代这三层，并增加流式输出和 Tool Calling。

## 架构变更

```
                    现有                          升级后
分析层  ticket_analyzer.py (规则引擎)    →  llm_analyzer.py (LLM Structured Output)
检索层  knowledge_base.py (关键词匹配)    →  embedding_service.py (向量语义检索)
回复层  build_reply_text() (模板拼接)     →  reply_generator.py (LLM 流式生成)
编排层  _run_agent_workflow()             →  保留增强，接入 Tool Calling
新增                                        →  routes/stream.py (SSE 端点)
新增                                        →  services/llm_client.py (统一 LLM 调用)
```

策略：新增文件，保留旧文件。通过环境变量切换新旧实现，方便回退和开发调试。

## LLM 接入

### 多 Provider 支持

services/llm_client.py 提供统一接口，支持三个 provider：

- DeepSeek API — 默认，成本低、中文效果好
- Claude API — 推理能力强，适合复杂分析场景
- OpenAI API — 兼容备选

通过环境变量切换：

```
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-xxx
LLM_MODEL=deepseek-chat    # 可选覆盖
LLM_ENABLED=true           # false 时降级为规则引擎
```

### 三个调用场景

| 场景 | 策略 | 原因 |
|------|------|------|
| 工单分析 | Structured Output (JSON mode) | 强制返回固定 schema |
| 自动回复 | Streaming API | 流式输出，用户体验好 |
| 工单总结 | 普通 completion | 一次性生成，无需流式 |

### 成本控制

- 主力模型用 DeepSeek，100万 token 几块钱
- 每条 LLM 调用限制 context 长度（知识库只传 top 3）
- LLM_ENABLED=false 可关闭所有 LLM 调用，开发调试时不烧钱

## RAG 检索升级

### 从关键词到语义检索

现有关键词匹配无法处理同义表达（"我的钱能退吗" vs "退款政策"）。升级为 Embedding + 向量相似度检索。

### 技术选型：ChromaDB

- 嵌入式运行，无需独立部署
- 启动时从知识库表读取文档，向量化存入 ChromaDB
- 检索返回 top 3 结果 + 相似度分数

### 检索模式切换

```
RAG_MODE=embedding   # embedding | keyword | hybrid
```

- `embedding`：纯向量检索
- `keyword`：保留原有关键词检索
- `hybrid`：两者结果合并去重，取交集优先

Embedding 模型跟随主力 LLM provider 选择，减少 API Key 数量。

## 流式输出

### SSE 端点

新增 POST /api/tickets/{id}/stream-reply，通过 Server-Sent Events 逐 token 推送前端。

前端回复区域改为打字机效果，逐字显示 AI 回复。

## Tool Calling

Agent 不再只生成文字，可以实际执行操作：

| Tool | 功能 |
|------|------|
| lookup_order(order_id) | 查询订单状态/物流 |
| check_refund_policy() | 查退款规则 |
| get_product_manual(sku) | 查产品说明 |
| escalate_to_human(reason) | 升级人工 |

Agent 工作流变为：分析意图 → 按需调用 Tool 获取数据 → 基于真实数据生成回复。

前端 Agent 工作台展示 Tool 调用链路，让 Agent 行为透明可解释。

## 部署

- 前端：Vercel（免费）
- 后端：Railway 或 Render（免费额度足够 demo）
- 数据库：SQLite → 升级为 Railway 提供的 PostgreSQL（生产环境）
- 可选：Docker Compose 一键启动脚本

## 文件清单

新增文件：
```
backend/services/llm_client.py       # LLM 统一调用客户端
backend/services/llm_analyzer.py     # LLM 版工单分析
backend/services/embedding_service.py # 向量化 + 语义检索
backend/services/reply_generator.py  # LLM 流式回复生成
backend/routes/stream.py             # SSE 流式端点
Dockerfile
docker-compose.yml
```

修改文件：
```
backend/main.py          # 新增流式端点、Tool Calling 逻辑
backend/requirements.txt # 新增 chromadb, openai, anthropic, sse-starlette
frontend/app/...         # 打字机效果、Tool 调用链路展示
```

不变文件（保留兼容）：
```
backend/services/ticket_analyzer.py   # 规则引擎保留
backend/services/knowledge_base.py    # 关键词检索保留
```

## 非目标（本次不做）

- 用户认证/登录系统
- 多知识库隔离
- 对话记忆（多轮上下文管理）
- 生产级监控/日志
- 高并发优化
