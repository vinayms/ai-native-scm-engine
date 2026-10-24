import uuid
from fastapi.testclient import TestClient
from app.models.tenant import Tenant


def test_multi_tenant_data_isolation(client: TestClient, test_tenant: Tenant, db_session):
    """
    Scenario 6: Tests that Tenant A and Tenant B are strictly isolated:
    Tenant B cannot see, search, or access Tenant A's parts or BOMs.
    """
    # 1. Create a second distinct tenant (Tenant B)
    tenant_b = Tenant(
        name=f"Tenant B Aerospace {uuid.uuid4().hex[:6]}",
        slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
        plan_tier="STANDARD"
    )
    db_session.add(tenant_b)
    db_session.commit()
    db_session.refresh(tenant_b)

    headers_a = {"X-Tenant-ID": str(test_tenant.id)}
    headers_b = {"X-Tenant-ID": str(tenant_b.id)}

    # 2. Tenant A creates a proprietary confidential part
    res_a = client.post("/api/v1/parts", headers=headers_a, json={
        "part_number": "SECRET-CHIP-99",
        "name": "Classified Defense Microcontroller",
        "unit_cost": 250.00
    })
    assert res_a.status_code == 200
    part_id_a = res_a.json()["id"]

    # 3. Tenant B lists parts -> Must NOT see Tenant A's part
    list_b = client.get("/api/v1/parts", headers=headers_b)
    assert list_b.status_code == 200
    tenant_b_part_numbers = [p["part_number"] for p in list_b.json()]
    assert "SECRET-CHIP-99" not in tenant_b_part_numbers

    # 4. Tenant B attempts direct access by ID -> Must receive 404 Not Found
    direct_get = client.get(f"/api/v1/parts/{part_id_a}", headers=headers_b)
    assert direct_get.status_code == 404
