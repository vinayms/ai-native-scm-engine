from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.tenant import Tenant

router = APIRouter(prefix="/tenants", tags=["Tenants"])


class TenantCreate(BaseModel):
    name: str
    slug: str
    plan_tier: Optional[str] = "ENTERPRISE"


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan_tier: str


@router.post("", response_model=TenantResponse)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.slug == payload.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant with this slug already exists.")
    
    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        plan_tier=payload.plan_tier or "ENTERPRISE"
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("", response_model=List[TenantResponse])
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).all()


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(tenant_id: UUID, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return tenant
