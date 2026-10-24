import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    plan_tier = Column(String(32), default="ENTERPRISE", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TenantUser(Base):
    __tablename__ = "tenant_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    role = Column(String(32), default="OPERATOR", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
