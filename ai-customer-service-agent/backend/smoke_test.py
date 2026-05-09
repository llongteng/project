"""Smoke tests for Phase 2 AI analysis module.

Usage:
    python smoke_test.py

Requires the backend server running on http://localhost:8000.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8000"


def request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    # URL-encode query parameters containing non-ASCII chars
    if "?" in path:
        base, qs = path.split("?", 1)
        parts = []
        for p in qs.split("&"):
            if "=" in p:
                k, v = p.split("=", 1)
                parts.append(f"{k}={urllib.parse.quote(v, safe='')}")
            else:
                parts.append(urllib.parse.quote(p, safe=''))
        path = f"{base}?{'&'.join(parts)}"
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read()
        return e.code, json.loads(err_body) if err_body else {}


def ok(cond, msg):
    if cond:
        print(f"  ✅ {msg}")
    else:
        print(f"  ❌ {msg}")
        sys.exit(1)


def header(text):
    print(f"\n── {text} ──")


# ─────────────────────────────────────────────────────────────

header("1. 普通咨询：无需人工，不自动升级")

code, ticket = request("POST", "/api/tickets", {
    "title": "如何查看订单物流信息",
    "customer_name": "测试用户A",
    "customer_email": "a@test.com",
    "category": "product",
    "priority": "low",
    "initial_message": "请问在哪里可以看到我的订单物流状态？谢谢",
})
ok(code == 201, f"创建成功 (201)")
ok(ticket["analysis_status"] == "completed", "分析状态为 completed")
ok(ticket["need_human"] == False, "need_human=False")
ok(ticket["status"] == "pending", "工单状态仍为 pending（未升级）")

msgs = [m["role"] for m in ticket["messages"]]
ok("system" in msgs, "包含 system 消息")
ai_msg = [m for m in ticket["messages"] if "AI 分析完成" in m["content"]]
ok(len(ai_msg) == 1, "有且仅有1条 AI 分析完成消息")
ok("无需人工" in ai_msg[0]["content"], "消息内容含'无需人工'")

normal_id = ticket["id"]

# ─────────────────────────────────────────────────────────────

header("2. 退货退款：检查分析结果")

code, ticket = request("POST", "/api/tickets", {
    "title": "申请退货退款",
    "customer_name": "测试用户B",
    "customer_email": "b@test.com",
    "category": "refund",
    "priority": "medium",
    "initial_message": "收到的商品有质量问题，我要退货退款",
})
ok(code == 201, "创建成功 (201)")
ok(ticket["analysis_status"] == "completed", "分析完成")
ok(ticket["ai_category"] is not None, f"AI分类={ticket['ai_category']}")
ok(ticket["sentiment"] is not None, f"情绪={ticket['sentiment']}")

# ─────────────────────────────────────────────────────────────

header("3. 投诉工单：自动升级人工")

code, ticket = request("POST", "/api/tickets", {
    "title": "客服态度投诉并要求赔偿",
    "customer_name": "测试用户C",
    "customer_email": "c@test.com",
    "category": "complaint",
    "priority": "high",
    "initial_message": "昨天客服态度太差了，还挂我电话，我要投诉！请立刻处理！",
})
ok(code == 201, "创建成功 (201)")
ok(ticket["analysis_status"] == "completed", "分析完成")
ok(ticket["need_human"] == True, "need_human=True")
ok(ticket["status"] == "escalated", "工单已自动升级为 escalated")

ai_msg = [m for m in ticket["messages"] if "AI 分析完成" in m["content"]]
ok(len(ai_msg) >= 1, "包含 AI 分析完成消息")
ok("升级" in ai_msg[-1]["content"], "消息说明已升级人工")

complaint_id = ticket["id"]

# Verify list API returns AI fields
code, tickets = request("GET", "/api/tickets")
ok(code == 200, "列表API正常")
t = next(t for t in tickets if t["id"] == complaint_id)
ok(t.get("sentiment") is not None, "列表项包含 sentiment")
ok(t.get("ai_category") is not None, "列表项包含 ai_category")
ok(t.get("need_human") == True, "列表项 need_human=True")

# ─────────────────────────────────────────────────────────────

header("4. 重新分析：手动触发并验证系统消息")

# First create a ticket that was NOT escalated
code, ticket = request("POST", "/api/tickets", {
    "title": "修改配送地址",
    "customer_name": "测试用户D",
    "customer_email": "d@test.com",
    "category": "order",
    "priority": "low",
    "initial_message": "请问能帮我改一下收货地址吗？",
})
ok(code == 201, "创建成功")
initial_msg_count = len(ticket["messages"])
re_id = ticket["id"]

# Now re-analyze
code, result = request("POST", f"/api/tickets/{re_id}/analyze")
ok(code == 200, "重新分析成功 (200)")
ok(len(result["messages"]) > initial_msg_count, "消息数增加（新增 AI 消息）")

ai_msgs = [m for m in result["messages"] if "重新分析完成" in m["content"]]
ok(len(ai_msgs) >= 1, "新增'重新分析完成'系统消息")

# ─────────────────────────────────────────────────────────────

header("5. 缺失 ID 返回 404")

code, body = request("POST", "/api/tickets/99999/analyze")
ok(code == 404, f"analyze 返回 404 (got {code})")

code, body = request("GET", "/api/tickets/99999")
ok(code == 404, f"GET 不存在的工单 返回 404 (got {code})")

code, body = request("POST", "/api/tickets/99999/messages", {
    "role": "agent",
    "content": "test",
})
ok(code == 404, f"POST message 不存在的工单 返回 404 (got {code})")

# ─────────────────────────────────────────────────────────────

header("6. 知识库 CRUD")

# List
code, entries = request("GET", "/api/knowledge")
ok(code == 200, "列出知识库")
ok(len(entries) >= 7, f"至少有7条种子数据 (got {len(entries)})")

# Search
code, entries = request("GET", "/api/knowledge?search=退款")
ok(code == 200, "搜索退款返回200")
ok(len(entries) >= 1, f"搜索退款有结果 (got {len(entries)})")
ok(any("退款" in e["title"] for e in entries), "结果包含退款相关条目")

# Search with no match
code, entries = request("GET", "/api/knowledge?search=xyzzy不存在的词")
ok(code == 200, "无匹配搜索返回200")
ok(len(entries) == 0, f"无匹配返回空列表 (got {len(entries)})")

# Create
code, entry = request("POST", "/api/knowledge", {
    "title": "smoke测试条目",
    "category": "other",
    "content": "这是smoke测试内容",
    "keywords": "测试,smoke",
})
ok(code == 201, "创建知识条目")
kb_id = entry["id"]

# Update
code, entry = request("PATCH", f"/api/knowledge/{kb_id}", {"title": "smoke已更新"})
ok(code == 200, "更新知识条目")
ok(entry["title"] == "smoke已更新", "标题已更新")

# Toggle disable
code, entry = request("PATCH", f"/api/knowledge/{kb_id}", {"enabled": False})
ok(code == 200, "停用条目")
ok(entry["enabled"] == False, "enabled=false")

# Delete
code, _ = request("DELETE", f"/api/knowledge/{kb_id}")
ok(code == 204, "删除条目返回204")

# KB 404
code, _ = request("DELETE", f"/api/knowledge/{kb_id}")
ok(code == 404, "重复删除返回404")

# ─────────────────────────────────────────────────────────────

header("7. 自动回复")

# Create a normal order ticket
code, ticket = request("POST", "/api/tickets", {
    "title": "查询物流信息",
    "customer_name": "回复测试",
    "customer_email": "reply@test.com",
    "category": "order",
    "priority": "low",
    "initial_message": "我的订单物流怎么查不到",
})
ok(code == 201, "创建工单成功")
reply_id = ticket["id"]

# Trigger auto-reply
code, result = request("POST", f"/api/tickets/{reply_id}/auto-reply")
ok(code == 200, "自动回复成功")
# Now returns TicketDetailResponse (full ticket detail)
ok("id" in result, "返回完整工单详情(含id)")
ok("messages" in result, "返回完整工单详情(含messages)")

# Verify auto-reply saved as agent message
agent_msgs = [m for m in result["messages"] if m["role"] == "agent"]
sys_msgs = [m for m in result["messages"] if "自动回复已生成" in m["content"] or ("命中" in m["content"] and "知识库" in m["content"])]
ok(len(agent_msgs) >= 1, "agent消息已保存")
ok(len(sys_msgs) >= 1, "system消息记录自动回复")

# Verify reply content is meaningful
agent_content = agent_msgs[0]["content"]
ok(len(agent_content) > 20, "回复内容不为空")

# Auto-reply on non-existent ticket
code, _ = request("POST", "/api/tickets/99999/auto-reply")
ok(code == 404, "auto-reply不存在的工单返回404")

# ─────────────────────────────────────────────────────────────

header("8. 知识库搜索 API (/api/knowledge/search)")

# Search with results
code, entries = request("GET", "/api/knowledge/search?q=物流&category=order")
ok(code == 200, f"search?q=物流&category=order 返回200")
ok(len(entries) >= 1, f"搜索结果数>0 (got {len(entries)})")
ok(any("物流" in e["title"] for e in entries), "结果包含物流条目")

# Search with no results
code, entries = request("GET", "/api/knowledge/search?q=xyzzy不存在的词")
ok(code == 200, "无匹配搜索返回200")
ok(len(entries) == 0, "无匹配返回空列表")

# Search across all categories
code, entries = request("GET", "/api/knowledge/search?q=退款")
ok(code == 200, "跨分类搜索退款返回200")
ok(len(entries) >= 1, f"搜索结果数>0 (got {len(entries)})")

# Missing q param → 422
code, _ = request("GET", "/api/knowledge/search")
ok(code == 422, f"缺少q参数返回422 (got {code})")

# ─────────────────────────────────────────────────────────────

header("9. 已解决工单 auto-reply 返回 400")

# Create a ticket then resolve it
code, ticket = request("POST", "/api/tickets", {
    "title": "测试已解决工单",
    "customer_name": "解析测试",
    "customer_email": "resolved@test.com",
    "category": "product",
    "priority": "low",
    "initial_message": "测试消息",
})
ok(code == 201, "创建工单成功")
resolved_id = ticket["id"]

# Set status to resolved
code, _ = request("PATCH", f"/api/tickets/{resolved_id}/status", {"status": "resolved"})
ok(code == 200, "工单状态改为resolved")

# Try auto-reply on resolved ticket
code, body = request("POST", f"/api/tickets/{resolved_id}/auto-reply")
ok(code == 400, f"已解决工单auto-reply返回400 (got {code})")
ok("已解决" in body.get("detail", ""), f"错误信息提及已解决 (got {body.get('detail', '')})")

# ─────────────────────────────────────────────────────────────

header("10. 知识库未命中时自动升级人工")

# Create a ticket with content that won't match any KB
code, ticket = request("POST", "/api/tickets", {
    "title": "星际旅行签证办理咨询",
    "customer_name": "未命中测试",
    "customer_email": "nomatch@test.com",
    "category": "product",
    "priority": "low",
    "initial_message": "请问星际旅行签证需要什么材料，多久能办好",
})
ok(code == 201, "创建工单成功")
nomatch_id = ticket["id"]

# Trigger auto-reply
code, result = request("POST", f"/api/tickets/{nomatch_id}/auto-reply")
ok(code == 200, f"auto-reply返回200 (got {code})")
ok(result["need_human"] == True, "need_human=True（已升级）")
ok(result["status"] == "escalated", f"status=escalated（已升级） (got {result['status']})")

# Verify system message explains no_match
sys_msgs = [m for m in result["messages"] if "no_match" in m["content"].lower() or "未命中" in m["content"]]
ok(len(sys_msgs) >= 1, "system消息包含no_match/未命中说明")

escalate_msg = [m for m in result["messages"] if "升级" in m["content"] and "人工" in m["content"]]
ok(len(escalate_msg) >= 1, "system消息包含升级人工说明")

# ─────────────────────────────────────────────────────────────

header("11. auto-reply 返回完整工单详情")

# Create a ticket that WILL match KB
code, ticket = request("POST", "/api/tickets", {
    "title": "退货流程咨询",
    "customer_name": "完整响应测试",
    "customer_email": "fullresp@test.com",
    "category": "refund",
    "priority": "medium",
    "initial_message": "我想退货退款，请问流程是怎样的？",
})
ok(code == 201, "创建工单成功")
fullresp_id = ticket["id"]

# Trigger auto-reply
code, result = request("POST", f"/api/tickets/{fullresp_id}/auto-reply")
ok(code == 200, "auto-reply返回200")

# Verify it returns full ticket detail fields
ok("id" in result, "响应包含id")
ok("title" in result, "响应包含title")
ok("messages" in result, "响应包含messages列表")
ok("status" in result, "响应包含status")
ok("sentiment" in result, "响应包含sentiment")
ok("ai_category" in result, "响应包含ai_category")
ok("analysis_reason" in result, "响应包含analysis_reason")

# Verify agent message is present
agent_msgs = [m for m in result["messages"] if m["role"] == "agent"]
ok(len(agent_msgs) >= 1, f"工单详情包含agent消息 (got {len(agent_msgs)})")

# Verify system message records KB match info
sys_msgs = [m for m in result["messages"] if m["role"] == "system" and ("命中" in m["content"] or "confidence" in m["content"])]
ok(len(sys_msgs) >= 1, "system消息记录命中知识标题和confidence")

# Verify system message mentions human suggestion
human_msg = [m for m in result["messages"] if "人工" in m["content"] and m["role"] == "system"]
ok(len(human_msg) >= 1, "system消息包含是否建议人工")

# ─────────────────────────────────────────────────────────────

header("12. 工单总结生成与查询")

# Generate summary for a ticket
code, summary = request("POST", f"/api/tickets/{fullresp_id}/summarize")
ok(code == 200, f"生成总结成功 (got {code})")
ok(summary["ticket_id"] == fullresp_id, f"总结ticket_id正确 ({summary['ticket_id']})")
ok(len(summary["summary_text"]) > 50, "总结文本内容充足")
ok(len(summary["problem"]) > 0, "总结包含问题描述")
ok(len(summary["category"]) > 0, "总结包含问题分类")
ok("resolution" in summary, "总结包含处理结果")
ok("need_human" in summary, "总结包含need_human")
ok("knowledge_used" in summary, "总结包含knowledge_used")
ok("escalation_reason" in summary, "总结包含escalation_reason")

# Get summary by ticket ID
code, fetched = request("GET", f"/api/tickets/{fullresp_id}/summary")
ok(code == 200, f"获取总结成功 (got {code})")
ok(fetched["id"] == summary["id"], "获取的总结与生成的总结一致")

# Re-generate should update (upsert), not duplicate
code, summary2 = request("POST", f"/api/tickets/{fullresp_id}/summarize")
ok(code == 200, f"重复生成总结成功 (upsert)")
ok(summary2["id"] == summary["id"], "upsert保持相同ID(更新而非插入)")

# Summary 404 for non-existent ticket
code, _ = request("GET", "/api/tickets/99999/summary")
ok(code == 404, "不存在的工单总结返回404")

# Summarize 404 for non-existent ticket
code, _ = request("POST", "/api/tickets/99999/summarize")
ok(code == 404, "不存在的工单生成总结返回404")

# Also summarize the escalated ticket
code, _ = request("POST", f"/api/tickets/{complaint_id}/summarize")
ok(code == 200, "已升级工单生成总结成功")

# ─────────────────────────────────────────────────────────────

header("13. 运营统计概览")

code, overview = request("GET", "/api/stats/overview")
ok(code == 200, f"统计概览返回200 (got {code})")
ok(overview["total_tickets"] > 0, f"总工单数>0 ({overview['total_tickets']})")
ok("resolved_tickets" in overview, "包含resolved_tickets")
ok("escalated_tickets" in overview, "包含escalated_tickets")
ok("escalation_rate" in overview, "包含escalation_rate")
ok("kb_hit_rate" in overview, "包含kb_hit_rate")
ok("avg_resolution_messages" in overview, "包含avg_resolution_messages")

# ─────────────────────────────────────────────────────────────

header("14. 分类统计")

code, categories = request("GET", "/api/stats/categories")
ok(code == 200, f"分类统计返回200 (got {code})")
ok(len(categories) >= 1, f"至少1个分类 ({len(categories)})")
ok(all("category" in c and "count" in c for c in categories), "每项包含category和count")

# ─────────────────────────────────────────────────────────────

header("15. 升级原因统计")

code, reasons = request("GET", "/api/stats/escalations")
ok(code == 200, f"升级原因返回200 (got {code})")
ok(isinstance(reasons, list), "升级原因返回列表")

# ─────────────────────────────────────────────────────────────

header("16. 知识库缺口统计")

code, gaps = request("GET", "/api/stats/knowledge-gaps")
ok(code == 200, f"知识库缺口返回200 (got {code})")
ok(isinstance(gaps, list), "知识库缺口返回列表")

# ─────────────────────────────────────────────────────────────

header("17. 兼容接口 POST /api/tickets/{id}/summary")

code, summary = request("POST", f"/api/tickets/{fullresp_id}/summary")
ok(code == 200, f"POST /summary 别名返回200 (got {code})")
ok(summary["ticket_id"] == fullresp_id, f"summary别名ticket_id正确 ({summary['ticket_id']})")
ok(len(summary["summary_text"]) > 50, "summary别名返回完整总结文本")

code, _ = request("POST", "/api/tickets/99999/summary")
ok(code == 404, "POST /summary 不存在工单返回404")

# ─────────────────────────────────────────────────────────────

header("18. 兼容接口 /api/analytics/overview")

code, overview = request("GET", "/api/analytics/overview")
ok(code == 200, f"/api/analytics/overview 返回200 (got {code})")
ok(overview["total_tickets"] > 0, f"总工单数>0 ({overview['total_tickets']})")
ok("resolved_tickets" in overview, "包含resolved_tickets")
ok("escalated_tickets" in overview, "包含escalated_tickets")
ok("escalation_rate" in overview, "包含escalation_rate")
ok("kb_hit_rate" in overview, "包含kb_hit_rate")
ok("avg_resolution_messages" in overview, "包含avg_resolution_messages")

# ─────────────────────────────────────────────────────────────

header("19. 兼容接口 /api/analytics/frequent-issues")

code, fi = request("GET", "/api/analytics/frequent-issues")
ok(code == 200, f"/api/analytics/frequent-issues 返回200 (got {code})")
ok("keywords" in fi, "包含keywords字段")
ok("categories" in fi, "包含categories字段")
ok("suggested_kb_gaps" in fi, "包含suggested_kb_gaps字段")
ok(isinstance(fi["keywords"], list), "keywords是列表")
ok(isinstance(fi["categories"], list), "categories是列表")
ok(isinstance(fi["suggested_kb_gaps"], list), "suggested_kb_gaps是列表")

# ─────────────────────────────────────────────────────────────

header("20. 状态变为 resolved 时自动生成总结")

# Create a fresh ticket and resolve it
code, ticket = request("POST", "/api/tickets", {
    "title": "自动总结测试",
    "customer_name": "自动总结用户",
    "customer_email": "autosum@test.com",
    "category": "product",
    "priority": "low",
    "initial_message": "这个产品怎么使用？",
})
ok(code == 201, "创建工单成功")
auto_sum_id = ticket["id"]

# Check no summary exists yet
code, _ = request("GET", f"/api/tickets/{auto_sum_id}/summary")
ok(code == 404, "resolve前无summary")

# Resolve the ticket → should auto-generate summary
code, resolved = request("PATCH", f"/api/tickets/{auto_sum_id}/status", {"status": "resolved"})
ok(code == 200, "状态改为resolved成功")

# Now summary should exist
code, summary = request("GET", f"/api/tickets/{auto_sum_id}/summary")
ok(code == 200, f"resolve后自动生成summary (got {code})")
ok(summary["ticket_id"] == auto_sum_id, f"自动生成的summary ticket_id正确")
ok(summary["final_status"] == "resolved", f"final_status=resolved (got {summary['final_status']})")

# ─────────────────────────────────────────────────────────────

header("21. auto-reply no_match 升级后自动生成总结")

# Create a ticket that won't match KB
code, ticket = request("POST", "/api/tickets", {
    "title": "木星基地设备校验请求",
    "customer_name": "木星测试",
    "customer_email": "jupiter@test.com",
    "category": "product",
    "priority": "low",
    "initial_message": "木星基地通讯设备需要定期校准维护，请提供远程技术方案",
})
ok(code == 201, "创建工单成功")
no_match_id = ticket["id"]

# Check no summary exists yet
code, _ = request("GET", f"/api/tickets/{no_match_id}/summary")
ok(code == 404, "auto-reply前无summary")

# Trigger auto-reply → no_match → escalate → should auto-summarize
code, result = request("POST", f"/api/tickets/{no_match_id}/auto-reply")
ok(code == 200, f"auto-reply返回200 (got {code})")
ok(result["status"] == "escalated", f"status=escalated (got {result['status']})")

# Summary should be auto-generated
code, summary = request("GET", f"/api/tickets/{no_match_id}/summary")
ok(code == 200, f"auto-reply no_match后自动生成summary (got {code})")
ok(summary["ticket_id"] == no_match_id, "自动summary ticket_id正确")
ok(summary["final_status"] == "escalated", f"final_status=escalated (got {summary['final_status']})")
ok(summary["knowledge_used"] == False, "knowledge_used=False（未命中知识库）")

# ─────────────────────────────────────────────────────────────

header("22. Agent 工作流：单个工单完整处理")

code, ticket = request("POST", "/api/tickets", {
    "title": "订单物流一直没有更新",
    "customer_name": "Agent单票测试",
    "customer_email": "agent-one@test.com",
    "category": "order",
    "priority": "low",
    "initial_message": "我的订单物流一直没有更新，请问怎么查看？",
})
ok(code == 201, "创建Agent测试工单成功")
agent_ticket_id = ticket["id"]

code, result = request("POST", f"/api/tickets/{agent_ticket_id}/agent-run")
ok(code == 200, f"第一次agent-run返回200 (got {code})")
ok(result["ticket_id"] == agent_ticket_id, "返回ticket_id正确")
ok(result["status"] in ("waiting_user", "escalated"), f"状态进入处理结果态 ({result['status']})")
ok("完成问题分析" in result["steps"], "步骤包含问题分析")
ok("完成知识库检索" in result["steps"], "步骤包含知识库检索")
ok(result["summary_id"] is not None, "Agent运行后生成summary")

code, summary = request("GET", f"/api/tickets/{agent_ticket_id}/summary")
ok(code == 200, "Agent运行后可查询summary")

# Second run without force should be blocked (idempotency)
code, body = request("POST", f"/api/tickets/{agent_ticket_id}/agent-run")
ok(code == 400, f"第二次agent-run默认被阻止 (got {code})")
ok("已有" in body.get("detail", ""), f"错误信息说明已有处理记录 (got {body.get('detail', '')})")

# Second run with force=true should succeed
code, result2 = request("POST", f"/api/tickets/{agent_ticket_id}/agent-run?force=true")
ok(code == 200, f"force=true允许重跑 (got {code})")
ok(result2["ticket_id"] == agent_ticket_id, "force重跑返回ticket_id正确")

# ─────────────────────────────────────────────────────────────

header("23. Agent 工作流：批量处理待处理工单")

for i in range(2):
    code, _ = request("POST", "/api/tickets", {
        "title": f"批量Agent测试{i + 1}",
        "customer_name": f"批量用户{i + 1}",
        "customer_email": f"agent-batch-{i + 1}@test.com",
        "category": "product",
        "priority": "low",
        "initial_message": "请问产品功能在哪里查看？",
    })
    ok(code == 201, f"创建批量工单{i + 1}成功")

code, batch = request("POST", "/api/agent/batch-run?limit=2")
ok(code == 200, f"batch-run返回200 (got {code})")
ok(batch["processed"] <= 2, f"处理数量不超过limit ({batch['processed']})")
ok(isinstance(batch["results"], list), "results是列表")
ok(all("ticket_id" in item for item in batch["results"]), "每个结果包含ticket_id")

# ─────────────────────────────────────────────────────────────

header("24. auto-reply 命中知识库后状态变为 waiting_user")

code, ticket = request("POST", "/api/tickets", {
    "title": "物流查询测试",
    "customer_name": "状态一致测试",
    "customer_email": "status-test@test.com",
    "category": "order",
    "priority": "low",
    "initial_message": "我的物流信息在哪里查看",
})
ok(code == 201, "创建工单成功")
status_ticket_id = ticket["id"]

code, result = request("POST", f"/api/tickets/{status_ticket_id}/auto-reply")
ok(code == 200, f"auto-reply返回200 (got {code})")
ok(result["status"] in ("waiting_user", "escalated"),
   f"命中KB后状态正确变更 (got {result['status']})")
ok(result["status"] != "pending", "状态不再是pending")

# ─────────────────────────────────────────────────────────────

header("25. 总结 knowledge_used 来自结构化 KB 引用")

code, summary = request("GET", f"/api/tickets/{status_ticket_id}/summary")
ok(code == 200, f"获取总结成功 (got {code})")
# If KB was hit, knowledge_used should be True
kb_hit = result["status"] == "waiting_user" or any(
    m["role"] == "agent" for m in result["messages"]
)
if kb_hit:
    ok(summary["knowledge_used"] == True,
       f"KB命中时knowledge_used=True (got {summary['knowledge_used']})")

# Also verify agent message has source_kb_ids
agent_msgs = [m for m in result["messages"] if m["role"] == "agent"]
if agent_msgs:
    ok("source_kb_ids" in agent_msgs[0], "agent消息包含source_kb_ids字段")

# ─────────────────────────────────────────────────────────────

header("26. 非法 category 返回 422")

code, body = request("POST", "/api/tickets", {
    "title": "测试",
    "customer_name": "校验测试",
    "customer_email": "valid@test.com",
    "category": "invalid_category_xyz",
    "priority": "low",
    "initial_message": "测试非法category",
})
ok(code == 422, f"非法category返回422 (got {code})")

# ─────────────────────────────────────────────────────────────

header("27. 非法 priority 返回 422")

code, body = request("POST", "/api/tickets", {
    "title": "测试",
    "customer_name": "校验测试",
    "customer_email": "valid@test.com",
    "category": "order",
    "priority": "super_high",
    "initial_message": "测试非法priority",
})
ok(code == 422, f"非法priority返回422 (got {code})")

# ─────────────────────────────────────────────────────────────

header("28. 非法 status 返回 422")

code, body = request("PATCH", f"/api/tickets/{status_ticket_id}/status",
                     {"status": "done_and_dusted"})
ok(code == 422, f"非法status返回422 (got {code})")

# ─────────────────────────────────────────────────────────────

header("29. 非法 role 返回 422")

code, body = request("POST", f"/api/tickets/{status_ticket_id}/messages", {
    "role": "super_agent",
    "content": "test",
})
ok(code == 422, f"非法role返回422 (got {code})")

# ─────────────────────────────────────────────────────────────

print(f"\n{'='*50}")
print("全部 smoke test 通过 ✅")
print(f"{'='*50}")
