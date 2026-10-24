from fastapi.testclient import TestClient
from app.models.tenant import Tenant


def test_bom_cycle_detection_prevention(client: TestClient, test_tenant: Tenant):
    """
    Scenario 5: Tests that cycle detection prevents circular dependencies in the BOM graph:
    1. Prevents self-reference (Part A cannot contain Part A).
    2. Prevents multi-hop cycle (Part A -> Part B -> Part C -> Part A).
    """
    headers = {"X-Tenant-ID": str(test_tenant.id)}

    # Create Parts A, B, and C
    p_a = client.post("/api/v1/parts", headers=headers, json={"part_number": "CYC-A", "name": "Assembly A"}).json()
    p_b = client.post("/api/v1/parts", headers=headers, json={"part_number": "CYC-B", "name": "Subassembly B"}).json()
    p_c = client.post("/api/v1/parts", headers=headers, json={"part_number": "CYC-C", "name": "Component C"}).json()

    # 1. Test Self-Reference: A -> A
    self_res = client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_a["id"],
        "component_part_id": p_a["id"],
        "quantity_required": 1.0
    })
    assert self_res.status_code == 400
    assert "Self-reference detected" in self_res.json()["detail"]

    # 2. Add valid edges: A -> B and B -> C
    res_ab = client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_a["id"],
        "component_part_id": p_b["id"],
        "quantity_required": 1.0
    })
    assert res_ab.status_code == 200

    res_bc = client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_b["id"],
        "component_part_id": p_c["id"],
        "quantity_required": 1.0
    })
    assert res_bc.status_code == 200

    # 3. Attempt to add cycle: C -> A (which would create A -> B -> C -> A)
    cycle_res = client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_c["id"],
        "component_part_id": p_a["id"],
        "quantity_required": 1.0
    })
    assert cycle_res.status_code == 400
    assert "Circular dependency detected" in cycle_res.json()["detail"]
