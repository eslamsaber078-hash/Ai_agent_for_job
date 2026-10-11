from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application
from ..schemas import STATUSES, ApplicationIn, ApplicationOut, ApplicationUpdate
from .deps import get_job_or_404, job_to_out

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _to_out(db: Session, app: Application) -> ApplicationOut:
    out = ApplicationOut.model_validate(app)
    out.job = job_to_out(db, app.job)
    return out


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    status: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == status)
    apps = query.order_by(Application.updated_at.desc()).all()
    result = []
    for a in apps:
        if q and q.lower() not in f"{a.job.title} {a.job.company}".lower():
            continue
        result.append(_to_out(db, a))
    return result


@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(data: ApplicationIn, db: Session = Depends(get_db)):
    get_job_or_404(db, data.job_id)
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
    db.commit()
    db.refresh(app)
    return _to_out(db, app)


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(app_id: int, data: ApplicationUpdate, db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
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
def delete_application(app_id: int, db: Session = Depends(get_db)):
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(app)
    db.commit()
    return {"deleted": True}
