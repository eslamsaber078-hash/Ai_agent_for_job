from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, GeneratedMaterial, Job, UserProfile
from ..schemas import (ApplicationIn, ApplicationOut, ApplicationUpdate,
                       PreparedApplication, PreparedMaterial, PrepareIn, STATUSES)
from ..services import pdf as pdf_service
from ..services.apply_method import apply_method
from ..services.assistant import (cv_for_pdf, generate_material, review_copy,
                                  unmark_suggestions)
from .deps import get_job_or_404, job_to_out, jobs_to_out
from .auth import get_current_profile

router = APIRouter(prefix="/api/applications", tags=["applications"])

# The documents one click prepares for a job he means to apply to.
PREPARE_KINDS = ["cv", "cover_letter", "email", "questions", "keywords"]


def _to_out(db: Session, app: Application, job_out=None, materials_count=None) -> ApplicationOut:
    out = ApplicationOut.model_validate(app)
    out.job = job_out if job_out is not None else job_to_out(db, app.job)
    out.materials_count = materials_count if materials_count is not None else (
        db.query(GeneratedMaterial).filter(GeneratedMaterial.application_id == app.id).count()
    )
    return out


def _get_app_or_404(db: Session, app_id: int, profile_id: int) -> Application:
    """Applications inherit ownership from their job; another account's id reads as 404."""
    app = (
        db.query(Application)
        .join(Job, Application.job_id == Job.id)
        .filter(Application.id == app_id, Job.profile_id == profile_id)
        .first()
    )
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    status: str = "",
    q: str = "",
    db: Session = Depends(get_db),
    profile: UserProfile = Depends(get_current_profile),
):
    query = (
        db.query(Application)
        .join(Job, Application.job_id == Job.id)
        .filter(Job.profile_id == profile.id)
    )
    if status:
        query = query.filter(Application.status == status)
    apps = query.order_by(Application.updated_at.desc()).all()
    apps = [a for a in apps if not q or q.lower() in f"{a.job.title} {a.job.company}".lower()]
    # Bulk lookups instead of three queries per application row.
    job_outs = {o.id: o for o in jobs_to_out(db, [a.job for a in apps])}
    counts = dict(
        db.query(GeneratedMaterial.application_id, func.count(GeneratedMaterial.id))
        .filter(GeneratedMaterial.application_id.in_([a.id for a in apps]))
        .group_by(GeneratedMaterial.application_id).all()
    )
    return [_to_out(db, a, job_out=job_outs[a.job_id], materials_count=counts.get(a.id, 0))
            for a in apps]


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(data: ApplicationIn, db: Session = Depends(get_db),
                       profile: UserProfile = Depends(get_current_profile)):
    get_job_or_404(db, data.job_id, profile.id)
    if data.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status. Valid: {', '.join(STATUSES)}")
    existing = db.query(Application).filter(Application.job_id == data.job_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="An application for this job already exists")
    app = Application(
        job_id=data.job_id,
        status=data.status,
        date_applied=data.date_applied,
        follow_up_date=data.follow_up_date,
        interview_date=data.interview_date,
        notes=data.notes,
    )
    db.add(app)
    try:
        db.commit()
    except IntegrityError:
        # He double-clicked Track; the other request already made this row.
        db.rollback()
        raise HTTPException(status_code=409, detail="An application for this job already exists")
    db.refresh(app)
    return _to_out(db, app)


@router.post("/prepare", response_model=PreparedApplication)
def prepare_application(data: PrepareIn, db: Session = Depends(get_db),
                        profile: UserProfile = Depends(get_current_profile)):
    """Do everything before the click: the documents for this one ad, in the tracker.

    The application itself is never sent from here — the ad lives on another site and
    only he can submit it. What he should get is the CV aimed at that ad, the letter,
    the email text, and the real address or link to apply with.
    """
    job = get_job_or_404(db, data.job_id, profile.id)
    app = db.query(Application).filter(Application.job_id == job.id).first()
    if app is None:
        app = Application(job_id=job.id, status="Preparing", notes=data.notes)
        db.add(app)
        try:
            db.commit()
        except IntegrityError:
            # Two presses at once: the other request created the row, and this one writes
            # into the row that won instead of failing on the unique job_id.
            db.rollback()
            app = db.query(Application).filter(Application.job_id == job.id).one()
        else:
            db.refresh(app)
    elif data.notes and not app.notes:
        app.notes = data.notes

    materials: list[GeneratedMaterial] = []
    for kind in PREPARE_KINDS:
        result = generate_material(db, job, profile, kind, data.notes)
        # Re-preparing the same ad refreshes its pack instead of stacking drafts.
        db.query(GeneratedMaterial).filter(GeneratedMaterial.application_id == app.id,
                                           GeneratedMaterial.kind == kind).delete()
        row = GeneratedMaterial(job_id=job.id, application_id=app.id, kind=kind,
                               content=result["content"], template_based=result["template_based"])
        db.add(row)
        materials.append(row)
    app.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(app)

    out = _to_out(db, app)
    return PreparedApplication(
        application=out,
        materials=[PreparedMaterial.model_validate(m) for m in materials],
        **apply_method(job),
    )


@router.get("/{app_id}/materials", response_model=list[PreparedMaterial])
def application_materials(app_id: int, db: Session = Depends(get_db),
                          profile: UserProfile = Depends(get_current_profile)):
    _get_app_or_404(db, app_id, profile.id)
    return [
        PreparedMaterial.model_validate(m)
        for m in db.query(GeneratedMaterial).filter(GeneratedMaterial.application_id == app_id)
        .order_by(GeneratedMaterial.created_at.desc()).all()
    ]


@router.get("/{app_id}/materials/{kind}/pdf")
def material_pdf(app_id: int, kind: str, marked: bool = Query(True),
                 db: Session = Depends(get_db),
                 profile: UserProfile = Depends(get_current_profile)):
    """The PDF of one prepared document.

    ``marked`` (the default) is the review copy: the skills this ad wants that his CV
    cannot show are drawn red and underlined so he sees exactly what to confirm or cut.
    ``marked=False`` is the copy for the employer: the same additions, brackets and
    review notes removed, so it reads as one ordinary CV.

    The CV PDF is rendered from the material he already reviewed on screen — rebuilding
    it here used to write a fresh (and sometimes template-fallback) document, which is
    how a download could come back as his plain CV while the other carried the changes.

    No Content-Disposition header here: Chrome rejects a CORS fetch whose response
    carries "attachment", and the browser names the file itself when it saves the blob.
    """
    app = _get_app_or_404(db, app_id, profile.id)
    row = (db.query(GeneratedMaterial)
           .filter(GeneratedMaterial.application_id == app_id,
                   GeneratedMaterial.kind == kind).first())
    if row is None:
        if kind != "cv":
            raise HTTPException(status_code=404, detail="This document has not been prepared yet")
        content = cv_for_pdf(app.job, profile, marked=marked)
        name_line = True
    else:
        content = review_copy(row.content) if marked else unmark_suggestions(row.content)
        name_line = kind == "cv"
    return Response(pdf_service.render_text_pdf(content, name_line=name_line,
                                                title=f"{kind} - {app.job.title}"),
                    media_type="application/pdf")


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(app_id: int, data: ApplicationUpdate, db: Session = Depends(get_db),
                       profile: UserProfile = Depends(get_current_profile)):
    app = _get_app_or_404(db, app_id, profile.id)
    # exclude_unset keeps an explicit null (clearing a date) different from "not sent".
    fields = data.model_dump(exclude_unset=True)
    if "status" in fields:
        status = fields.pop("status")
        if status not in STATUSES:
            raise HTTPException(status_code=422, detail=f"Invalid status. Valid: {', '.join(STATUSES)}")
        app.status = status
        if status == "Applied" and app.date_applied is None and "date_applied" not in fields:
            app.date_applied = datetime.now(timezone.utc)
    for field, value in fields.items():
        setattr(app, field, value)
    app.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(app)
    return _to_out(db, app)


@router.delete("/{app_id}")
def delete_application(app_id: int, db: Session = Depends(get_db),
                       profile: UserProfile = Depends(get_current_profile)):
    app = _get_app_or_404(db, app_id, profile.id)
    # SQLite ignores the ondelete the column declares, so the pack has to go here by hand:
    # otherwise it stays behind under the job and the Assistant lists it twice after a
    # second Track + Prepare. Drafts he wrote himself in the Assistant (application_id
    # null) are his, not the pack's, and stay.
    db.query(GeneratedMaterial).filter(GeneratedMaterial.application_id == app_id).delete()
    db.delete(app)
    db.commit()
    return {"deleted": True}
