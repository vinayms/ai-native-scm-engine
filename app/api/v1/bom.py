from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.bom import BOMStructure
from app.models.part import Part
from app.services.bom_engine import check_bom_cycle, explode_bom, BOMCycleDetectedException

router = APIRouter(prefix="/bom", tags=["Bill of Materials"])


class BOMItemCreate(BaseModel):
    parent_part_id: UUID
    component_part_id: UUID
    quantity_required: float = Field(default=1.0, gt=0.0)
    scrap_factor_pct: float = Field(default=0.0, ge=0.0)
    find_number: Optional[str] = None
    notes: Optional[str] = None


@router.post("")
def add_bom_item(
    payload: BOMItemCreate,
    x_tenant_id: UUID = Header(...),
    db: Session = Depends(get_db)
):
    # Verify both parts exist and belong to the tenant
    parent = db.query(Part).filter(Part.tenant_id == x_tenant_id, Part.id == payload.parent_part_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent part not found.")

    component = db.query(Part).filter(Part.tenant_id == x_tenant_id, Part.id == payload.component_part_id).first()
    if not component:
        raise HTTPException(status_code=404, detail="Component part not found.")

    # 1. Cycle detection validation
    try:
        check_bom_cycle(db, x_tenant_id, payload.parent_part_id, payload.component_part_id)
    except BOMCycleDetectedException as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Check for duplicate link
    existing = db.query(BOMStructure).filter(
        BOMStructure.tenant_id == x_tenant_id,
        BOMStructure.parent_part_id == payload.parent_part_id,
        BOMStructure.component_part_id == payload.component_part_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="This component relationship already exists in the BOM.")

    bom_item = BOMStructure(
        tenant_id=x_tenant_id,
        parent_part_id=payload.parent_part_id,
        component_part_id=payload.component_part_id,
        quantity_required=payload.quantity_required,
        scrap_factor_pct=payload.scrap_factor_pct,
        find_number=payload.find_number,
        notes=payload.notes,
    )
    db.add(bom_item)
    db.commit()
    db.refresh(bom_item)

    return {
        "message": "Component successfully added to BOM",
        "bom_id": str(bom_item.id),
        "parent_part_number": parent.part_number,
        "component_part_number": component.part_number,
        "quantity_required": payload.quantity_required,
        "scrap_factor_pct": payload.scrap_factor_pct,
    }


@router.get("/{root_part_id}/explode")
def explode_assembly_bom(
    root_part_id: UUID,
    x_tenant_id: UUID = Header(...),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Recursively explodes a multi-tier assembly, returning total rolled-up cost,
    scrap allowances, and the critical-path bottleneck lead time.
    """
    try:
        return explode_bom(db, x_tenant_id, root_part_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
