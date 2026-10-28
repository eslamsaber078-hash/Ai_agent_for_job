"""AI integration (OpenAI, free Gemini, free Groq) with graceful fallbacks.

Every function returns None (or a sensible default) when no API key is
configured or the API call fails, so the app stays fully functional offline.
OpenAI is tried first when its key is set, then Gemini, then Groq — the two
free providers alone are enough for the whole app to be AI-powered at no cost.
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from ..config import (GEMINI_API_KEY, GEMINI_MODEL, GROQ_API_KEY, GROQ_MODEL,
                      OPENAI_API_KEY, OPENAI_MODEL)

log = logging.getLogger("jobhunter.ai")

_client = None

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Once Gemini's free daily quota is exhausted, stop asking it (each retry costs
# ~10s of waiting) and let the backup provider answer until the next restart.
_gemini_quota_exhausted = False

# A hung Gemini endpoint used to cost 60s per attempt (three attempts per call), so
# one prepared application could sit for ten minutes. Timeouts are treated as an
# outage: two in a row switch to the backup provider until the next restart.
_gemini_failures = 0
_GEMINI_FAILURES_BEFORE_FALLBACK = 2
_GEMINI_TIMEOUT_SECONDS = 20
_gemini_unreachable = False


def openai_available() -> bool:
    return bool(OPENAI_API_KEY)


def gemini_available() -> bool:
    return bool(GEMINI_API_KEY)


def groq_available() -> bool:
    return bool(GROQ_API_KEY)


def ai_available() -> bool:
    return openai_available() or gemini_available() or groq_available()


def _get_client():
    global _client
    if _client is None and openai_available():
        try:
            from openai import OpenAI

            _client = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as exc:  # noqa: BLE001
            log.warning("OpenAI client init failed: %s", exc)
    return _client


def _openai_chat(messages: list[dict], temperature: float, json_mode: bool) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        kwargs: dict = dict(
            model=OPENAI_MODEL,
            temperature=temperature,
            messages=messages,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as exc:  # noqa: BLE001
        log.warning("OpenAI call failed (%s), falling through to the next provider", exc)
        return None


def _gemini_chat(system: str, user: str, temperature: float, json_mode: bool) -> str | None:
    global _gemini_failures, _gemini_quota_exhausted, _gemini_unreachable
    if not gemini_available() or _gemini_quota_exhausted or _gemini_unreachable:
        return None
    # Older free models (2.5/2.0-flash) were retired by Google and answer 404;
    # trying them only burns latency on the way to the backup provider.
    models = list(dict.fromkeys([GEMINI_MODEL, "gemini-3.8-flash"]))
    for model in models:
        for attempt in range(2):
            try:
                resp = httpx.post(
                    GEMINI_URL.format(model=model),
                    # The key travels in a header so it never appears in request URLs
                    # (httpx logs those at INFO level).
                    headers={"x-goog-api-key": GEMINI_API_KEY},
                    json={
                        "system_instruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": {
                            "temperature": temperature,
                            **({"responseMimeType": "application/json"} if json_mode else {}),
                        },
                    },
                    timeout=_GEMINI_TIMEOUT_SECONDS,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Gemini call failed on %s (%s)", model, exc)
                _gemini_failures += 1
                if _gemini_failures >= _GEMINI_FAILURES_BEFORE_FALLBACK:
                    _gemini_unreachable = True
                    log.warning("Gemini stopped answering; the backup provider takes over until the next restart")
                return None
            if resp.status_code in (429, 503):
                if "quota" in (resp.text or "").lower():
                    # The free daily quota is gone (not a transient overload): no
                    # retry can help, so hand over to the backup provider.
                    log.warning("Gemini's free daily quota is exhausted; the backup provider takes over until the next restart")
                    _gemini_quota_exhausted = True
                    return None
                # The free tier is often overloaded; Google asks callers to retry.
                log.warning("Gemini %s is overloaded (HTTP %s), retrying", model, resp.status_code)
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code != 200:
                log.warning("Gemini call failed on %s (HTTP %s: %s)",
                            model, resp.status_code, resp.text[:200])
                break
            try:
                payload = resp.json()
                parts = payload["candidates"][0]["content"]["parts"]
                if not isinstance(parts, list):
                    raise TypeError("parts is not a list")
            except (KeyError, IndexError, TypeError, ValueError):
                # A safety block or an empty candidates list is still HTTP 200; it
                # must fall through to the template, not crash the request.
                log.warning("Gemini returned an unreadable reply on %s", model)
                break
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            if text.strip():
                _gemini_failures = 0
                return text
            log.warning("Gemini returned an empty reply on %s", model)
            break
    log.warning("Gemini unavailable, using fallback")
    _gemini_failures += 1
    if _gemini_failures >= _GEMINI_FAILURES_BEFORE_FALLBACK:
        _gemini_unreachable = True
        log.warning("Gemini stopped answering; the backup provider takes over until the next restart")
    return None


def _groq_chat(system: str, user: str, temperature: float, json_mode: bool) -> str | None:
    if not groq_available():
        return None
    models = list(dict.fromkeys([GROQ_MODEL, "qwen/qwen3.8-27b", "openai/gpt-oss-120b", "allam-2-7b"]))
    for model in models:
        for attempt in range(3):
            payload = {
                "model": model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            try:
                resp = httpx.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json=payload,
                    timeout=30,
                )
            except Exception as exc:  # noqa: BLE001
                # A timeout/connection error hits every model on this endpoint, so
                # waiting on the rest only delays the template fallback.
                log.warning("Groq call failed on %s (%s)", model, exc)
                return None
            if resp.status_code in (429, 503):
                log.warning("Groq %s is overloaded (HTTP %s), retrying", model, resp.status_code)
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code != 200:
                log.warning("Groq call failed on %s (HTTP %s: %s)",
                            model, resp.status_code, resp.text[:200])
                break
            try:
                text = resp.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError):
                log.warning("Groq returned an unreadable reply on %s", model)
                break
            if (text or "").strip():
                return text
            log.warning("Groq returned an empty reply on %s", model)
            break
    log.warning("Groq unavailable, using fallback")
    return None


def _chat(system: str, user: str, temperature: float, json_mode: bool) -> str | None:
    text = _openai_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature, json_mode)
    if text is not None:
        return text
    text = _gemini_chat(system, user, temperature, json_mode)
    if text is not None:
        return text
    return _groq_chat(system, user, temperature, json_mode)


def chat_json(system: str, user: str, temperature: float = 0.4) -> dict | None:
    """Call the chat API and return parsed JSON, or None on any failure."""
    raw = _chat(system, user, temperature, json_mode=True)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("AI reply was not valid JSON (%s)", exc)
        return None


def chat_text(system: str, user: str, temperature: float = 0.5) -> str | None:
    return _chat(system, user, temperature, json_mode=False)
