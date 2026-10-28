from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Application, GeneratedMaterial, Job, UserProfile
from ..schemas import GENERATION_KINDS, GenerationRequest, GenerationResult
from ..services import pdf as pdf_service
from ..services import generate_material
from ..services.assistant import cv_for_pdf, review_copy, unmark_suggestions
from .deps import get_job_or_404
from .auth import get_current_profile

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/generate", response_model=GenerationResult)
def generate(req: GenerationRequest, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    if req.kind not in GENERATION_KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown kind. Choose from: {', '.join(GENERATION_KINDS)}")
    job = get_job_or_404(db, req.job_id, profile.id)
    result = generate_material(db, job, profile, req.kind, req.extra_notes)
    # A draft for a job he already tracks belongs to that application, so the tracker
    # can show everything prepared for it.
    tracked = db.query(Application).filter(Application.job_id == job.id).first()
    db.add(GeneratedMaterial(job_id=job.id, application_id=tracked.id if tracked else None,
                             kind=req.kind, content=result["content"],
                             template_based=result["template_based"]))
    db.commit()
    return result


@router.get("/cv/{job_id}/pdf")
def cv_pdf(job_id: int, marked: bool = Query(True), db: Session = Depends(get_db),
           profile: UserProfile = Depends(get_current_profile)):
    """The CV written for this one ad, as a PDF — no tracker entry needed to get it.

    ``marked`` (the default) is the copy he reviews: additions the assistant suggested
    for this ad are drawn red and underlined. ``marked=False`` is the copy for the
    employer: the same additions, brackets and review notes removed.

    When this ad already has a CV draft, that reviewed text is what gets rendered —
    regenerating on every download is how the two copies could disagree.
    """
    job = get_job_or_404(db, job_id, profile.id)
    row = (db.query(GeneratedMaterial)
           .filter(GeneratedMaterial.job_id == job_id, GeneratedMaterial.kind == "cv")
           .order_by(GeneratedMaterial.created_at.desc()).first())
    if row is None:
        content = cv_for_pdf(job, profile, marked=marked)
    else:
        content = review_copy(row.content) if marked else unmark_suggestions(row.content)
    return Response(pdf_service.render_text_pdf(content, name_line=True, title=f"CV - {job.title}"),
                    media_type="application/pdf")


@router.get("/materials/{job_id}")
def list_materials(job_id: int, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    get_job_or_404(db, job_id, profile.id)
    items = (
        db.query(GeneratedMaterial)
        .filter(GeneratedMaterial.job_id == job_id)
        .order_by(GeneratedMaterial.created_at.desc())
        .all()
    )
    return [
        dict(id=m.id, kind=m.kind, content=m.content, template_based=m.template_based,
             created_at=m.created_at)
        for m in items
    ]


@router.delete("/materials/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db), profile: UserProfile = Depends(get_current_profile)):
    material = (
        db.query(GeneratedMaterial)
        .join(Job, GeneratedMaterial.job_id == Job.id)
        .filter(GeneratedMaterial.id == material_id, Job.profile_id == profile.id)
        .first()
    )
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    db.delete(material)
    db.commit()
    return {"deleted": True}
