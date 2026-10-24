from fastapi.testclient import TestClient
from app.models.tenant import Tenant


def test_pgvector_cosine_similarity_clustering(client: TestClient, test_tenant: Tenant):
    """
    Scenario 1: Tests that pgvector groups functionally similar components together
    (STM32 and GD32 microcontrollers) while rejecting unrelated mechanical parts (Aluminum Bracket).
    """
    headers = {"X-Tenant-ID": str(test_tenant.id)}

    # 1. Create Target Part: STM32 Microcontroller
    res1 = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "MCU-STM32F405",
        "name": "STM32F405 32-bit Microcontroller",
        "description": "ARM Cortex-M4 168MHz MCU 64-pin LQFP",
        "unit_cost": 5.50,
        "lead_time_days": 14,
        "specifications": {"core": "Cortex-M4", "pin_count": 64}
    })
    assert res1.status_code == 200, res1.text
    stm32_id = res1.json()["id"]

    # 2. Create Candidate Part: GigaDevice Clone (Compatible IC)
    res2 = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "MCU-GD32F405",
        "name": "GigaDevice GD32F405 Compatible MCU",
        "description": "32-bit ARM Cortex-M4 compatible microcontroller IC 64-pin",
        "unit_cost": 4.20,
        "lead_time_days": 5,
        "specifications": {"core": "Cortex-M4", "pin_count": 64}
    })
    assert res2.status_code == 200

    # 3. Create Dissimilar Part: Mechanical Bracket
    res3 = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "BRK-ALUM-01",
        "name": "Aluminum Mounting Bracket",
        "description": "CNC milled 6061-T6 aluminum mounting bracket for chassis",
        "unit_cost": 12.00,
        "lead_time_days": 10,
        "specifications": {"material": "AL6061", "finish": "anodized"}
    })
    assert res3.status_code == 200

    # 4. Search substitutes for STM32
    sub_res = client.get(f"/api/v1/parts/{stm32_id}/substitutes", headers=headers)
    assert sub_res.status_code == 200
    data = sub_res.json()

    assert data["substitutes_found"] >= 1
    top_match = data["results"][0]

    # Verify top match is the GigaDevice MCU with high similarity
    assert top_match["part_number"] == "MCU-GD32F405"
    assert top_match["similarity_score"] > 0.80
    assert top_match["cost_difference"] == -1.30  # Saves $1.30 per unit
