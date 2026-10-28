import hashlib
import json
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app import config
from app.api import auth
from app.database import SessionLocal
from app.main import app
from app.models import Account, AuthSession, Job, SearchPreference, UserProfile
from app.services import REGISTRY

HEADERS = {"X-Requested-With": "XMLHttpRequest"}
PHONE = "01012345678"
CANONICAL_PHONE = "+201012345678"
PASSWORD = "correct-password-123"


@pytest.fixture
def auth_client(reset_db, monkeypatch):
    sentinel = object()
    previous = app.dependency_overrides.pop(auth.get_current_profile, sentinel)
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", False)
    monkeypatch.setattr(config, "SESSION_MAX_AGE_SECONDS", 604800)
    with auth._THROTTLE_LOCK:
        auth._THROTTLE_BUCKETS.clear()
    with SessionLocal() as db:
        db.query(AuthSession).delete()
        db.query(Account).delete()
        db.commit()
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        if previous is sentinel:
            app.dependency_overrides.pop(auth.get_current_profile, None)
        else:
            app.dependency_overrides[auth.get_current_profile] = previous
        with auth._THROTTLE_LOCK:
            auth._THROTTLE_BUCKETS.clear()


def register(client, **changes):
    payload = {"name": "  Ahmed Hassan  ", "phone": PHONE, "password": PASSWORD}
    payload.update(changes)
    # ensure_ascii keeps lone surrogates representable as JSON escapes; httpx's
    # json= encoder would raise before the request reaches the validation code.
    return client.post("/api/auth/register",
                       content=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
                       headers={**HEADERS, "Content-Type": "application/json"})


def login(client, phone=PHONE, password=PASSWORD, headers=None):
    return client.post("/api/auth/login", json={"phone": phone, "password": password},
                       headers=HEADERS if headers is None else headers)


def session_hash(client):
    return hashlib.sha256(client.cookies.get(auth.COOKIE_NAME).encode("ascii")).hexdigest()


def test_register_creates_new_blank_account_without_claiming_legacy_profile(auth_client):
    with SessionLocal() as db:
        legacy = db.get(UserProfile, 1)
        legacy.full_name = "Legacy private profile"
        legacy.phone = CANONICAL_PHONE
        legacy.email = "legacy@example.com"
        legacy.summary = "Private legacy resume"
        legacy.desired_titles = ["Legacy Job"]
        db.commit()
        initial_jobs = db.query(Job).count()
        initial_profiles = db.query(UserProfile).count()
    response = register(auth_client)
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {"id", "profile_id", "phone", "full_name"}
    assert data["phone"] == CANONICAL_PHONE
    assert data["full_name"] == "Ahmed Hassan"
    assert data["profile_id"] != 1
    assert auth_client.get("/api/auth/me").json() == data
    with SessionLocal() as db:
        account = db.get(Account, data["id"])
        profile = db.get(UserProfile, data["profile_id"])
        preference = db.get(SearchPreference, profile.id)
        assert account.profile_id == profile.id
        assert account.phone == profile.phone == CANONICAL_PHONE
        assert account.password_hash != PASSWORD
        assert PASSWORD not in account.password_hash
        assert account.password_hash.startswith("scrypt$")
        assert auth._verify_password(PASSWORD, account.password_hash)
        assert profile.email == profile.summary == profile.country == profile.city == ""
        assert profile.desired_titles == profile.preferred_locations == profile.languages == []
        assert profile.resume_text is None and profile.resume_filename is None
        assert not profile.skills and not profile.experiences and not profile.education and not profile.projects
        assert preference.enabled is False
        assert preference.sources == list(REGISTRY)
        assert preference.titles == preference.skills == preference.locations == []
        assert db.query(Job).count() == initial_jobs
        assert db.query(UserProfile).count() == initial_profiles + 1
        assert db.get(UserProfile, 1).summary == "Private legacy resume"
        session = db.get(AuthSession, session_hash(auth_client))
        assert session.account_id == account.id
        assert len(session.token_hash) == 64
        assert session.token_hash != auth_client.cookies.get(auth.COOKIE_NAME)
        remaining = (session.expires_at - datetime.now(timezone.utc)).total_seconds()
        assert 604790 <= remaining <= 604800


@pytest.mark.parametrize("secure", [False, True])
def test_session_cookie_flags_and_configured_lifetime(auth_client, monkeypatch, secure):
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", secure)
    monkeypatch.setattr(config, "SESSION_MAX_AGE_SECONDS", 120)
    response = register(auth_client)
    assert response.status_code == 201
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie[auth.COOKIE_NAME]
    assert morsel["httponly"]
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == "/"
    assert morsel["max-age"] == "120"
    assert bool(morsel["secure"]) is secure
    assert len(morsel.value) == 43
    assert response.headers["cache-control"] == "no-store"
    token_hash = hashlib.sha256(morsel.value.encode("ascii")).hexdigest()
    with SessionLocal() as db:
        session = db.get(AuthSession, token_hash)
        remaining = (session.expires_at - datetime.now(timezone.utc)).total_seconds()
        assert 110 <= remaining <= 120


def test_wrong_and_unknown_login_are_generic_and_normalized_login_works(auth_client):
    registered = register(auth_client).json()
    old_hash = session_hash(auth_client)
    auth_client.cookies.clear()
    wrong = login(auth_client, password="wrong-password-123")
    unknown = login(auth_client, phone="01123456789")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid phone or password"}
    assert "set-cookie" not in wrong.headers and "set-cookie" not in unknown.headers
    assert auth_client.get("/api/auth/me").status_code == 401
    right = login(auth_client, phone=CANONICAL_PHONE)
    assert right.status_code == 200 and right.json() == registered
    assert session_hash(auth_client) != old_hash
    assert auth_client.get("/api/auth/me").json() == registered
    assert login(auth_client, phone=PHONE).json() == registered


def test_login_rotates_and_revokes_presented_cookie(auth_client):
    register(auth_client)
    old_token = auth_client.cookies.get(auth.COOKIE_NAME)
    old_hash = session_hash(auth_client)
    assert login(auth_client).status_code == 200
    assert auth_client.cookies.get(auth.COOKIE_NAME) != old_token
    with SessionLocal() as db:
        assert db.get(AuthSession, old_hash) is None
        assert db.query(AuthSession).count() == 1
    auth_client.cookies.clear()
    auth_client.cookies.set(auth.COOKIE_NAME, old_token)
    assert auth_client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("revoke", [False, True])
def test_expired_and_revoked_sessions_are_unauthorized(auth_client, revoke):
    register(auth_client)
    with SessionLocal() as db:
        session = db.get(AuthSession, session_hash(auth_client))
        if revoke:
            db.delete(session)
        else:
            session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert auth_client.get("/api/auth/me").status_code == 401
    assert auth_client.get("/api/profile").status_code == 401
    assert auth_client.post("/api/auth/logout", headers=HEADERS).status_code == 401


def test_logout_revokes_session_and_clears_httponly_cookie(auth_client):
    register(auth_client)
    token = auth_client.cookies.get(auth.COOKIE_NAME)
    token_hash = session_hash(auth_client)
    response = auth_client.post("/api/auth/logout", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    assert cookie[auth.COOKIE_NAME]["max-age"] == "0"
    assert cookie[auth.COOKIE_NAME]["httponly"]
    assert cookie[auth.COOKIE_NAME]["path"] == "/"
    assert auth_client.get("/api/auth/me").status_code == 401
    with SessionLocal() as db:
        assert db.get(AuthSession, token_hash) is None
    auth_client.cookies.clear()
    auth_client.cookies.set(auth.COOKIE_NAME, token)
    assert auth_client.get("/api/auth/me").status_code == 401


def test_duplicate_registration_rolls_back_every_new_row(auth_client):
    data = register(auth_client).json()
    old_hash = session_hash(auth_client)
    with SessionLocal() as db:
        before = (db.query(Account).count(), db.query(UserProfile).count(),
                  db.query(SearchPreference).count(), db.query(AuthSession).count())
    response = register(auth_client, phone=CANONICAL_PHONE, name="Not the existing owner")
    assert response.status_code == 409
    assert "set-cookie" not in response.headers
    with SessionLocal() as db:
        after = (db.query(Account).count(), db.query(UserProfile).count(),
                 db.query(SearchPreference).count(), db.query(AuthSession).count())
        assert before == after
        assert db.get(AuthSession, old_hash) is not None
    assert auth_client.get("/api/auth/me").json() == data
    assert register(auth_client, phone="01123456789", name="Second User").status_code == 201


@pytest.mark.parametrize("headers", [{}, {"X-Requested-With": "fetch"},
                                     {**HEADERS, "Origin": "https://attacker.example"},
                                     {**HEADERS, "Origin": "null"}])
@pytest.mark.parametrize("path", ["register", "login", "logout"])
def test_auth_mutations_require_csrf_and_trusted_origin(auth_client, headers, path):
    register(auth_client)
    old_hash = session_hash(auth_client)
    payload = {"phone": "01123456789", "password": PASSWORD}
    if path == "register":
        payload["name"] = "Another User"
    response = auth_client.post(f"/api/auth/{path}", json=payload, headers=headers)
    assert response.status_code == 403
    with SessionLocal() as db:
        assert db.query(Account).count() == 1
        assert db.get(AuthSession, old_hash) is not None


def test_allowed_origin_and_no_origin_are_supported(auth_client, monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://trusted.example"])
    assert register(auth_client).status_code == 201
    assert login(auth_client, headers={**HEADERS, "Origin": "https://trusted.example"}).status_code == 200


def test_unauthenticated_requests_and_forged_user_ids_are_rejected(auth_client):
    assert auth_client.get("/api/auth/me?user_id=1&profile_id=1").status_code == 401
    assert auth_client.get("/api/profile?user_id=1&profile_id=1").status_code == 401
    assert auth_client.put("/api/profile", json={"full_name": "Intruder"}, headers=HEADERS).status_code == 401
    assert auth_client.post("/api/auth/logout", headers=HEADERS).status_code == 401
    assert register(auth_client, profile_id=1).status_code == 422
    data = register(auth_client).json()
    assert auth_client.get("/api/auth/me?user_id=1&profile_id=1").json() == data
    assert auth_client.put("/api/profile", json={"full_name": "Intruder"}).status_code == 403
    assert auth_client.put("/api/profile", json={"full_name": "Intruder"},
                           headers={**HEADERS, "Origin": "https://attacker.example"}).status_code == 403


@pytest.mark.parametrize("token", ["forged", "a" * 43, "x" * 10000])
def test_forged_or_malformed_session_cookies_fail_closed(auth_client, token):
    auth_client.cookies.set(auth.COOKIE_NAME, token)
    assert auth_client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("changes", [
    {"name": "   "}, {"name": "x" * 201}, {"phone": "12345"}, {"phone": "201012345678"},
    {"phone": "0101234567"}, {"phone": "+0123456789"}, {"phone": "+1234567890123456"},
    {"phone": "+20 1012345678"}, {"phone": 1012345678}, {"password": "short"},
    {"password": "p" * 129}, {"password": 12345678}, {"password": "\ud800" * 8},
    {"name": "\ud800"}, {"id": 1},
])
def test_registration_validation_is_safe_and_does_not_create_rows(auth_client, changes):
    response = register(auth_client, **changes)
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])
    with SessionLocal() as db:
        assert db.query(Account).count() == 0
        assert db.query(AuthSession).count() == 0


@pytest.mark.parametrize("password", ["p" * 6, "p" * 128])
def test_password_length_boundaries(auth_client, password):
    assert register(auth_client, password=password).status_code == 201
    assert login(auth_client, password=password).status_code == 200


def test_international_phone_and_independent_salts(auth_client):
    first = register(auth_client, phone="+12025550123").json()
    second = register(auth_client, phone="+971501234567", name="Second User").json()
    assert first["profile_id"] != second["profile_id"]
    with SessionLocal() as db:
        assert db.get(Account, first["id"]).password_hash != db.get(Account, second["id"]).password_hash
    assert login(auth_client, phone="+12025550123").json() == first


def test_malformed_json_and_oversized_bodies_are_safe(auth_client):
    malformed = auth_client.post("/api/auth/register", content=b'{"password":"private-value",',
                                 headers={**HEADERS, "Content-Type": "application/json"})
    assert malformed.status_code == 422
    assert "private-value" not in malformed.text
    oversized = auth_client.post("/api/auth/register", content=b"x" * (auth._MAX_BODY_BYTES + 1),
                                 headers={**HEADERS, "Content-Type": "application/json"})
    assert oversized.status_code == 413


@pytest.mark.parametrize("path", ["login", "register"])
def test_login_and_register_are_rate_limited(auth_client, monkeypatch, path):
    monkeypatch.setattr(auth, "_LOGIN_LIMIT", 2)
    monkeypatch.setattr(auth, "_REGISTER_LIMIT", 2)
    for index in range(2):
        if path == "login":
            assert login(auth_client).status_code == 401
        else:
            assert register(auth_client, phone=f"0101234567{index}").status_code == 201
    response = login(auth_client) if path == "login" else register(auth_client)
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_throttle_is_bounded_per_real_client_ip_and_expires(auth_client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(auth, "_THROTTLE_MAX_BUCKETS", 2)

    def request(ip):
        return Request({"type": "http", "method": "POST", "path": "/api/auth/login",
                        "client": (ip, 1234), "headers": [(b"x-forwarded-for", b"spoofed")]})

    auth._throttle(request("192.0.2.1"), "login", 1)
    with pytest.raises(HTTPException) as limited:
        auth._throttle(request("192.0.2.1"), "login", 1)
    assert limited.value.status_code == 429
    auth._throttle(request("192.0.2.2"), "login", 1)
    with pytest.raises(HTTPException) as full:
        auth._throttle(request("192.0.2.3"), "login", 1)
    assert full.value.status_code == 429
    assert len(auth._THROTTLE_BUCKETS) == 2
    clock[0] += auth._THROTTLE_WINDOW_SECONDS + 1
    auth._throttle(request("192.0.2.3"), "login", 1)
    assert len(auth._THROTTLE_BUCKETS) == 1


def test_stored_scrypt_parameters_cannot_increase_work(auth_client, monkeypatch):
    register(auth_client)
    with SessionLocal() as db:
        account = db.query(Account).first()
        account.password_hash = account.password_hash.replace("$16384$", "$1073741824$")
        db.commit()
    original = auth.hashlib.scrypt
    calls = []

    def bounded_scrypt(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(auth.hashlib, "scrypt", bounded_scrypt)
    assert login(auth_client).status_code == 401
    assert len(calls) == 1
    assert calls[0]["n"] == 16384 and calls[0]["r"] == 8 and calls[0]["p"] == 1
    assert calls[0]["maxmem"] == 32 * 1024 * 1024
