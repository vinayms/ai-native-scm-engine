from typing import Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.part import Part
from app.services.ai_service import get_embedding, parse_unstructured_bom, build_combined_part_text

router = APIRouter(prefix="/ai", tags=["AI Native Operations"])


class IngestBOMRequest(BaseModel):
    raw_content: str


class EmbedTextRequest(BaseModel):
    text: str


@router.post("/ingest-bom")
def ingest_unstructured_bom_endpoint(
    payload: IngestBOMRequest,
    x_tenant_id: UUID = Header(...),
    db: Session = Depends(get_db)
):
    """
    AI-Native Ingestion: Parses unformatted text/CSV into structured parts,
    computes 768-dim embeddings, and registers them into the tenant catalog.
    """
    parsed_items = parse_unstructured_bom(payload.raw_content)
    created_parts = []

    for item in parsed_items:
        part_no = item["part_number"]
        name = item["name"]
        cost = item.get("unit_cost", 0.0)

        # Check if already exists
        existing = db.query(Part).filter(Part.tenant_id == x_tenant_id, Part.part_number == part_no).first()
        if not existing:
            doc_text = build_combined_part_text(name=name, description=f"Imported via AI Ingestion: {name}", specs={})
            emb = get_embedding(doc_text)
            part = Part(
                tenant_id=x_tenant_id,
                part_number=part_no,
                name=name,
                description=f"AI Ingested component {name}",
                part_type="COMPONENT",
                unit_cost=cost,
                lead_time_days=7,
                specifications={"source": "unstructured_import"},
                embedding=emb,
            )
            db.add(part)
            db.commit()
            db.refresh(part)
            created_parts.append({"id": str(part.id), "part_number": part_no, "name": name, "unit_cost": cost})
        else:
            created_parts.append({"id": str(existing.id), "part_number": part_no, "name": name, "status": "already_exists"})

    return {
        "status": "success",
        "total_parsed": len(parsed_items),
        "imported_parts": created_parts
    }


@router.post("/embed")
def embed_text_endpoint(payload: EmbedTextRequest):
    """Generates a 768-dimensional embedding vector for input text."""
    vector = get_embedding(payload.text)
    return {
        "dimension": len(vector),
        "sample": vector[:5],
        "vector": vector
    }
