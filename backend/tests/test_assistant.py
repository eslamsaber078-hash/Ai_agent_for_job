def _setup_profile(client):
    client.put("/api/profile", json=dict(
        full_name="Ahmed", email="a@b.com", summary="Flutter developer",
        desired_titles=["Flutter Developer"], target_levels=["Junior"],
    ))
    client.put("/api/profile/skills", json=[dict(name="Flutter", level=4), dict(name="Dart", level=3)])


def test_generate_without_key_uses_templates(client):
    _setup_profile(client)
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="cover_letter"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kind"] == "cover_letter"
    assert len(data["content"]) > 100
    assert data["template_based"] is True  # no OpenAI key in test env
    assert "review" in data["warning"].lower()


def test_generate_all_kinds(client):
    _setup_profile(client)
    for kind in ["summary", "bullets", "cover_letter", "email", "questions", "keywords"]:
        r = client.post("/api/assistant/generate", json=dict(job_id=1, kind=kind))
        assert r.status_code == 200, kind
        assert r.json()["content"].strip()


def test_generate_invalid_kind(client):
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="poem"))
    assert r.status_code == 422


def test_generate_unknown_job(client):
    r = client.post("/api/assistant/generate", json=dict(job_id=999999, kind="summary"))
    assert r.status_code == 404


def test_generate_never_fabricates_name(client):
    # Empty profile: generated texts must use placeholders, not invented facts
    r = client.post("/api/assistant/generate", json=dict(job_id=1, kind="email"))
    content = r.json()["content"]
    assert "[Your Name]" in content or "[your email]" in content
    assert "Ahmed" not in content


def test_materials_list_and_delete(client):
    _setup_profile(client)
    client.post("/api/assistant/generate", json=dict(job_id=1, kind="summary"))
    r = client.get("/api/assistant/materials/1")
    items = r.json()
    assert len(items) == 1
    assert items[0]["kind"] == "summary"
    r = client.delete(f"/api/assistant/materials/{items[0]['id']}")
    assert r.status_code == 200
    assert client.get("/api/assistant/materials/1").json() == []
