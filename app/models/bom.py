import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class BOMStructure(Base):
    __tablename__ = "bom_structures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    parent_part_id = Column(UUID(as_uuid=True), ForeignKey("parts.id", ondelete="CASCADE"), nullable=False, index=True)
    component_part_id = Column(UUID(as_uuid=True), ForeignKey("parts.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    quantity_required = Column(Numeric(10, 4), nullable=False, default=1.0000)
    scrap_factor_pct = Column(Numeric(5, 2), nullable=False, default=0.00)
    find_number = Column(String(32), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "parent_part_id", "component_part_id", name="uq_tenant_parent_component"),
    )
