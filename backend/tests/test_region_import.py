"""The two-choice import: Egypt jobs or jobs outside Egypt.

Each choice must pick its own sites automatically, so one press never has to
fetch every site in the app.
"""
import pytest
from fastapi import HTTPException

from app.api.deps import resolve_sources
from app.database import SessionLocal
from app.services import providers as providers_mod
from app.services.providers import REGISTRY


def test_regions_split_the_registry_without_overlap():
    egypt = resolve_sources(None, [], 1, region="egypt")
    worldwide = resolve_sources(None, [], 1, region="worldwide")
    assert egypt == [name for name, cls in REGISTRY.items() if cls.region == "egypt"]
    assert worldwide == [name for name, cls in REGISTRY.items() if cls.region == "worldwide"]
    assert egypt and worldwide
    assert not set(egypt) & set(worldwide)


def test_region_is_trimmed_and_case_insensitive():
    assert resolve_sources(None, [], 1, region=" EGYPT ") == resolve_sources(None, [], 1, region="egypt")


def test_unknown_region_is_refused():
    with pytest.raises(HTTPException) as exc:
        resolve_sources(None, [], 1, region="mars")
    assert exc.value.status_code == 422
    assert "egypt" in exc.value.detail


def test_region_import_runs_only_that_regions_sites(client, monkeypatch):
    class EgyptSpy(providers_mod.BaseProvider):
        name = "region_spy_eg"
        label = "Egypt spy"
        region = "egypt"

        def fetch(self, titles, skills, locations, remote_only):
            return []

    class WorldSpy(providers_mod.BaseProvider):
        name = "region_spy_world"
        label = "World spy"
        region = "worldwide"

        def fetch(self, titles, skills, locations, remote_only):
            return []

    monkeypatch.setitem(providers_mod.REGISTRY, "region_spy_eg", EgyptSpy)
    monkeypatch.setitem(providers_mod.REGISTRY, "region_spy_world", WorldSpy)
    # The worldwide spy is the only ticked site, so a region import must ignore the
    # tick list and still pick Egypt sites — that is the "automatic" part.
    client.put("/api/automation/settings", json=dict(
        enabled=False, titles=["Flutter Developer"], skills=["Flutter"],
        locations=["Cairo"], remote_only=False, interval_minutes=60,
        min_match_score=50, sources=["region_spy_world"], max_age_days=30,
    ))
    db = SessionLocal()
    try:
        providers_mod.ensure_sources(db)
    finally:
        db.close()

    r = client.post("/api/jobs/refresh?region=egypt", json=[])
    assert r.status_code == 200
    used = r.json()["sources_used"]
    assert "region_spy_eg" in used
    assert "region_spy_world" not in used
