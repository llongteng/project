"""Ticket analysis service — rule-based with LLM integration point."""

from models import Sentiment, TicketCategory, TicketPriority


class AnalysisResult:
    def __init__(
        self,
        sentiment: str,
        ai_category: str,
        ai_priority: str,
        need_human: bool,
        reason: str,
    ):
        self.sentiment = sentiment
        self.ai_category = ai_category
        self.ai_priority = ai_priority
        self.need_human = need_human
        self.reason = reason

    def to_dict(self):
        return {
            "sentiment": self.sentiment,
            "ai_category": self.ai_category,
            "ai_priority": self.ai_priority,
            "need_human": self.need_human,
            "analysis_reason": self.reason,
        }


# ─── Rule-based analyzer (no LLM required) ───────────────────────────

SENTIMENT_PATTERNS: list[tuple[Sentiment, list[str]]] = [
    (Sentiment.COMPLAINT, ["投诉", "举报", "曝光", "媒体", "315", "消协"]),
    (Sentiment.ANGRY, ["生气", "非常失望", "太差", "垃圾", "骗子", "坑", "退款到底"]),
    (Sentiment.ANXIOUS, ["急", "尽快", "立刻", "马上", "一直没", "还没", "等了", "为什么还"]),
]

CATEGORY_PATTERNS: list[tuple[TicketCategory, list[str]]] = [
    (TicketCategory.ORDER, ["订单", "物流", "发货", "配送", "签收", "没收到", "运单", "快递"]),
    (TicketCategory.REFUND, ["退款", "退货", "退钱", "申请退", "退差价", "补偿"]),
    (TicketCategory.ACCOUNT, ["账号", "登录", "密码", "被封", "锁定", "验证码", "绑定"]),
    (TicketCategory.PRODUCT, ["怎么", "如何", "说明书", "使用方法", "功能", "在哪里", "找不到"]),
    (TicketCategory.COMPLAINT, ["投诉", "态度差", "挂电话", "等了.*分钟", "人工客服"]),
]

URGENCY_KEYWORDS = ["紧急", "立刻", "马上", "严重", "重大", "损失", "泄露", "安全"]


def _match_sentiment(text: str) -> tuple[Sentiment, list[str]]:
    """Return the most severe matched sentiment and the matches."""
    for sentiment, keywords in SENTIMENT_PATTERNS:
        matched = [kw for kw in keywords if kw in text]
        if matched:
            return sentiment, matched
    return Sentiment.NORMAL, []


def _match_category(text: str) -> tuple[TicketCategory, list[str]]:
    for category, keywords in CATEGORY_PATTERNS:
        matched = [kw for kw in keywords if kw in text]
        if matched:
            return category, matched
    return TicketCategory.OTHER, []


def _infer_priority(sentiment: Sentiment, category: TicketCategory, text: str) -> tuple[TicketPriority, str]:
    urgency_hits = [kw for kw in URGENCY_KEYWORDS if kw in text]

    if sentiment in (Sentiment.COMPLAINT, Sentiment.ANGRY) and urgency_hits:
        return TicketPriority.URGENT, f"负面情绪+紧急关键词: {', '.join(urgency_hits)}"
    if sentiment == Sentiment.COMPLAINT:
        return TicketPriority.HIGH, "用户投诉情绪"
    if sentiment == Sentiment.ANGRY:
        return TicketPriority.HIGH, "用户情绪激动"
    if category == TicketCategory.ACCOUNT and urgency_hits:
        return TicketPriority.HIGH, "账号问题+紧急关键词"
    if urgency_hits:
        return TicketPriority.MEDIUM, f"包含紧急关键词: {', '.join(urgency_hits)}"
    if sentiment == Sentiment.ANXIOUS:
        return TicketPriority.MEDIUM, "用户情绪焦急"
    return TicketPriority.LOW, "常规问题"


def _should_escalate(sentiment: Sentiment, priority: TicketPriority, category: TicketCategory) -> tuple[bool, str]:
    reasons = []
    if sentiment in (Sentiment.COMPLAINT, Sentiment.ANGRY):
        reasons.append("用户情绪负面")
    if priority == TicketPriority.URGENT:
        reasons.append("优先级为紧急")
    if category == TicketCategory.COMPLAINT:
        reasons.append("投诉类问题")
    if reasons:
        return True, "; ".join(reasons)
    return False, "无需升级"


class RuleBasedAnalyzer:
    """Keyword- and rule-based analyzer. No external API needed."""

    def analyze(self, title: str, content: str) -> AnalysisResult:
        text = f"{title} {content}"

        sentiment, s_matches = _match_sentiment(text)
        category, c_matches = _match_category(text)
        priority, p_reason = _infer_priority(sentiment, category, text)
        need_human, h_reason = _should_escalate(sentiment, priority, category)

        reason_parts = []
        if s_matches:
            reason_parts.append(f"情绪匹配关键词: {', '.join(s_matches)} → {sentiment.value}")
        if c_matches:
            reason_parts.append(f"分类匹配关键词: {', '.join(c_matches)} → {category.value}")
        reason_parts.append(f"优先级判定: {p_reason}")
        reason_parts.append(f"升级判定: {h_reason}")

        return AnalysisResult(
            sentiment=sentiment.value,
            ai_category=category.value,
            ai_priority=priority.value,
            need_human=need_human,
            reason="; ".join(reason_parts),
        )


# ─── LLM analyzer (integration point) ────────────────────────────────

class LLMAnalyzer:
    """
    Placeholder for future LLM integration.

    Usage once API key is configured:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("LLM_API_KEY"))
        response = client.chat.completions.create(...)
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def analyze(self, title: str, content: str) -> AnalysisResult:
        from services.llm_client import get_llm_client

        llm = get_llm_client()
        if not llm.available:
            raise RuntimeError("LLM is not enabled")

        text = f"{title} {content}"[: llm.max_input_chars]

        messages = [
            {
                "role": "user",
                "content": (
                    f"分析以下客服工单，返回JSON:\n\n"
                    f"工单标题: {title}\n"
                    f"用户消息: {content}\n"
                ),
            }
        ]

        schema = {
            "type": "object",
            "properties": {
                "sentiment": {
                    "type": "string",
                    "enum": ["normal", "anxious", "angry", "complaint"],
                    "description": "用户情绪",
                },
                "ai_category": {
                    "type": "string",
                    "enum": ["order", "refund", "account", "product", "complaint", "other"],
                    "description": "问题分类",
                },
                "ai_priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "优先级",
                },
                "need_human": {
                    "type": "boolean",
                    "description": "是否需要人工介入",
                },
                "reason": {
                    "type": "string",
                    "description": "分析理由，说明为什么会给出以上结论",
                },
            },
            "required": ["sentiment", "ai_category", "ai_priority", "need_human", "reason"],
        }

        result = llm.chat_structured(messages, schema)

        return AnalysisResult(
            sentiment=result.get("sentiment", "normal"),
            ai_category=result.get("ai_category", "other"),
            ai_priority=result.get("ai_priority", "medium"),
            need_human=result.get("need_human", False),
            reason=result.get("reason", "LLM analysis"),
        )


# ─── Factory ──────────────────────────────────────────────────────────

import os

_analyzer: RuleBasedAnalyzer | LLMAnalyzer | None = None


def get_analyzer():
    """Return LLM analyzer when enabled, otherwise rule-based."""
    global _analyzer
    if _analyzer is None:
        api_key = os.getenv("LLM_API_KEY", "")
        if api_key and os.getenv("LLM_ENABLED", "false").lower() == "true":
            _analyzer = LLMAnalyzer(api_key=api_key, base_url=os.getenv("LLM_BASE_URL"))
        else:
            _analyzer = RuleBasedAnalyzer()
    return _analyzer
