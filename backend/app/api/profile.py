from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import ALLOWED_RESUME_TYPES, MAX_RESUME_SIZE_MB
from ..database import get_db
from ..models import Education, Project, Skill, UserProfile, WorkExperience
from ..schemas import (
    ProfileIn,
    ProfileOut,
    ResumeAutofillApply,
    ResumeAutofillOut,
    TermSuggestion,
    TermSuggestIn,
)
from ..services.resume_parse import parse_resume
from ..services.terms import clean_term, suggest

from .auth import get_current_profile

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def read_profile(db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    return profile


@router.put("", response_model=ProfileOut)
def update_profile(data: ProfileIn, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/skills", response_model=ProfileOut)
def replace_skills(skills: list[dict], db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    for s in profile.skills:
        db.delete(s)
    for item in skills:
        try:
            name = str(item["name"])[:100]
            level = int(item.get("level", 3))
            years = item.get("years")
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Each skill needs a name and an optional level (1-5)")
        if not name:
            raise HTTPException(status_code=422, detail="Skill name cannot be empty")
        if not 1 <= level <= 5:
            raise HTTPException(status_code=422, detail=f"Skill level for '{name}' must be between 1 and 5")
        if years is not None and (not isinstance(years, (int, float)) or isinstance(years, bool) or years < 0 or years > 60):
            raise HTTPException(status_code=422, detail="Skill years must be a number between 0 and 60")
        db.add(Skill(profile_id=profile.id, name=name, level=level, years=years))
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/term-suggestions", response_model=list[TermSuggestion])
def term_suggestions(data: TermSuggestIn, profile: UserProfile = Depends(get_current_profile)):
    """Spelling hints for text the user typed.

    Read-only: nothing is stored or rewritten, so the profile keeps exactly what
    the user wrote; applying a hint is their click in the UI.
    """
    out: list[TermSuggestion] = []
    seen: set[tuple[str, str]] = set()
    for kind, values in (("title", data.titles), ("skill", data.skills),
                         ("location", data.locations)):
        for raw in values:
            term = clean_term(raw)
            fixed = suggest(term, kind) if term else None
            if not fixed or fixed.casefold() == term.casefold():
                continue
            key = (term.casefold(), fixed.casefold())
            if key in seen:
                continue
            seen.add(key)
            out.append(TermSuggestion(term=term, suggestion=fixed, kind=kind))
    return out


def _date_str(value) -> str | None:
    """Coerce a free-form dict value into the VARCHAR column these tables use.

    The endpoints take raw dicts, so a nested object would otherwise reach SQLite
    and crash the request with a 500.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value).strip()[:20] or None
    return None


@router.put("/experiences", response_model=ProfileOut)
def replace_experiences(items: list[dict], db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    for e in profile.experiences:
        db.delete(e)
    for item in items:
        db.add(WorkExperience(
            profile_id=profile.id,
            title=str(item.get("title", ""))[:200],
            company=str(item.get("company", ""))[:200],
            location=str(item.get("location", ""))[:200],
            start_date=_date_str(item.get("start_date")),
            end_date=_date_str(item.get("end_date")),
            current=bool(item.get("current", False)),
            description=str(item.get("description", ""))[:5000],
        ))
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/education", response_model=ProfileOut)
def replace_education(items: list[dict], db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    for e in profile.education:
        db.delete(e)
    for item in items:
        db.add(Education(
            profile_id=profile.id,
            degree=str(item.get("degree", ""))[:200],
            institution=str(item.get("institution", ""))[:200],
            field=str(item.get("field", ""))[:200],
            start_date=_date_str(item.get("start_date")),
            end_date=_date_str(item.get("end_date")),
            description=str(item.get("description", ""))[:2000],
        ))
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/projects", response_model=ProfileOut)
def replace_projects(items: list[dict], db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    for p in profile.projects:
        db.delete(p)
    for item in items:
        db.add(Project(
            profile_id=profile.id,
            name=str(item.get("name", ""))[:200],
            description=str(item.get("description", ""))[:5000],
            url=str(item.get("url", ""))[:300],
            technologies=[str(t) for t in (item.get("technologies") or [])][:30],
        ))
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/resume", response_model=ProfileOut)
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    import os

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_RESUME_TYPES:
        raise HTTPException(status_code=422,
                            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_RESUME_TYPES))}")
    limit = MAX_RESUME_SIZE_MB * 1024 * 1024
    # Read one byte past the limit so an oversized upload never lands fully in memory.
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_RESUME_SIZE_MB} MB limit")
    if ext in (".txt", ".md"):
        profile.resume_text = content.decode("utf-8", errors="replace")[:50000]
    elif ext == ".pdf":
        profile.resume_text = _extract_pdf_text(content)
    elif ext == ".docx":
        try:
            profile.resume_text = _extract_docx_text(content)
        except ValueError:
            raise HTTPException(status_code=422,
                                detail="This file is in the old .doc format. Open it in Word, "
                                       "choose Save As → .docx (or PDF), then upload again.")
    else:
        raise HTTPException(status_code=422,
                            detail="The old .doc format cannot be read safely. Open the file in "
                                   "Word, choose Save As → .docx (or PDF), then upload again.")
    profile.resume_filename = file.filename[:300]
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/resume/autofill", response_model=ResumeAutofillOut)
def preview_resume_autofill(profile: UserProfile = Depends(get_current_profile)):
    """Suggest profile values read literally from the uploaded resume.

    Read-only: the user reviews every item in the UI and applies what they pick.
    """
    text = (profile.resume_text or "").strip()
    if not text:
        raise HTTPException(status_code=422,
                            detail="Upload a resume with readable text first — there is nothing to read.")
    return ResumeAutofillOut(**parse_resume(text))


_SCALAR_LIMITS = {
    "full_name": 200, "email": 300, "phone": 50, "country": 100, "city": 100,
    "linkedin": 300, "github": 300, "portfolio": 300, "summary": 20000,
}


@router.post("/resume/autofill/apply", response_model=ProfileOut)
def apply_resume_autofill(data: ResumeAutofillApply, db: Session = Depends(get_db),
                          profile: UserProfile = Depends(get_current_profile)):
    """Write only the suggestions the user ticked, without deleting anything.

    Text fields are replaced because the user explicitly chose them; skills,
    experience and education are appended and de-duplicated.
    """
    for key, value in data.fields.items():
        limit = _SCALAR_LIMITS.get(key)
        if limit is None:
            continue
        setattr(profile, key, str(value or "").strip()[:limit])

    existing_skills = {s.name.casefold() for s in profile.skills}
    for raw in data.skills:
        name = str(raw).strip()[:100]
        if name and name.casefold() not in existing_skills:
            db.add(Skill(profile_id=profile.id, name=name, level=3))
            existing_skills.add(name.casefold())

    existing_exp = {(e.title.casefold(), e.company.casefold(), (e.start_date or ""))
                    for e in profile.experiences}
    for item in data.experiences:
        title = item.title.strip()[:200]
        if not title:
            continue
        signature = (title.casefold(), item.company.strip().casefold(), item.start_date or "")
        if signature in existing_exp:
            continue
        db.add(WorkExperience(
            profile_id=profile.id,
            title=title,
            company=item.company.strip()[:200],
            location=item.location.strip()[:200],
            start_date=_date_str(item.start_date),
            end_date=_date_str(item.end_date),
            current=item.current,
            description=item.description.strip()[:5000],
        ))
        existing_exp.add(signature)

    existing_edu = {(e.degree.casefold(), e.institution.casefold()) for e in profile.education}
    for item in data.education:
        degree = item.degree.strip()[:200]
        if not degree:
            continue
        signature = (degree.casefold(), item.institution.strip().casefold())
        if signature in existing_edu:
            continue
        db.add(Education(
            profile_id=profile.id,
            degree=degree,
            institution=item.institution.strip()[:200],
            field=item.field.strip()[:200],
            start_date=_date_str(item.start_date),
            end_date=_date_str(item.end_date),
            description=item.description.strip()[:2000],
        ))
        existing_edu.add(signature)

    db.commit()
    db.refresh(profile)
    return profile


def _extract_pdf_text(content: bytes) -> str | None:
    try:
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)[:50000]
        return text.strip() or None
    except Exception:
        return None


def _extract_docx_text(content: bytes) -> str | None:
    """Read word/document.xml from the .docx zip with the stdlib only.

    The file is never opened by Word or executed; we only unzip one member and
    strip markup. An old binary .doc renamed to .docx is detected by its OLE2
    magic so the user gets a clear convert message instead of a silent empty CV.
    """
    if content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("binary .doc disguised as .docx")
    try:
        import html
        import io
        import re
        import zipfile

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            with archive.open("word/document.xml") as raw:
                xml = raw.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    # Keep the whitespace structure: paragraphs become line breaks, tabs stay tabs.
    xml = re.sub(r"<w:tab(?: [^>]*)?/>", "\t", xml)
    xml = re.sub(r"<w:p(?: [^>]*)?>", "\n", xml)
    body = re.sub(r"<[^>]+>", " ", xml)
    body = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in body.splitlines())
    body = re.sub(r"\n{2,}", "\n", body).strip()[:50000]
    return html.unescape(body) or None


@router.delete("/resume", response_model=ProfileOut)
def delete_resume(db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    profile.resume_filename = None
    profile.resume_text = None
    db.commit()
    db.refresh(profile)
    return profile
