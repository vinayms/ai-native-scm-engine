from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.part import Part
from app.services.ai_service import get_embedding, build_combined_part_text, find_substitute_parts

router = APIRouter(prefix="/parts", tags=["Parts"])


class PartCreate(BaseModel):
    part_number: str
    name: str
    description: Optional[str] = None
    part_type: Optional[str] = "COMPONENT"
    uom: Optional[str] = "EA"
    unit_cost: float = Field(default=0.0, ge=0.0)
    lead_time_days: int = Field(default=7, ge=0)
    specifications: Dict[str, Any] = Field(default_factory=dict)
    ai_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)


class PartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    part_number: str
    name: str
    description: Optional[str] = None
    part_type: str
    uom: str
    unit_cost: float
    lead_time_days: int
    specifications: Dict[str, Any]
    ai_risk_score: float


@router.post("", response_model=PartResponse)
def create_part(
    payload: PartCreate,
    x_tenant_id: UUID = Header(..., description="Tenant ID header for multi-tenancy"),
    db: Session = Depends(get_db)
):
    # Verify part number uniqueness within this tenant
    existing = db.query(Part).filter(Part.tenant_id == x_tenant_id, Part.part_number == payload.part_number).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Part {payload.part_number} already exists for this tenant.")

    # 1. Build combined document representation
    combined_doc = build_combined_part_text(
        name=payload.name,
        description=payload.description,
        specs=payload.specifications,
    )
    
    # 2. Generate 768-dim vector embedding
    embedding = get_embedding(combined_doc)

    part = Part(
        tenant_id=x_tenant_id,
        part_number=payload.part_number,
        name=payload.name,
        description=payload.description,
        part_type=payload.part_type or "COMPONENT",
        uom=payload.uom or "EA",
        unit_cost=payload.unit_cost,
        lead_time_days=payload.lead_time_days,
        specifications=payload.specifications,
        embedding=embedding,
        ai_risk_score=payload.ai_risk_score,
    )
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


@router.get("", response_model=List[PartResponse])
def list_parts(
    x_tenant_id: UUID = Header(...),
    part_type: Optional[str] = None,
    max_cost: Optional[float] = None,
    max_lead_time: Optional[int] = None,
    semantic_query: Optional[str] = None,
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db)
):
    """
    Hybrid Search: Combines exact SQL WHERE filters with pgvector semantic similarity ordering.
    """
    query = db.query(Part).filter(Part.tenant_id == x_tenant_id)

    if part_type:
        query = query.filter(Part.part_type == part_type)
    if max_cost is not None:
        query = query.filter(Part.unit_cost <= max_cost)
    if max_lead_time is not None:
        query = query.filter(Part.lead_time_days <= max_lead_time)

    if semantic_query:
        query_vec = get_embedding(semantic_query)
        vec_str = f"[{','.join(str(x) for x in query_vec)}]"
        # Order by cosine distance
        query = query.order_by(text(f"embedding <=> '{vec_str}'::vector ASC"))

    return query.limit(limit).all()


@router.get("/{part_id}", response_model=PartResponse)
def get_part(part_id: UUID, x_tenant_id: UUID = Header(...), db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.tenant_id == x_tenant_id, Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="Part not found.")
    return part


@router.get("/{part_id}/substitutes")
def get_substitutes(
    part_id: UUID,
    x_tenant_id: UUID = Header(...),
    limit: int = Query(default=5, le=20),
    min_similarity: float = Query(default=0.50, ge=0.0, le=1.0),
    db: Session = Depends(get_db)
):
    """Finds alternative/substitute parts using vector proximity in PostgreSQL."""
    substitutes = find_substitute_parts(
        db=db,
        tenant_id=x_tenant_id,
        target_part_id=part_id,
        limit=limit,
        min_similarity=min_similarity
    )
    return {
        "target_part_id": part_id,
        "substitutes_found": len(substitutes),
        "results": substitutes,
    }
