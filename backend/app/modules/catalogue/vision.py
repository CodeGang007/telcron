"""Reads a product photo with a vision model on an OpenAI-compatible API (Groq's free plan). The ONLY
code that talks to it; replaced wholesale in tests. Its answer is a SUGGESTION for a person to check:
in testing it named the wrong product with 0.9 confidence, so nothing it says is stored unconfirmed."""

import json
from typing import Any

import httpx

from app.core.config import get_settings

PROMPT = """Identify the consumer product in this photo of its packaging or the product itself.
Read the brand, product name and model number printed on it; do not guess what is not visible.
Answer with JSON only: {"brand": str|null, "name": str|null, "model": str|null,
"category": one of [blenders, mini_fridges, window_ac, power_adapters, smartphones, electronics,
appliances, food, household], "confidence": number 0-1, "visible_text": str}"""


class VisionUnavailable(Exception):
    pass


async def read_photo(data_url: str) -> dict[str, Any]:
    s = get_settings()
    if not s.llm_api_key:
        raise VisionUnavailable("no model configured")
    try:
        async with httpx.AsyncClient(base_url=s.llm_base_url, timeout=90) as http:
            response = await http.post("/chat/completions", headers={
                "Authorization": f"Bearer {s.llm_api_key}"}, json={
                "model": s.vision_model, "temperature": 0, "max_completion_tokens": 800,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}}]}]})
            response.raise_for_status()
            answer = json.loads(response.json()["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        raise VisionUnavailable(f"{type(exc).__name__}: {exc}"[:300]) from exc
    return answer if isinstance(answer, dict) else {}
