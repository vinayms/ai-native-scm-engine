from fastapi.testclient import TestClient
from app.models.tenant import Tenant


def test_recursive_bom_explosion_and_cost_rollup(client: TestClient, test_tenant: Tenant):
    """
    Scenario 4: Tests multi-tier recursive BOM explosion and cost rollups.
    Tree structure:
    Level 0: Quadcopter Drone (Finished Good, base cost $0)
      ├── Level 1: 4x Motor Subassembly (Qty: 4, scrap: 0%, base cost $0)
      │     ├── Level 2: 1x BLDC Stator (Qty: 1, scrap: 0%, unit cost $10.00, lead time: 8 days)
      │     └── Level 2: 12x Neodymium Magnets (Qty: 12, scrap: 5%, unit cost $0.50, lead time: 14 days)
      └── Level 1: 1x Carbon Fiber Frame (Qty: 1, scrap: 0%, unit cost $30.00, lead time: 5 days)
    """
    headers = {"X-Tenant-ID": str(test_tenant.id)}

    # 1. Create Parts
    p_drone = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "DRONE-X1", "name": "Quadcopter Drone", "part_type": "FINISHED_GOOD", "unit_cost": 0.0, "lead_time_days": 1
    }).json()

    p_motor_sub = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "SUB-MTR-01", "name": "Motor Subassembly", "part_type": "SUB_ASSEMBLY", "unit_cost": 0.0, "lead_time_days": 2
    }).json()

    p_stator = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "ST-BLDC-2204", "name": "BLDC Stator Core", "part_type": "COMPONENT", "unit_cost": 10.00, "lead_time_days": 8
    }).json()

    p_magnet = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "MAG-N52", "name": "N52 Neodymium Magnet", "part_type": "COMPONENT", "unit_cost": 0.50, "lead_time_days": 14
    }).json()

    p_frame = client.post("/api/v1/parts", headers=headers, json={
        "part_number": "FRM-CF-250", "name": "Carbon Fiber Frame", "part_type": "COMPONENT", "unit_cost": 30.00, "lead_time_days": 5
    }).json()

    # 2. Build BOM Tree Edges
    # Motor Subassembly -> Stator (1x)
    client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_motor_sub["id"],
        "component_part_id": p_stator["id"],
        "quantity_required": 1.0,
        "scrap_factor_pct": 0.0
    })

    # Motor Subassembly -> Magnets (12x with 5% scrap allowance)
    # Effective quantity = 12 * 1.05 = 12.6 magnets per motor
    client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_motor_sub["id"],
        "component_part_id": p_magnet["id"],
        "quantity_required": 12.0,
        "scrap_factor_pct": 5.0
    })

    # Drone -> 4x Motor Subassembly
    client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_drone["id"],
        "component_part_id": p_motor_sub["id"],
        "quantity_required": 4.0,
        "scrap_factor_pct": 0.0
    })

    # Drone -> 1x Frame
    client.post("/api/v1/bom", headers=headers, json={
        "parent_part_id": p_drone["id"],
        "component_part_id": p_frame["id"],
        "quantity_required": 1.0,
        "scrap_factor_pct": 0.0
    })

    # 3. Explode the Drone BOM
    explode_res = client.get(f"/api/v1/bom/{p_drone['id']}/explode", headers=headers)
    assert explode_res.status_code == 200, explode_res.text
    data = explode_res.json()

    # Calculations:
    # Frame cost: 1 * $30.00 = $30.00
    # Stator total: 4 motors * 1 stator = 4 stators * $10.00 = $40.00
    # Magnet total: 4 motors * 12 magnets * 1.05 (scrap) = 50.4 magnets * $0.50 = $25.20
    # Expected total rolled up cost = $30.00 + $40.00 + $25.20 = $95.20
    assert data["total_rolled_up_cost"] == 95.20

    # Critical path lead time is the longest lead time in the leaf components:
    # Frame (5 days), Stator (8 days), Magnets (14 days) -> Critical Path = 14 days
    assert data["critical_path_lead_time_days"] == 14
