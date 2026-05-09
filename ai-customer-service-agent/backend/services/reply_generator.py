"""LLM-based streaming reply generator with RAG context."""

import asyncio
import queue
import threading
from typing import AsyncGenerator

from models import KnowledgeBase


class ReplyGenerator:
    SYSTEM_PROMPT = (
        "你是一个专业的客服助手，名叫「小智」。请根据以下规则回复用户：\n"
        "1. 语气亲切、专业、有同理心\n"
        "2. 根据提供的知识库内容回答问题，引用具体信息\n"
        "3. 如果知识库没有相关信息，坦诚告知并建议联系人工客服\n"
        "4. 回复简洁清晰，不超过300字\n"
        "5. 不要编造知识库中没有的信息\n"
    )

    def build_prompt(
        self,
        ticket_title: str,
        analysis: dict,
        kb_entries: list[KnowledgeBase],
    ) -> list[dict]:
        kb_context = ""
        if kb_entries:
            kb_context = "参考知识库内容：\n"
            for i, entry in enumerate(kb_entries[:3], 1):
                kb_context += f"{i}. [{entry.title}] {entry.content[:500]}\n"
        else:
            kb_context = "（暂无匹配的知识库内容，请建议用户等待人工客服处理）\n"

        sentiment = analysis.get("sentiment", "normal")
        sentiment_hint = {
            "angry": "用户情绪激动，请先安抚再解答",
            "complaint": "用户正在投诉，请表达歉意并认真对待",
            "anxious": "用户比较着急，请简洁快速回应",
        }.get(sentiment, "正常回复")

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "system", "content": f"知识库参考：\n{kb_context}"},
            {"role": "system", "content": f"用户情绪提示：{sentiment_hint}"},
            {"role": "user", "content": f"工单标题：{ticket_title}\n请生成客服回复。"},
        ]
        return messages

    async def generate_stream(
        self,
        ticket_title: str,
        analysis: dict,
        kb_entries: list[KnowledgeBase],
    ) -> AsyncGenerator[str, None]:
        from services.llm_client import get_llm_client

        llm = get_llm_client()
        if not llm.available:
            yield "（LLM 未启用，无法生成自动回复。请联系管理员配置 LLM_API_KEY。）"
            return

        messages = self.build_prompt(ticket_title, analysis, kb_entries)
        total_len = sum(len(m["content"]) for m in messages)
        if total_len > llm.max_input_chars:
            overhead = sum(len(m["content"]) for i, m in enumerate(messages) if i != 1)
            max_kb = llm.max_input_chars - overhead - 100
            if max_kb > 0:
                messages[1]["content"] = messages[1]["content"][:max_kb] + "\n..."

        q: queue.Queue = queue.Queue()

        def produce():
            try:
                for token in llm.stream_chat(messages):
                    q.put(("token", token))
                q.put(("done", None))
            except Exception as e:
                q.put(("error", e))

        thread = threading.Thread(target=produce, daemon=True)
        thread.start()
        loop = asyncio.get_event_loop()

        while True:
            event_type, value = await loop.run_in_executor(None, q.get)
            if event_type == "done":
                break
            if event_type == "error":
                raise value
            yield value
            await asyncio.sleep(0)


_instance: ReplyGenerator | None = None


def get_reply_generator() -> ReplyGenerator:
    global _instance
    if _instance is None:
        _instance = ReplyGenerator()
    return _instance
