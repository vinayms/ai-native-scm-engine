from typing import List, Dict, Any, Set
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.bom import BOMStructure
from app.models.part import Part


class BOMCycleDetectedException(Exception):
    """Raised when a circular dependency is detected in the BOM hierarchy."""
    pass


def check_bom_cycle(db: Session, tenant_id: UUID, parent_id: UUID, component_id: UUID) -> None:
    """
    Validates that adding component_id under parent_id will not create a circular dependency.
    Raises BOMCycleDetectedException if a cycle is found.
    """
    if parent_id == component_id:
        raise BOMCycleDetectedException(f"Self-reference detected: Part {parent_id} cannot contain itself.")

    # Check if parent_id exists anywhere in the sub-tree under component_id
    visited: Set[UUID] = set()
    queue = [component_id]

    while queue:
        curr = queue.pop(0)
        if curr == parent_id:
            raise BOMCycleDetectedException(
                f"Circular dependency detected: Part {parent_id} is already a descendant of Part {component_id}."
            )
        if curr in visited:
            continue
        visited.add(curr)

        children = (
            db.query(BOMStructure.component_part_id)
            .filter(
                BOMStructure.tenant_id == tenant_id,
                BOMStructure.parent_part_id == curr,
            )
            .all()
        )
        for child in children:
            queue.append(child[0])


def explode_bom(db: Session, tenant_id: UUID, root_part_id: UUID) -> Dict[str, Any]:
    """
    Executes a recursive SQL CTE to explode a hierarchical BOM tree.
    Returns:
    - Root part details
    - Exploded lines (leaf & subassembly parts with depth, effective quantity, scrap, line cost)
    - Total rolled-up cost
    - Critical-path bottleneck lead time (days)
    """
    root_part = db.query(Part).filter(Part.tenant_id == tenant_id, Part.id == root_part_id).first()
    if not root_part:
        raise ValueError(f"Root part {root_part_id} not found for tenant {tenant_id}")

    sql = text("""
    WITH RECURSIVE bom_tree AS (
        -- Anchor member: direct children of root part
        SELECT 
            b.id AS bom_id,
            b.parent_part_id,
            b.component_part_id,
            b.quantity_required,
            b.scrap_factor_pct,
            (b.quantity_required * (1 + b.scrap_factor_pct / 100.0)) AS effective_quantity,
            1 AS level_depth,
            ARRAY[b.parent_part_id] AS path,
            b.find_number
        FROM bom_structures b
        WHERE b.tenant_id = :tenant_id AND b.parent_part_id = :root_part_id

        UNION ALL

        -- Recursive member: components of sub-assemblies
        SELECT 
            b.id AS bom_id,
            b.parent_part_id,
            b.component_part_id,
            b.quantity_required,
            b.scrap_factor_pct,
            (bt.effective_quantity * b.quantity_required * (1 + b.scrap_factor_pct / 100.0)) AS effective_quantity,
            bt.level_depth + 1 AS level_depth,
            bt.path || b.parent_part_id AS path,
            b.find_number
        FROM bom_structures b
        JOIN bom_tree bt ON b.parent_part_id = bt.component_part_id
        WHERE b.tenant_id = :tenant_id
          AND NOT b.parent_part_id = ANY(bt.path) -- Prevent infinite loop on cycles
    )
    SELECT 
        bt.bom_id,
        bt.parent_part_id,
        bt.component_part_id,
        p.part_number,
        p.name,
        p.part_type,
        p.uom,
        p.unit_cost,
        p.lead_time_days,
        p.ai_risk_score,
        bt.level_depth,
        bt.quantity_required AS unit_quantity,
        bt.scrap_factor_pct,
        ROUND(bt.effective_quantity::numeric, 4) AS effective_quantity,
        ROUND((bt.effective_quantity * p.unit_cost)::numeric, 4) AS total_line_cost,
        bt.find_number
    FROM bom_tree bt
    JOIN parts p ON bt.component_part_id = p.id
    ORDER BY bt.level_depth ASC, p.part_number ASC;
    """)

    result = db.execute(sql, {"tenant_id": tenant_id, "root_part_id": root_part_id}).mappings().all()

    lines = [dict(row) for row in result]

    # Calculate rollup metrics
    total_cost = sum(float(line["total_line_cost"]) for line in lines)
    critical_lead_time = max([int(line["lead_time_days"]) for line in lines], default=root_part.lead_time_days)
    max_risk = max([float(line["ai_risk_score"]) for line in lines], default=float(root_part.ai_risk_score))

    return {
        "root_part": {
            "id": root_part.id,
            "part_number": root_part.part_number,
            "name": root_part.name,
            "part_type": root_part.part_type,
            "base_cost": float(root_part.unit_cost),
        },
        "total_rolled_up_cost": round(total_cost, 4),
        "critical_path_lead_time_days": critical_lead_time,
        "max_component_risk_score": max_risk,
        "total_component_count": len(lines),
        "components": lines,
    }
