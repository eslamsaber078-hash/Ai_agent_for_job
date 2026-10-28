def test_dashboard_stats_computed_from_db(client):
    r = client.get("/api/dashboard/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_jobs"] >= 20
    assert data["applications"] == 0
    assert data["saved_jobs"] == 0
    assert len(data["recent_jobs"]) > 0


def test_dashboard_reflects_actions(client):
    client.post("/api/jobs/1/save")
    client.post("/api/applications", json=dict(job_id=2, status="Interview"))
    data = client.get("/api/dashboard/stats").json()
    assert data["saved_jobs"] == 1
    assert data["applications"] == 1
    assert data["interviews"] == 1
    breakdown = {b["status"]: b["count"] for b in data["status_breakdown"]}
    assert breakdown.get("Interview") == 1


def test_dashboard_high_match_with_profile(client):
    client.put("/api/profile", json=dict(
        full_name="Ahmed", summary="Flutter dev",
        desired_titles=["Flutter Developer"], target_levels=["Junior"],
    ))
    client.put("/api/profile/skills", json=[
        dict(name="Flutter", level=5), dict(name="Dart", level=5),
        dict(name="Firebase", level=4), dict(name="REST APIs", level=4),
        dict(name="Git", level=4),
    ])
    data = client.get("/api/dashboard/stats").json()
    assert data["profile_complete"] is True
    assert data["high_match_jobs"] >= 1
    assert len(data["best_matches"]) >= 1
    assert data["best_matches"][0]["score"] >= 70


def test_follow_up_list_starts_with_the_overdue_one(client):
    """An unnoticed past follow-up date used to disappear from the dashboard."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    client.post("/api/applications", json=dict(
        job_id=1, status="Applied", follow_up_date=(now - timedelta(days=2)).isoformat()))
    client.post("/api/applications", json=dict(
        job_id=2, status="Interview", follow_up_date=(now + timedelta(days=3)).isoformat()))
    dates = [f["follow_up_date"] for f in client.get("/api/dashboard/stats").json()["upcoming_follow_ups"]]
    assert len(dates) == 2
    assert dates == sorted(dates)
    assert dates[0] < now.isoformat()


def test_dead_applications_do_not_ask_for_a_follow_up(client):
    """A Rejected or Archived row has nothing left to follow up on."""
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    for job_id, status in ((3, "Rejected"), (4, "Archived"), (5, "Applied")):
        client.post("/api/applications", json=dict(job_id=job_id, status=status, follow_up_date=past))
    rows = client.get("/api/dashboard/stats").json()["upcoming_follow_ups"]
    assert [a["status"] for a in rows] == ["Applied"]
