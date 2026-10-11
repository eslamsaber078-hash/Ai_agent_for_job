"""OpenAI integration with graceful fallbacks.

Every function returns None (or a sensible default) when the API key is
missing or the API call fails, so the app stays fully functional offline.
"""
from __future__ import annotations

import json
import logging

from ..config import OPENAI_API_KEY, OPENAI_MODEL

log = logging.getLogger("jobhunter.ai")

_client = None


def openai_available() -> bool:
    return bool(OPENAI_API_KEY)


def _get_client():
    global _client
    if _client is None and openai_available():
        try:
            from openai import OpenAI

            _client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as exc:  # noqa: BLE001
            log.warning("OpenAI client init failed: %s", exc)
    return _client


def chat_json(system: str, user: str, temperature: float = 0.4) -> dict | None:
    """Call the chat API and return parsed JSON, or None on any failure."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as exc:  # noqa: BLE001
        log.warning("OpenAI call failed (%s), using fallback", exc)
        return None


def chat_text(system: str, user: str, temperature: float = 0.5) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        log.warning("OpenAI call failed (%s), using fallback", exc)
        return None
