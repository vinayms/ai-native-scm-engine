from fastapi.testclient import TestClient
from app.models.tenant import Tenant


def test_multi_column_concatenated_embeddings(client: TestClient, test_tenant: Tenant):
    """
    Scenario 2: Tests that combining multiple columns (name, description, specifications)
    into a single document embedding enables searching by properties stored in distinct columns.
    """
    headers = {"X-Tenant-ID": str(test_tenant.id)}

    # Create a part where 'name' has the title, but 'specifications' has the package type
    res = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "RES-10K-0805",
        "name": "Precision Surface Mount Resistor",
        "description": "High stability automotive grade component",
        "unit_cost": 0.05,
        "lead_time_days": 2,
        "specifications": {
            "resistance": "10k_ohm",
            "tolerance": "0.1%",
            "package": "0805_SMD"
        }
    })
    assert res.status_code == 200

    # 1. Search by a term present ONLY in specifications ('0805_SMD')
    search_specs = client.get("/api/v1/parts", headers=headers, params={"semantic_query": "0805 SMD resistor"})
    assert search_specs.status_code == 200
    parts_by_specs = search_specs.json()
    assert any(p["part_number"] == "RES-10K-0805" for p in parts_by_specs)

    # 2. Search by a term present ONLY in description ('automotive grade')
    search_desc = client.get("/api/v1/parts", headers=headers, params={"semantic_query": "automotive precision resistor"})
    assert search_desc.status_code == 200
    parts_by_desc = search_desc.json()
    assert any(p["part_number"] == "RES-10K-0805" for p in parts_by_desc)
