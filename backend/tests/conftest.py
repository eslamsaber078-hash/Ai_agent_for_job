import hashlib
import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), "jobhunter_test.db").replace("\\", "/")
# Set to "" (not just unset): config._load_dotenv fills any key missing from the
# environment with the real backend/.env value, which would make the tests call
# the real AI provider with his live API key.
os.environ["OPENAI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.api import auth as auth_api  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
import app.main as app_main  # noqa: E402
from app.models import Account, AuthSession, Job, UserProfile  # noqa: E402
from app.services import cache, ensure_sources  # noqa: E402
from fixture_jobs import FIXTURE_JOBS  # noqa: E402

# The reset_db fixture drops and recreates every table between tests; a housekeeping
# pass still running from the previous database would write into the next one.
app_main.STARTUP_HOUSEKEEPING = False

# The fixture owner. Sessions are seeded directly (one scrypt hash computed once)
# so ordinary API tests do not pay a password verification each time.
TEST_PHONE = "+201000000001"
TEST_PHONE_LOCAL = "01000000001"
TEST_PASSWORD = "test-password-1"
TEST_PASSWORD_HASH = auth_api._hash_password(TEST_PASSWORD)
TEST_SESSION_TOKEN = "t" * 43


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # The ranking memo outlives a request by design; a fresh database in the next test
    # must not be answered with the previous test's rankings.
    cache.clear()
    db = SessionLocal()
    try:
        ensure_sources(db)
        now = datetime.now(timezone.utc)
        for i, item in enumerate(FIXTURE_JOBS, start=1):
            db.add(Job(
                external_id=f"fixture-{i}",
                source="remotive",
                title=item["title"],
                company=item["company"],
                location=item["location"],
                country="Egypt",
                remote=item["remote"],
                employment_type="Full-time",
                experience_level=item["level"],
                description="Real-format fixture job used by the test suite.",
                url=f"http://example.com/{i}",
                skills=item["skills"],
                posted_date=now - timedelta(days=i),
                is_demo=False,
            ))
        db.add(UserProfile(id=1))
        db.flush()
        account = Account(phone=TEST_PHONE, password_hash=TEST_PASSWORD_HASH, profile_id=1)
        db.add(account)
        db.flush()
        db.add(AuthSession(
            token_hash=hashlib.sha256(TEST_SESSION_TOKEN.encode("ascii")).hexdigest(),
            account_id=account.id,
            expires_at=now + timedelta(days=1),
        ))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(autouse=True)
def authenticated(client, reset_db):
    """Every test talks to the API as the fixture account (owner of profile 1)."""
    auth_api._THROTTLE_BUCKETS.clear()
    client.headers["X-Requested-With"] = "XMLHttpRequest"
    client.cookies.set(auth_api.COOKIE_NAME, TEST_SESSION_TOKEN)
    yield client


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests must never hit the real internet: stub every provider GET."""
    from app.services import providers as providers_mod
    from app.services.providers import clear_fetch_cache

    class FakeResp:
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {"jobs": []}

    def fake_get(*args, **kwargs):
        return FakeResp()

    def fake_post(*args, **kwargs):
        return FakeResp()

    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    monkeypatch.setattr(providers_mod.httpx, "post", fake_post)
    clear_fetch_cache()
    yield
