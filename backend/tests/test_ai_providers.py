"""Unit tests for the AI provider layer (OpenAI + free Gemini + free Groq) with
all network access faked — tests must never hit the real internet."""


def test_chat_text_falls_through_to_gemini(monkeypatch):
    from app.services import ai as ai_mod

    monkeypatch.setattr(ai_mod, "_openai_chat", lambda *a, **k: None)
    monkeypatch.setattr(ai_mod, "_gemini_chat", lambda *a, **k: "gemini reply")
    assert ai_mod.chat_text("s", "u") == "gemini reply"


def test_chat_text_falls_through_to_groq_when_gemini_is_out(monkeypatch):
    # Gemini's free daily quota runs out every day; the app must then land on Groq
    # instead of giving up and falling back to the templates.
    from app.services import ai as ai_mod

    monkeypatch.setattr(ai_mod, "_openai_chat", lambda *a, **k: None)
    monkeypatch.setattr(ai_mod, "_gemini_chat", lambda *a, **k: None)
    monkeypatch.setattr(ai_mod, "_groq_chat", lambda *a, **k: "groq reply")
    assert ai_mod.chat_text("s", "u") == "groq reply"


def test_groq_chat_sends_bearer_auth_and_the_openai_shaped_body(monkeypatch):
    from app.services import ai as ai_mod

    captured = {}

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "hello from groq"}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        captured["json"] = kwargs["json"]
        return FakeResp()

    monkeypatch.setattr(ai_mod, "GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(ai_mod, "GROQ_MODEL", "qwen/qwen3.8-27b")
    monkeypatch.setattr(ai_mod.httpx, "post", fake_post)
    out = ai_mod._groq_chat("sys-prompt", "user-prompt", 0.4, json_mode=True)
    assert out == "hello from groq"
    assert captured["url"] == ai_mod.GROQ_URL
    assert captured["headers"]["Authorization"] == "Bearer gsk-test"
    body = captured["json"]
    assert body["model"] == "qwen/qwen3.8-27b"
    assert body["messages"][0] == {"role": "system", "content": "sys-prompt"}
    assert body["response_format"] == {"type": "json_object"}


def test_groq_retries_when_the_free_tier_is_overloaded(monkeypatch):
    from app.services import ai as ai_mod

    calls = {"n": 0}

    class Overloaded:
        status_code = 429
        text = "rate limited"

    class Ok:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "finally a reply"}}]}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        return Ok() if calls["n"] >= 2 else Overloaded()

    monkeypatch.setattr(ai_mod, "GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(ai_mod, "GROQ_MODEL", "qwen/qwen3.8-27b")
    monkeypatch.setattr(ai_mod, "time", type("T", (), {"sleep": lambda *a: None})())
    monkeypatch.setattr(ai_mod.httpx, "post", fake_post)
    assert ai_mod._groq_chat("s", "u", 0.4, json_mode=False) == "finally a reply"
    assert calls["n"] == 2


def test_groq_moves_to_the_next_model_when_one_is_unavailable(monkeypatch):
    from app.services import ai as ai_mod

    class FakeResp:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = "error body"

        def json(self):
            return {"choices": [{"message": {"content": "hello from the fallback model"}}]}

    seen = []

    def fake_post(url, **kwargs):
        seen.append(kwargs["json"]["model"])
        return FakeResp(200) if kwargs["json"]["model"] == "qwen/qwen3.8-27b" else FakeResp(404)

    monkeypatch.setattr(ai_mod, "GROQ_API_KEY", "gsk-test")
    monkeypatch.setattr(ai_mod, "GROQ_MODEL", "a-model-that-no-longer-exists")
    monkeypatch.setattr(ai_mod.httpx, "post", fake_post)
    assert ai_mod._groq_chat("sys", "user", 0.4, json_mode=False) == "hello from the fallback model"
    assert seen == ["a-model-that-no-longer-exists", "qwen/qwen3.8-27b"]


def test_chat_json_prefers_the_openai_result(monkeypatch):
    from app.services import ai as ai_mod

    monkeypatch.setattr(ai_mod, "_openai_chat", lambda *a, **k: '{"x": 1}')
    monkeypatch.setattr(ai_mod, "_gemini_chat", lambda *a, **k: "not called")
    assert ai_mod.chat_json("s", "u") == {"x": 1}


def test_gemini_moves_to_the_next_model_when_one_is_unavailable(monkeypatch):
    from app.services import ai as ai_mod

    class FakeResp:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = "error body"

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "hello from gemini"}]}}]}

    seen = []

    def fake_post(url, **kwargs):
        seen.append(url)
        return FakeResp(200) if "gemini-3.8-flash" in url else FakeResp(404)

    monkeypatch.setattr(ai_mod, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai_mod, "GEMINI_MODEL", "a-model-google-retired")
    monkeypatch.setattr(ai_mod.httpx, "post", fake_post)
    assert ai_mod._gemini_chat("sys", "user", 0.4, json_mode=False) == "hello from gemini"
    assert len(seen) == 2


def test_gemini_sends_the_system_instruction_and_json_mode(monkeypatch):
    from app.services import ai as ai_mod

    captured = {}

    class FakeResp:
        status_code = 200
        text = ""

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "{\"ok\": true}"}]}}]}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs["headers"]
        captured["json"] = kwargs["json"]
        return FakeResp()

    monkeypatch.setattr(ai_mod, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai_mod, "GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(ai_mod.httpx, "post", fake_post)
    out = ai_mod._gemini_chat("sys-prompt", "user-prompt", 0.4, json_mode=True)
    assert out == '{"ok": true}'
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert "key=" not in captured["url"]
    body = captured["json"]
    assert body["system_instruction"]["parts"][0]["text"] == "sys-prompt"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["temperature"] == 0.4


def test_gemini_retries_when_the_free_tier_is_overloaded(monkeypatch):
    # The free Gemini tier answers 503 under load; one failed attempt must not
    # throw the user back to the template.
    from app.services import ai as ai_mod

    calls = {"n": 0}

    class Overloaded:
        status_code = 503
        text = "overloaded"

    class Ok:
        status_code = 200
        text = ""

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "finally a reply"}]}}]}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        return Ok() if calls["n"] >= 2 else Overloaded()

    monkeypatch.setattr(ai_mod, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai_mod, "GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(ai_mod, "time", type("T", (), {"sleep": lambda *a: None})())
    monkeypatch.setattr(ai_mod.httpx, "post", fake_post)
    assert ai_mod._gemini_chat("s", "u", 0.4, json_mode=False) == "finally a reply"
    assert calls["n"] == 2


def test_gemini_network_failures_switch_to_the_backup(monkeypatch):
    # A hung Gemini endpoint used to cost 60s per attempt; two failed calls must
    # take it out of rotation so the user is not left waiting minutes.
    from app.services import ai as ai_mod

    monkeypatch.setattr(ai_mod, "_gemini_quota_exhausted", False)
    monkeypatch.setattr(ai_mod, "_gemini_unreachable", False)
    monkeypatch.setattr(ai_mod, "_gemini_failures", 0)
    monkeypatch.setattr(ai_mod, "GEMINI_API_KEY", "test-key")
    calls = {"n": 0}

    def boom(url, **kwargs):
        calls["n"] += 1
        raise ai_mod.httpx.TimeoutException("timed out")

    monkeypatch.setattr(ai_mod.httpx, "post", boom)
    assert ai_mod._gemini_chat("s", "u", 0.4, json_mode=False) is None
    assert calls["n"] == 1
    assert ai_mod._gemini_chat("s", "u", 0.4, json_mode=False) is None
    assert calls["n"] == 2
    assert ai_mod._gemini_unreachable is True
    # Later calls reach the backup provider without waiting on Gemini again.
    assert ai_mod._gemini_chat("s", "u", 0.4, json_mode=False) is None
    assert calls["n"] == 2


def test_gemini_is_skipped_for_the_rest_of_the_day_after_its_quota_is_exhausted(monkeypatch):
    # When the daily quota is gone, retrying Gemini only wastes ~10s per call.
    # One quota answer must switch the app to the backup provider for good.
    from app.services import ai as ai_mod

    monkeypatch.setattr(ai_mod, "_gemini_quota_exhausted", False)
    monkeypatch.setattr(ai_mod, "_gemini_unreachable", False)
    monkeypatch.setattr(ai_mod, "_gemini_failures", 0)
    calls = {"n": 0}

    class QuotaOut:
        status_code = 429
        text = "You exceeded your current quota, please check your plan and billing details."

    def fake_post(url, **kwargs):
        calls["n"] += 1
        return QuotaOut()

    monkeypatch.setattr(ai_mod, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai_mod, "GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(ai_mod, "time", type("T", (), {"sleep": lambda *a: None})())
    monkeypatch.setattr(ai_mod.httpx, "post", fake_post)
    assert ai_mod._gemini_chat("s", "u", 0.4, json_mode=False) is None
    assert calls["n"] == 1
    # The next call answers from the backup without touching Gemini at all
    assert ai_mod._gemini_chat("s", "u", 0.4, json_mode=False) is None
    assert calls["n"] == 1
