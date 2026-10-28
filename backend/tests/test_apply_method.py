"""The ad's own instructions, read literally: never guess an address he did not write."""
from app.models import Job
from app.services.apply_method import apply_method, board_of

BOARD = "https://board.example.com/job/1"


def _job(description: str, url: str = BOARD) -> Job:
    return Job(title="Junior Flutter Developer", company="NileSoft",
               description=description, url=url, source="remotive", external_id="x")


def test_email_ad_yields_the_mailbox_it_names():
    result = apply_method(_job("To apply, send your CV to hiring@nilesoft.example today."))
    assert result["apply_channel"] == "email"
    assert result["apply_emails"] == ["hiring@nilesoft.example"]
    assert "hiring@nilesoft.example" in result["apply_note"]


def test_a_mailbox_named_for_hiring_needs_no_sentence_around_it():
    result = apply_method(_job("recruitment@montu.example"))
    assert result["apply_emails"] == ["recruitment@montu.example"]


def test_a_privacy_mailbox_is_never_offered_as_an_apply_route():
    result = apply_method(_job("For data questions write privacy@nilesoft.example. "
                               "To apply visit our page."))
    assert result["apply_emails"] == []
    assert result["apply_channel"] == "listing"


def test_company_link_is_offered_but_the_boards_own_link_is_not():
    result = apply_method(_job(
        "Apply directly at https://nilesoft.example/careers/flutter. "
        "This ad is on https://board.example.com/job/1"))
    assert result["apply_channel"] == "company-link"
    assert result["apply_links"] == ["https://nilesoft.example/careers/flutter"]


def test_a_press_release_or_blog_link_is_not_an_application_page():
    result = apply_method(_job(
        "Read the announcement at https://nilesoft.example/press/2026 and our "
        "culture blog https://nilesoft.example/blog/culture. Applications open soon."))
    assert result["apply_links"] == []
    assert result["apply_channel"] == "listing"


def test_a_markdown_link_is_read_for_its_target_not_its_label():
    result = apply_method(_job(
        "Apply via this link: [https://nilesoft.example/company/131](https://nilesoft.example/jobs/apply)"))
    assert result["apply_links"] == ["https://nilesoft.example/jobs/apply"]


def test_a_redirect_wrapper_is_opened_to_the_address_inside_it():
    result = apply_method(_job(
        'Please email your resume via '
        '<a href="https://www.google.com/url?q=https://nilesoft.example/company/careers&amp;source=gmail">'
        'careers</a>'))
    assert result["apply_links"] == ["https://nilesoft.example/company/careers"]


def test_an_ad_that_states_nothing_falls_back_to_its_own_page():
    result = apply_method(_job("Great team, great product, apply soon."))
    assert result["apply_channel"] == "listing"
    assert result["apply_note"] == "Apply on the board page — the ad gives no other address"


def test_api_job_carries_the_apply_route(client):
    r = client.get("/api/jobs/1")
    assert r.status_code == 200
    data = r.json()
    assert data["apply_channel"] == "listing"
    assert data["apply_emails"] == []
    assert data["apply_note"]
    assert data["publisher"] == ""


def test_a_half_written_redirect_wrapper_does_not_stop_the_ad_being_read():
    # apply_method runs for every job in every list, so a malformed URL must not raise.
    result = apply_method(_job(
        "Apply here: https://[google.com/url?q=https://nilesoft.example/careers"))
    assert result["apply_channel"] in ("company-link", "listing")
    assert result["apply_note"]


def test_the_board_that_published_the_ad_is_named():
    job = _job("[via Wuzzuf] Job Description. Apply on the ad page.",
               url="https://wuzzuf.net/jobs/p/senior-developer-cairo-egypt")
    assert board_of(job) == "Wuzzuf"
    assert apply_method(job)["apply_note"] == "Apply on Wuzzuf — the ad gives no other address"


def test_a_known_board_host_is_recognised_without_the_prefix():
    job = _job("Great team.", url="https://eg.linkedin.com/jobs/view/123")
    assert board_of(job) == "LinkedIn"


def test_an_ordinary_source_keeps_the_generic_note():
    assert board_of(_job("Great team.")) == ""
    assert apply_method(_job("Great team."))["apply_note"] == \
        "Apply on the board page — the ad gives no other address"


def test_the_api_says_which_board_the_apply_button_opens(client):
    from app.database import SessionLocal
    from app.models import Job

    with SessionLocal() as db:
        db.add(Job(profile_id=1, external_id="js-wuzzuf-1", source="jsearch",
                   title="Flutter Developer", company="NileSoft", location="Cairo",
                   country="Egypt", remote=False,
                   description="[via Wuzzuf] Job Description. Apply on the ad page.",
                   url="https://wuzzuf.net/jobs/p/flutter-cairo-egypt", skills=[],
                   is_demo=False, is_active=True))
        db.commit()
        job_id = db.query(Job).filter(Job.external_id == "js-wuzzuf-1").one().id

    data = client.get(f"/api/jobs/{job_id}").json()
    assert data["publisher"] == "Wuzzuf"
    assert data["apply_channel"] == "listing"
    assert data["apply_note"].startswith("Apply on Wuzzuf")
