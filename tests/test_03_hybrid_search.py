from fastapi.testclient import TestClient
from app.models.tenant import Tenant


def test_hybrid_search_sql_filters_with_vector_ordering(client: TestClient, test_tenant: Tenant):
    """
    Scenario 3: Tests Hybrid Search: deterministic SQL filters (unit_cost, lead_time_days)
    filter the candidate set, while vector similarity sorts the qualifying rows.
    """
    headers = {"X-Tenant-ID": str(test_tenant.id)}

    # Create Cheap Motor (Cost $8, Lead Time 5 days)
    client.post("/api/v1/parts", headers=headers, json={
        "part_number": "MTR-CHEAP",
        "name": "BLDC Brushless Drone Motor",
        "unit_cost": 8.00,
        "lead_time_days": 5,
        "part_type": "COMPONENT"
    })

    # Create Expensive Motor (Cost $45, Lead Time 2 days)
    client.post("/api/v1/parts", headers=headers, json={
        "part_number": "MTR-EXPENSIVE",
        "name": "High Performance BLDC Drone Motor",
        "unit_cost": 45.00,
        "lead_time_days": 2,
        "part_type": "COMPONENT"
    })

    # Hybrid Search: semantic search for "drone motor", but with strict SQL filter: max_cost=15.00
    res = client.get("/api/v1/parts", headers=headers, params={
        "semantic_query": "drone motor",
        "max_cost": 15.00,
    })
    assert res.status_code == 200
    results = res.json()

    # Verify that MTR-CHEAP passes the SQL filter, but MTR-EXPENSIVE is completely excluded
    part_numbers = [r["part_number"] for r in results]
    assert "MTR-CHEAP" in part_numbers
    assert "MTR-EXPENSIVE" not in part_numbers
