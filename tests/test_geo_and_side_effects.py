"""
Tests for Geolocation Fallback Chain and Safe Side Effects.
Validates:
- Provider A down -> Provider B answers -> submission enriched (Probe 4 Part 1).
- All providers down -> submission still succeeds without geo (Probe 4 Part 2).
- Secondary side effect throws error -> submission still returns 201 Created and is safely stored (Probe 5).
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_geo_fallback_chain_probe4(client: AsyncClient, auth_headers: dict):
    """
    PROBE 4: Disable geo provider A -> next submission is stored, enriched by provider B.
    Disable both -> stored anyway, without geo.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Geo Form",
        "widget_type": "signup",
        "title": "Geo Test",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # 1. Normal state: Provider A answers
    resp_normal = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"email": "geo.normal@test.com"}
    })
    assert resp_normal.status_code == 201
    sub_id_normal = resp_normal.json()["submission_id"]

    # 2. Disable Provider A: Provider B answers
    resp_fallback = await client.post(
        "/submissions",
        json={"widget_id": widget_id, "data": {"email": "geo.fallback@test.com"}},
        headers={"X-Simulate-Geo-A": "down"}
    )
    assert resp_fallback.status_code == 201
    sub_id_fallback = resp_fallback.json()["submission_id"]

    # 3. Disable BOTH Provider A and Provider B: Stored anyway, without geo (Degrade, never fail!)
    resp_both_down = await client.post(
        "/submissions",
        json={"widget_id": widget_id, "data": {"email": "geo.bothdown@test.com"}},
        headers={"X-Simulate-Geo-A": "down", "X-Simulate-Geo-B": "down"}
    )
    assert resp_both_down.status_code == 201
    sub_id_both_down = resp_both_down.json()["submission_id"]

    # Verify stored records in owner dashboard
    dash_resp = await client.get("/api/dashboard/submissions", headers=auth_headers)
    assert dash_resp.status_code == 200
    submissions = {s["id"]: s for s in dash_resp.json()}

    # Provider A enriched
    assert submissions[sub_id_normal]["geo_provider"] == "provider_a"
    assert submissions[sub_id_normal]["geo_country"] is not None

    # Provider B enriched (fallback)
    assert submissions[sub_id_fallback]["geo_provider"] == "provider_b"
    assert submissions[sub_id_fallback]["geo_country"] is not None

    # Both down -> degraded gracefully
    assert submissions[sub_id_both_down]["geo_provider"] == "none"
    assert submissions[sub_id_both_down]["geo_country"] is None


@pytest.mark.asyncio
async def test_safe_side_effects_isolation_probe5(client: AsyncClient, auth_headers: dict):
    """
    PROBE 5: Force the email/webhook side effect to throw ->
    the submission still returns success and is stored.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Side Effect Form",
        "widget_type": "contact",
        "title": "Side Effect Test",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # Submit with header forcing the notification side effect to raise an exception
    resp = await client.post(
        "/submissions",
        json={
            "widget_id": widget_id,
            "data": {"email": "broken.notifier@test.com"}
        },
        headers={"X-Simulate-Side-Effect-Fail": "true"}
    )

    # MUST return 201 Created and NOT 500!
    assert resp.status_code == 201
    assert resp.json()["success"] is True
    sub_id = resp.json()["submission_id"]

    # Verify that the submission was indeed saved in the database
    dash_resp = await client.get("/api/dashboard/submissions", headers=auth_headers)
    assert dash_resp.status_code == 200
    sub_ids = [s["id"] for s in dash_resp.json()]
    assert sub_id in sub_ids
