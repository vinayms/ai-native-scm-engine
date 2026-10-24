import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    country_code = Column(String(2), default="US", nullable=False)
    lead_time_days = Column(Integer, default=14, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_tenant_supplier_code"),
    )


class ApprovedVendor(Base):
    __tablename__ = "approved_vendors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    part_id = Column(UUID(as_uuid=True), ForeignKey("parts.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    supplier_part_number = Column(String(128), nullable=True)
    unit_price = Column(Numeric(12, 4), nullable=False, default=0.0000)
    min_order_quantity = Column(Integer, default=1, nullable=False)
    lead_time_days = Column(Integer, default=14, nullable=False)
    preference_rank = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "part_id", "supplier_id", name="uq_tenant_part_supplier"),
    )
