import asyncio
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


def test_security_headers_on_api_responses(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "object-src 'none'" in response.headers["content-security-policy"]
    assert "geolocation=()" in response.headers["permissions-policy"]
    # HSTS is only for requests that actually arrived over HTTPS.
    assert "strict-transport-security" not in response.headers


def test_security_headers_on_static_pages(client):
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers


def test_oversized_json_body_is_refused_before_parsing(client):
    payload = json.dumps({"summary": "x" * (1024 * 1024 + 2048)})
    response = client.put("/api/profile", content=payload,
                          headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"


def test_resume_upload_gets_a_larger_ceiling_than_json(client):
    from app.config import MAX_RESUME_SIZE_MB
    from app.security import BodySizeLimit

    limit = BodySizeLimit(None)
    assert limit._limit_for("/api/profile") == 1024 * 1024
    assert limit._limit_for("/api/profile/resume") == MAX_RESUME_SIZE_MB * 1024 * 1024 + 512 * 1024


def test_write_throttle_blocks_after_the_ceiling():
    from app.security import WriteThrottle

    app = FastAPI()

    @app.post("/api/thing")
    def thing():
        return {"ok": True}

    @app.get("/api/thing")
    def read_thing():
        return {"ok": True}

    app.add_middleware(WriteThrottle, limit=2)
    with TestClient(app) as local:
        assert local.post("/api/thing").status_code == 200
        assert local.post("/api/thing").status_code == 200
        blocked = local.post("/api/thing")
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"].isdigit()
        # Reads are not throttled.
        assert local.get("/api/thing").status_code == 200


def test_database_outage_answers_503_with_retry_after():
    from app.main import _database_unavailable

    request = SimpleNamespace(method="GET", url=SimpleNamespace(path="/api/jobs"))
    exc = OperationalError("SELECT 1", {}, Exception("connection reset"))
    response = asyncio.run(_database_unavailable(request, exc))
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert b"database" in response.body.lower()
