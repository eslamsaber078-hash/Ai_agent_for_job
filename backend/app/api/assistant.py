from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import GeneratedMaterial, UserProfile
from ..schemas import GENERATION_KINDS, GenerationRequest, GenerationResult
from ..services import generate_material
from .deps import get_job_or_404

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/generate", response_model=GenerationResult)
def generate(req: GenerationRequest, db: Session = Depends(get_db)):
    if req.kind not in GENERATION_KINDS:
        raise HTTPException(status_code=422, detail=f"Unknown kind. Choose from: {', '.join(GENERATION_KINDS)}")
    job = get_job_or_404(db, req.job_id)
    profile = db.get(UserProfile, 1)
    result = generate_material(db, job, profile, req.kind, req.extra_notes)
    db.add(GeneratedMaterial(job_id=job.id, kind=req.kind, content=result["content"],
                             template_based=result["template_based"]))
    db.commit()
    return result


@router.get("/materials/{job_id}")
def list_materials(job_id: int, db: Session = Depends(get_db)):
    get_job_or_404(db, job_id)
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
def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.get(GeneratedMaterial, material_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Material not found")
    db.delete(material)
    db.commit()
    return {"deleted": True}
