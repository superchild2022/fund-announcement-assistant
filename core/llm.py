from __future__ import annotations

import json
import re
import time
from typing import Any

from openai import OpenAI

from .config import get_api_key, get_base_url, get_model, get_thinking


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty response")
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(text[start : end + 1])


def chat_json(
    system_prompt: str,
    user_prompt: str,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8192,
    max_retries: int = 2,
) -> tuple[dict | None, dict]:
    key = (api_key or get_api_key()).strip()
    if not key:
        return None, {"ok": False, "error": "未配置 DEEPSEEK_API_KEY"}

    client = OpenAI(api_key=key, base_url=get_base_url(), timeout=120.0)
    last_error = ""
    last_raw = ""
    last_reasoning = ""
    last_finish = None
    started = time.time()

    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model or get_model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                extra_body={
                    "thinking": {
                        "type": "enabled" if get_thinking() == "enabled" else "disabled"
                    }
                },
            )
            message = resp.choices[0].message
            content = message.content or ""
            reasoning = getattr(message, "reasoning_content", None) or ""
            last_raw = content
            last_reasoning = reasoning
            last_finish = resp.choices[0].finish_reason
            # deepseek-flash 是推理模型，正常情况下 content 是最终 JSON；
            # 若 content 为空但 reasoning 中有 JSON，做一次兜底解析。
            parse_source = content if content.strip() else reasoning
            data = _extract_json(parse_source)
            usage = getattr(resp, "usage", None)
            meta = {
                "ok": True,
                "model": model or get_model(),
                "latency_s": round(time.time() - started, 2),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
                "reasoning_chars": len(reasoning),
                "finish_reason": last_finish,
                "attempts": attempt + 1,
                "raw_preview": content[:1200],
            }
            return data, meta
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < max_retries:
                time.sleep(1.2 * (attempt + 1))

    return None, {
        "ok": False,
        "model": model or get_model(),
        "latency_s": round(time.time() - started, 2),
        "attempts": max_retries + 1,
        "error": last_error,
        "finish_reason": last_finish,
        "reasoning_chars": len(last_reasoning),
        "raw_preview": last_raw[:1200],
        "reasoning_preview": last_reasoning[:600],
    }


def health_check(api_key: str | None = None) -> dict:
    data, meta = chat_json(
        "你是一个连通性测试助手。只输出 JSON。",
        '请输出 {"status":"ok","message":"connected"}',
        api_key=api_key,
        max_tokens=1024,
        max_retries=0,
    )
    if data and data.get("status") == "ok":
        return {"ok": True, "meta": meta}
    return {"ok": False, "meta": meta, "data": data}
