# AI 客服工单处理 Agent

一个面向电商 / SaaS 场景的 AI Native 客服工单处理系统。系统通过大语言模型、RAG 知识库检索、工具调用和工单状态流转，实现用户问题识别、自动回复生成、复杂问题升级人工、工单总结与高频问题分析。

该项目旨在模拟真实企业客服场景，展示 AI Agent 在业务流程自动化中的应用能力。

## 项目背景

在真实客服系统中，大量用户问题具有重复性，例如订单查询、退款规则、账号登录、产品使用说明等。传统客服系统依赖人工分类、检索知识库和撰写回复，效率较低。

本项目尝试构建一个 AI 客服 Agent，使其能够：

- 自动理解用户问题
- 判断问题类型和紧急程度
- 从知识库中检索相关答案
- 生成可直接发送的客服回复
- 对复杂或高风险问题升级人工
- 自动总结工单处理过程
- 统计高频问题，帮助企业优化产品和知识库

## 核心功能

### 1. 工单创建与管理

- 用户提交问题后自动生成工单
- 支持工单状态流转：
  - 待处理
  - AI处理中
  - 等待用户回复
  - 已解决
  - 已升级人工
- 支持按状态、问题类型、优先级筛选工单

### 2. 用户问题理解

系统会对用户输入进行结构化分析：

- 问题类型识别
  - 订单问题
  - 退款 / 售后
  - 账号问题
  - 产品使用问题
  - 投诉建议
  - 其他问题
- 用户情绪识别
  - 正常
  - 焦急
  - 生气
  - 严重投诉
- 优先级判断
  - 低
  - 中
  - 高
  - 紧急

### 3. RAG 知识库问答

系统内置客服知识库，支持基于知识库生成回复。

知识库内容可以包括：

- 常见问题 FAQ
- 退款政策
- 物流规则
- 账号安全说明
- 产品使用文档
- 售后服务流程

Agent 在回复用户时，需要先检索相关知识，再结合用户问题生成回答，避免纯模型幻觉。

### 4. AI 自动回复生成

系统根据用户问题、工单上下文和知识库检索结果，生成客服回复。

回复要求：

- 语气礼貌、专业
- 回答具体，可操作
- 不编造知识库中不存在的政策
- 对无法确定的问题主动升级人工
- 对负面情绪用户使用安抚性表达

### 5. 人工升级机制

当系统判断问题复杂、高风险或知识库无法覆盖时，会自动升级人工。

典型升级场景：

- 用户强烈投诉
- 涉及金额争议
- 知识库检索结果置信度低
- 用户连续多轮未解决
- 涉及隐私、安全、法律风险

### 6. 工单总结

每个工单结束后，系统自动生成结构化总结：

- 用户核心问题
- AI 处理过程
- 最终解决方案
- 是否升级人工
- 用户情绪变化
- 可沉淀为知识库的内容

### 7. 高频问题分析

系统统计一段时间内的工单数据，输出：

- 高频问题类型
- 高频关键词
- 未解决问题分布
- 人工升级原因统计
- 知识库缺失建议

## 技术栈

### 前端

- React / Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui

### 后端

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL

### AI / Agent

- OpenAI API / Claude API / DeepSeek API / Qwen API
- LangChain / LlamaIndex / 自研 Agent 流程
- Function Calling / Tool Calling
- Prompt Engineering
- Structured Output

### 检索与存储

- PostgreSQL
- pgvector / Qdrant / Milvus
- Embedding Model
- 文档切分与向量化

### 部署

- Docker
- Docker Compose
- Nginx
- 云服务器部署

## 系统架构

```text
用户提交问题
    |
    v
工单系统创建 Ticket
    |
    v
AI Agent 分析问题
    |
    +--> 意图分类
    +--> 情绪识别
    +--> 优先级判断
    |
    v
知识库 RAG 检索
    |
    v
回复生成 / 工具调用 / 人工升级判断
    |
    v
更新工单状态
    |
    v
生成工单总结与统计数据
```

## 本地启动（第一阶段）

### 环境要求

- Python 3.10+
- Node.js 18+

### 1. 启动后端

```bash
cd backend
pip install -r requirements.txt
python seed.py          # 初始化数据库和种子数据
uvicorn main:app --reload --port 8000
```

后端运行在 http://localhost:8000

API 文档: http://localhost:8000/docs

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 http://localhost:3000

### 第一阶段完成功能

- [x] 工单创建（支持分类和优先级）
- [x] 工单列表（支持按状态筛选）
- [x] 工单详情（含消息记录）
- [x] 工单状态流转
- [x] 客服回复消息
- [x] 种子数据（5个示例工单）

## 第二阶段：AI 问题分析模块

### 新增功能

- **自动分析**：创建工单时自动对用户问题进行结构化分析
- **手动分析**：支持对已有工单重新触发 AI 分析
- **情绪识别**：基于关键词匹配，识别用户情绪（正常/焦急/生气/严重投诉）
- **问题分类**：AI 判断问题类型（订单/退款/账号/产品使用/投诉/其他）
- **优先级判断**：AI 推断优先级（低/中/高/紧急）
- **人工升级建议**：自动判断是否需要人工介入
- **前端分析面板**：工单详情页展示 AI 分析结果

### 分析策略

当前使用**规则引擎**（关键词匹配）进行分析，不依赖任何大模型 API。规则定义在 `backend/services/ticket_analyzer.py`。

已预留 LLM 接入接口 `LLMAnalyzer`，接入后只需配置环境变量即可切换为真实大模型分析。

### 验证方式

```bash
# 创建含投诉关键词的工单，观察自动分析结果
curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"订单一直没发货我要投诉","customer_name":"用户","customer_email":"u@t.com","category":"order","priority":"high","initial_message":"三天了还不发货，太差了，投诉！立刻处理！"}'

# 手动对已有工单触发分析
curl -s -X POST http://localhost:8000/api/tickets/1/analyze

# 查看工单详情中的分析字段
curl -s http://localhost:8000/api/tickets/6 | python3 -m json.tool
```

前端访问 http://localhost:3000/tickets/6 查看分析面板。

### 第二阶段完成功能

- [x] Ticket 模型扩展 AI 分析字段（sentiment, ai_category, ai_priority, need_human, analysis_reason, analysis_status, analyzed_at）
- [x] 规则引擎分析服务（零依赖，无 API Key 也能运行）
- [x] 创建工单时自动触发分析
- [x] POST /api/tickets/{id}/analyze 手动分析端点
- [x] 前端分析面板（情绪、AI分类、AI优先级、人工建议、分析理由）
- [x] 预留 LLMAnalyzer 接口（未来接入大模型）
- [x] 非法输入 400 错误处理

## 第三阶段：轻量知识库与自动回复

### 新增功能

- **知识库管理**：CRUD 接口 + 前端管理页面，支持搜索、分类筛选、启用/停用
- **关键词检索**：基于关键词 + 标题 + 正文的评分检索，无需向量数据库
- **自动回复**：POST /api/tickets/{id}/auto-reply，结合 AI 分析 + 知识库检索 + 情绪安抚生成回复
- **回复来源追溯**：自动回复标注引用的知识条目
- **种子 FAQ**：预置 8 条知识条目覆盖订单/退款/账号/产品/投诉场景

### 知识库搜索策略

纯 SQLite 关键词匹配，不引入向量数据库：

1. 关键词字段匹配（权重 3）—— comma/space 分隔
2. 标题全文匹配（权重 2）
3. 正文单词出现次数（权重 0.5/次）

仅返回得分 > 0 的条目，按得分排序。

### 新增 API

```
GET    /api/knowledge                  知识库列表（支持 ?search=&category=）
POST   /api/knowledge                  创建知识条目
PATCH  /api/knowledge/{id}             更新知识条目（含启用/停用）
DELETE /api/knowledge/{id}             删除知识条目
POST   /api/tickets/{id}/auto-reply    生成自动回复（保存为agent消息）
```

### 前端页面

- `/knowledge` —— 知识库管理页（搜索、增删改查、启用/停用）
- 工单详情页新增「AI 自动回复」按钮，展示引用知识库来源

### 验证方式

```bash
# 运行 smoke test
cd backend && python smoke_test.py

# 搜索知识库
curl "http://localhost:8000/api/knowledge?search=退款"

# 对工单触发自动回复
curl -X POST http://localhost:8000/api/tickets/1/auto-reply
```

### 第三阶段完成功能

- [x] KnowledgeBase 数据模型（id, title, category, content, keywords, enabled）
- [x] 种子 FAQ 数据（8 条，覆盖订单/退款/账号/产品/投诉）
- [x] 关键词评分检索（无向量数据库）
- [x] 知识库前端管理页（CRUD + 搜索）
- [x] 自动回复端点（分析 + 检索 + 生成回复 + 保存消息）
- [x] 前端自动回复按钮 + 来源展示
- [x] smoke test 覆盖（40+ 断言，7 个场景）
- [x] 零外部依赖，无 API Key 完整可运行

## 第四阶段：工单总结与运营统计分析

### 新增功能

- **工单总结**：POST /api/tickets/{id}/summarize，基于规则/模板生成结构化总结（不依赖 LLM API）
- **总结字段**：problem、category、sentiment、resolution、final_status、need_human、escalation_reason、knowledge_used、summary_text
- **Upsert 策略**：重复生成不会产生重复记录，而是更新已有总结（ticket_id UNIQUE 约束）
- **总结查询**：GET /api/tickets/{id}/summary，获取已有总结，无总结时返回 404
- **运营统计概览**：GET /api/stats/overview —— 总工单数、已解决、已升级、升级率、知识库命中率、平均消息数
- **分类统计**：GET /api/stats/categories —— 各问题分类的工单数量分布
- **升级原因统计**：GET /api/stats/escalations —— 人工升级原因 Top 10
- **知识库缺口**：GET /api/stats/knowledge-gaps —— 知识库未覆盖的高频问题 Top 10
- **前端总结面板**：工单详情页新增「生成总结」按钮和总结展示区
- **前端统计仪表盘**：/stats 页面展示概览卡片、分类分布柱状图、升级原因表、知识库缺口表
- **导航扩展**：顶部导航新增「运营统计」入口

### 总结生成策略

纯规则/模板生成，不依赖 LLM API：

1. 从第一条 user 消息提取问题描述
2. 从最后一条 agent 消息提取处理结果
3. 从 ticket 字段提取分类、情绪、状态
4. 检测 system 消息中是否引用知识库，判定 knowledge_used
5. 从 analysis_reason 和字段组合判定 escalation_reason
6. 组合所有信息生成 summary_text

### 新增 API

```
POST   /api/tickets/{id}/summarize      生成/更新工单总结
GET    /api/tickets/{id}/summary        获取工单总结
GET    /api/stats/overview              运营统计概览
GET    /api/stats/categories            问题分类分布
GET    /api/stats/escalations           升级原因统计
GET    /api/stats/knowledge-gaps        知识库缺口
```

### 前端页面

- 工单详情页新增「工单总结」面板（生成按钮 + 总结展示）
- `/stats` —— 运营统计仪表盘（概览卡片 + 分类分布 + 升级原因 + 知识库缺口）

### 验证方式

```bash
# 运行完整 smoke test（含第四阶段 5 个新场景）
cd backend && python smoke_test.py

# 生成工单总结
curl -X POST http://localhost:8000/api/tickets/1/summarize | python3 -m json.tool

# 查看已有总结
curl http://localhost:8000/api/tickets/1/summary | python3 -m json.tool

# 查看运营统计概览
curl http://localhost:8000/api/stats/overview | python3 -m json.tool

# 查看分类统计
curl http://localhost:8000/api/stats/categories | python3 -m json.tool

# 查看知识库缺口
curl http://localhost:8000/api/stats/knowledge-gaps | python3 -m json.tool
```

前端访问：
- http://localhost:3000/tickets/1 —— 点击「生成总结」查看工单总结面板
- http://localhost:3000/stats —— 运营统计仪表盘

### 第四阶段完成功能

- [x] TicketSummary 数据模型（id, ticket_id UNIQUE, problem, category, sentiment, resolution, final_status, need_human, escalation_reason, knowledge_used, summary_text）
- [x] 规则模板总结服务 backend/services/ticket_summarizer.py
- [x] POST /api/tickets/{id}/summarize 生成/更新总结（upsert）
- [x] GET /api/tickets/{id}/summary 查询总结
- [x] GET /api/stats/overview 运营统计概览
- [x] GET /api/stats/categories 分类分布
- [x] GET /api/stats/escalations 升级原因
- [x] GET /api/stats/knowledge-gaps 知识库缺口
- [x] 前端总结面板（生成按钮 + 总结展示）
- [x] 前端运营统计仪表盘 /stats
- [x] 顶部导航新增「运营统计」
- [x] smoke test 16 个场景全部通过
- [x] 零外部依赖，无 LLM API Key 完整可运行

## 第五阶段：Agent 工作流编排与批量处理

### 新增功能

- **单票 Agent 运行**：POST /api/tickets/{id}/agent-run，一键串联分析、知识库检索、自动回复/人工升级、工单总结
- **批量 Agent 处理**：POST /api/agent/batch-run，按队列处理待处理工单，支持 limit 参数
- **工作流状态记录**：运行时写入 system 消息，保留 Agent 启动、知识库命中、升级人工等关键动作
- **动作结果返回**：返回 action、kb_hit、kb_sources、summary_id、steps，方便前端展示执行轨迹
- **Agent 工作台页面**：/agent 展示待处理队列，支持单票运行和批量处理
- **工单详情页入口**：工单详情页新增「Agent 工作流」面板，可直接运行完整流程
- **自动总结衔接**：Agent 运行后自动生成/更新工单总结，供统计和复盘使用

### 工作流策略

当前仍保持零外部依赖，使用规则引擎和轻量知识库：

1. 将工单状态切换为 AI处理中
2. 对首条用户消息执行结构化分析
3. 使用问题标题 + 用户消息检索知识库
4. 命中知识库时生成客服回复
5. 若需人工或未命中知识库，则升级人工
6. 生成/更新工单总结
7. 返回完整执行步骤

### 新增 API

```
POST   /api/tickets/{id}/agent-run      运行单个工单 Agent 工作流
POST   /api/agent/batch-run?limit=5     批量运行待处理工单 Agent 工作流
```

### 前端页面

- `/agent` —— Agent 工作台（待处理队列、单票运行、批量处理、最近运行结果）
- 工单详情页新增「Agent 工作流」面板

### 验证方式

```bash
# 运行完整 smoke test（含第五阶段 Agent 工作流场景）
cd backend && python smoke_test.py

# 运行单个工单 Agent
curl -X POST http://localhost:8000/api/tickets/1/agent-run | python3 -m json.tool

# 批量处理待处理工单
curl -X POST "http://localhost:8000/api/agent/batch-run?limit=5" | python3 -m json.tool
```

前端访问：
- http://localhost:3000/agent —— Agent 工作台
- http://localhost:3000/tickets/1 —— 在详情页运行完整 Agent 流程

### 第五阶段完成功能

- [x] POST /api/tickets/{id}/agent-run 单票 Agent 编排接口
- [x] POST /api/agent/batch-run 批量 Agent 处理接口
- [x] AgentRunResult / BatchAgentRunResponse 响应结构
- [x] Agent 工作流自动写入 system 消息
- [x] 命中知识库后生成自动回复并进入等待用户回复
- [x] 未命中知识库或高风险问题自动升级人工
- [x] Agent 运行后自动生成/更新工单总结
- [x] 前端 /agent 工作台
- [x] 工单详情页 Agent 工作流面板
- [x] smoke test 新增 Agent 单票和批量处理场景
