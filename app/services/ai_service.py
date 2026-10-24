import os
import re
import json
import hashlib
from typing import List, Dict, Any, Optional
from uuid import UUID
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.part import Part


def _generate_mock_embedding(text_content: str, dimension: int = 768) -> List[float]:
    """
    Generates a deterministic pseudo-semantic 768-dimensional normalized embedding.
    Ensures that similar domain terms (e.g., 'microcontroller', 'mcu', 'cortex')
    project into nearby vector spaces, while dissimilar terms ('bracket', 'screw')
    project far away, enabling full offline testing.
    """
    clean_text = text_content.lower()
    
    # Define semantic cluster biases
    electronics_terms = ["mcu", "microcontroller", "arm", "cortex", "ic", "bldc", "flash", "pin", "chip", "electronic"]
    mechanical_terms = ["bracket", "aluminum", "screw", "cnc", "mount", "chassis", "frame", "metal", "sheet"]
    
    e_score = sum(1.0 for term in electronics_terms if term in clean_text)
    m_score = sum(1.0 for term in mechanical_terms if term in clean_text)

    # Base seed from sha256
    hash_bytes = hashlib.sha256(clean_text.encode("utf-8")).digest()
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], "big"))
    
    vec = rng.randn(dimension).astype(np.float32)
    # Inject cluster bias into the first 48 dimensions for domain cohesion
    if e_score > 0:
        vec[:48] += float(e_score) * 2.5
    if m_score > 0:
        vec[:48] -= float(m_score) * 2.5
        
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def get_embedding(text_content: str) -> List[float]:
    """
    Generates a 768-dimensional embedding.
    Uses Google GenAI text-embedding-004 if GEMINI_API_KEY is available,
    otherwise falls back to deterministic local mock embedding.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.embed_content(
                model="text-embedding-004",
                contents=text_content,
            )
            return response.embeddings[0].values
        except Exception as e:
            # Fall back to mock if API call fails
            return _generate_mock_embedding(text_content)
    
    return _generate_mock_embedding(text_content)


def build_combined_part_text(name: str, description: Optional[str], specs: Dict[str, Any], notes: Optional[str] = None) -> str:
    """Combines multiple columns and JSON specifications into a unified semantic document."""
    specs_str = ", ".join(f"{k}: {v}" for k, v in (specs or {}).items())
    parts = [f"Name: {name}"]
    if description:
        parts.append(f"Description: {description}")
    if specs_str:
        parts.append(f"Specs: {specs_str}")
    if notes:
        parts.append(f"Notes: {notes}")
    return ". ".join(parts)


def find_substitute_parts(
    db: Session,
    tenant_id: UUID,
    target_part_id: UUID,
    limit: int = 5,
    min_similarity: float = 0.50
) -> List[Dict[str, Any]]:
    """
    Queries PostgreSQL with pgvector cosine similarity to find compatible substitute parts.
    """
    target = db.query(Part).filter(Part.tenant_id == tenant_id, Part.id == target_part_id).first()
    if not target or target.embedding is None:
        return []

    sql = text("""
    SELECT 
        p.id,
        p.part_number,
        p.name,
        p.part_type,
        p.unit_cost,
        p.lead_time_days,
        p.ai_risk_score,
        p.specifications,
        ROUND((1 - (p.embedding <=> :target_embedding))::numeric, 4) AS similarity_score
    FROM parts p
    WHERE p.tenant_id = :tenant_id
      AND p.id != :target_id
      AND p.embedding IS NOT NULL
      AND (1 - (p.embedding <=> :target_embedding)) >= :min_similarity
    ORDER BY p.embedding <=> :target_embedding ASC
    LIMIT :limit;
    """)

    # target.embedding is pgvector Vector or list
    emb_str = f"[{','.join(str(x) for x in target.embedding)}]"

    rows = db.execute(sql, {
        "tenant_id": tenant_id,
        "target_id": target_part_id,
        "target_embedding": emb_str,
        "min_similarity": min_similarity,
        "limit": limit
    }).mappings().all()

    substitutes = []
    for r in rows:
        cost_diff = float(r["unit_cost"]) - float(target.unit_cost)
        lead_time_diff = int(r["lead_time_days"]) - int(target.lead_time_days)
        substitutes.append({
            "part_id": str(r["id"]),
            "part_number": r["part_number"],
            "name": r["name"],
            "part_type": r["part_type"],
            "unit_cost": float(r["unit_cost"]),
            "cost_difference": round(cost_diff, 4),
            "lead_time_days": int(r["lead_time_days"]),
            "lead_time_difference": lead_time_diff,
            "similarity_score": float(r["similarity_score"]),
            "specifications": r["specifications"],
        })

    return substitutes


def parse_unstructured_bom(raw_content: str) -> List[Dict[str, Any]]:
    """
    Parses unstructured text, CSV lines, or markdown BOM lists into structured component items.
    """
    items = []
    lines = raw_content.strip().split("\n")
    for line in lines:
        line = line.strip().lstrip("-*0123456789. ")
        if not line or line.lower().startswith("part number") or line.lower().startswith("---"):
            continue
            
        # Parse CSV or pipe-separated or tab-separated formats
        parts = [p.strip() for p in re.split(r"[,|\t]", line) if p.strip()]
        if len(parts) >= 2:
            part_no = parts[0]
            name = parts[1]
            qty = float(parts[2]) if len(parts) > 2 and parts[2].replace(".", "", 1).isdigit() else 1.0
            cost = float(parts[3]) if len(parts) > 3 and parts[3].replace(".", "", 1).isdigit() else 0.0
            items.append({
                "part_number": part_no,
                "name": name,
                "quantity": qty,
                "unit_cost": cost,
            })
        elif len(parts) == 1:
            items.append({
                "part_number": f"GEN-{hashlib.md5(parts[0].encode()).hexdigest()[:6].upper()}",
                "name": parts[0],
                "quantity": 1.0,
                "unit_cost": 0.0,
            })
    return items
