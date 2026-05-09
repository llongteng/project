"""Unified LLM client — openai-compatible protocol (DeepSeek default)."""

import json
import os
import time
import logging
from typing import Generator

from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")
        self.enabled = os.getenv("LLM_ENABLED", "false").lower() == "true"
        self.timeout = int(os.getenv("LLM_TIMEOUT", "30"))
        self.max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.max_input_chars = int(os.getenv("LLM_MAX_INPUT_CHARS", "4000"))
        self.max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1024"))
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)

    @property
    def available(self) -> bool:
        return self.enabled and self.client is not None

    def _retry_sleep(self, attempt: int):
        time.sleep(1 * (attempt + 1))

    def chat(self, messages: list[dict], stream: bool = False, **kwargs):
        if not self.available:
            raise RuntimeError("LLM is not enabled or API key is not configured")
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_output_tokens),
            "temperature": kwargs.get("temperature", 0.3),
            "stream": stream,
        }
        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                return self.client.chat.completions.create(**params)
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    logger.warning("LLM call failed (attempt %d): %s, retrying...", attempt + 1, e)
                    self._retry_sleep(attempt)
        raise last_err

    def chat_structured(self, messages: list[dict], schema: dict) -> dict:
        if not self.available:
            raise RuntimeError("LLM is not enabled")

        schema_prompt = json.dumps(schema, ensure_ascii=False)
        system_msg = {
            "role": "system",
            "content": (
                f"You must respond with a valid JSON object matching this schema:\n"
                f"{schema_prompt}\n"
                f"Do not include any text outside the JSON object."
            ),
        }
        msgs = [system_msg] + messages

        last_err = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=msgs,
                    max_tokens=self.max_output_tokens,
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content.strip()
                return json.loads(raw)
            except json.JSONDecodeError as e:
                last_err = e
                if attempt < self.max_retries:
                    logger.warning("JSON parse failed (attempt %d): %s, retrying...", attempt + 1, e)
                    self._retry_sleep(attempt)
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    logger.warning("Structured chat failed (attempt %d): %s, retrying...", attempt + 1, e)
                    self._retry_sleep(attempt)

        raise ValueError(f"Failed to parse structured output after {self.max_retries + 1} attempts: {last_err}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.available:
            raise RuntimeError("LLM is not enabled")
        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [d.embedding for d in response.data]

    def stream_chat(self, messages: list[dict]) -> Generator[str, None, None]:
        """Generator yielding content tokens from a streaming chat completion."""
        if not self.available:
            raise RuntimeError("LLM is not enabled")
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_output_tokens,
            temperature=0.3,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


_llm_instance: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMClient()
    return _llm_instance
