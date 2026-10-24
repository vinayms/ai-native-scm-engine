import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Numeric, Integer, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from app.database import Base


class Part(Base):
    __tablename__ = "parts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    part_number = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    part_type = Column(String(32), default="COMPONENT", nullable=False)  # RAW_MATERIAL, COMPONENT, SUB_ASSEMBLY, FINISHED_GOOD
    uom = Column(String(16), default="EA", nullable=False)
    unit_cost = Column(Numeric(12, 4), default=0.0000, nullable=False)
    lead_time_days = Column(Integer, default=7, nullable=False)
    
    specifications = Column(JSONB, default={}, nullable=False)
    embedding = Column(Vector(768), nullable=True)
    ai_risk_score = Column(Numeric(4, 2), default=0.00, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "part_number", name="uq_tenant_part_number"),
        Index("idx_parts_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
