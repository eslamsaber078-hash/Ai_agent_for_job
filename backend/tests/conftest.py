import os
import tempfile
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), "jobhunter_test.db").replace("\\", "/")
os.environ.pop("OPENAI_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Job, UserProfile  # noqa: E402
from app.services import ensure_sources  # noqa: E402
from fixture_jobs import FIXTURE_JOBS  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
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
        db.commit()
    finally:
        db.close()
    yield


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

    monkeypatch.setattr(providers_mod.httpx, "get", fake_get)
    clear_fetch_cache()
    yield
