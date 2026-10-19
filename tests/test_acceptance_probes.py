"""
Formal Verification Suite for all Layer 2 Acceptance Probes (Probes 1 to 6).
Matches Section 13 of the FlyRank Capstone Specification.
"""

import pytest
from httpx import AsyncClient
from app.services.rate_limiter import rate_limiter


@pytest.mark.asyncio
async def test_probe_1_second_origin_submission(client: AsyncClient, auth_headers: dict):
    """
    PROBE 1 — POST a valid submission from the second-origin test page
    -> stored, 2xx, and visible via the dashboard API.
    """
    # 1. Create a widget
    create_resp = await client.post("/api/widgets", json={
        "name": "Probe 1 Widget",
        "widget_type": "signup",
        "title": "Probe 1 Newsletter",
        "fields": [
            {"name": "email", "label": "Work Email", "type": "email", "required": True},
            {"name": "name", "label": "Full Name", "type": "text", "required": True}
        ]
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    widget_id = create_resp.json()["id"]

    # 2. Simulate submission from customer origin http://localhost:5500
    sub_resp = await client.post(
        "/submissions",
        json={
            "widget_id": widget_id,
            "data": {
                "email": "probe1.visitor@second-origin.com",
                "name": "Alex Mercer"
            },
            "website_hp": ""
        },
        headers={
            "Origin": "http://localhost:5500",
            "Referer": "http://localhost:5500/index.html"
        }
    )
    assert sub_resp.status_code == 201
    assert sub_resp.headers.get("Access-Control-Allow-Origin") == "*"
    res_json = sub_resp.json()
    assert res_json["success"] is True
    sub_id = res_json["submission_id"]

    # 3. Verify submission is visible in owner dashboard
    dash_resp = await client.get("/api/dashboard/submissions", headers=auth_headers)
    assert dash_resp.status_code == 200
    subs = dash_resp.json()
    matched = [s for s in subs if s["id"] == sub_id]
    assert len(matched) == 1
    assert matched[0]["payload"]["email"] == "probe1.visitor@second-origin.com"


@pytest.mark.asyncio
async def test_probe_2_malformed_and_oversized_payloads(client: AsyncClient, auth_headers: dict):
    """
    PROBE 2 — Send a malformed and an oversized payload
    -> clean 4xx JSON errors, never a 500.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Probe 2 Widget",
        "widget_type": "signup",
        "title": "Probe 2 Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # Part A: Malformed syntax
    malformed_resp = await client.post(
        "/submissions",
        content="not a valid json string {missing_quote: 123",
        headers={"Content-Type": "application/json"}
    )
    assert malformed_resp.status_code == 400
    assert "error" in malformed_resp.json()
    assert malformed_resp.status_code < 500

    # Part B: Oversized payload (> 64 KB)
    huge_payload = "X" * (66 * 1024)
    oversized_resp = await client.post(
        "/submissions",
        content=f'{{"widget_id": "{widget_id}", "data": {{"blob": "{huge_payload}"}}}}',
        headers={"Content-Type": "application/json"}
    )
    assert oversized_resp.status_code == 413
    assert "exceeds maximum allowable size" in oversized_resp.json()["error"]
    assert oversized_resp.status_code < 500


@pytest.mark.asyncio
async def test_probe_3_rate_limiting_burst(client: AsyncClient, auth_headers: dict):
    """
    PROBE 3 — Fire a burst of rapid submissions
    -> 429s appear, and a normal request right after still succeeds.
    """
    rate_limiter.reset()

    create_resp = await client.post("/api/widgets", json={
        "name": "Probe 3 Widget",
        "widget_type": "signup",
        "title": "Probe 3 Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    burst_ip = "10.0.0.99"
    regular_ip = "10.0.0.100"

    # Rapid burst
    statuses = []
    for i in range(7):
        r = await client.post(
            "/submissions",
            json={"widget_id": widget_id, "data": {"email": f"flood{i}@test.com"}},
            headers={"X-Forwarded-For": burst_ip}
        )
        statuses.append(r.status_code)

    assert 429 in statuses

    # Normal request right after from regular client succeeds
    normal_resp = await client.post(
        "/submissions",
        json={"widget_id": widget_id, "data": {"email": "legitimate.user@clean.com"}},
        headers={"X-Forwarded-For": regular_ip}
    )
    assert normal_resp.status_code == 201
    assert normal_resp.json()["success"] is True


@pytest.mark.asyncio
async def test_probe_4_geo_provider_fallback_chain(client: AsyncClient, auth_headers: dict):
    """
    PROBE 4 — Disable geo provider A -> the next submission is stored, enriched by provider B.
    Disable both -> stored anyway, without geo.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Probe 4 Widget",
        "widget_type": "signup",
        "title": "Probe 4 Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # Step 1: Disable Provider A -> Provider B responds
    resp_b = await client.post(
        "/submissions",
        json={"widget_id": widget_id, "data": {"email": "fallback.b@test.com"}},
        headers={"X-Simulate-Geo-A": "down"}
    )
    assert resp_b.status_code == 201
    sub_b_id = resp_b.json()["submission_id"]

    # Step 2: Disable both Provider A and B -> Stored anyway without geo
    resp_none = await client.post(
        "/submissions",
        json={"widget_id": widget_id, "data": {"email": "fallback.none@test.com"}},
        headers={"X-Simulate-Geo-A": "down", "X-Simulate-Geo-B": "down"}
    )
    assert resp_none.status_code == 201
    sub_none_id = resp_none.json()["submission_id"]

    # Step 3: Inspect database storage via dashboard
    dash = await client.get("/api/dashboard/submissions", headers=auth_headers)
    assert dash.status_code == 200
    by_id = {s["id"]: s for s in dash.json()}

    assert by_id[sub_b_id]["geo_provider"] == "provider_b"
    assert by_id[sub_b_id]["geo_country"] is not None

    assert by_id[sub_none_id]["geo_provider"] == "none"
    assert by_id[sub_none_id]["geo_country"] is None


@pytest.mark.asyncio
async def test_probe_5_side_effect_failure_isolation(client: AsyncClient, auth_headers: dict):
    """
    PROBE 5 — Force the email/webhook side effect to throw
    -> the submission still returns success and is stored.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Probe 5 Widget",
        "widget_type": "signup",
        "title": "Probe 5 Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # Force side effect failure
    resp = await client.post(
        "/submissions",
        json={"widget_id": widget_id, "data": {"email": "sideeffect.fail@test.com"}},
        headers={"X-Simulate-Side-Effect-Fail": "true"}
    )
    assert resp.status_code == 201
    assert resp.json()["success"] is True
    sub_id = resp.json()["submission_id"]

    # Confirm it is safely stored in database
    dash = await client.get("/api/dashboard/submissions", headers=auth_headers)
    assert dash.status_code == 200
    ids = [s["id"] for s in dash.json()]
    assert sub_id in ids


@pytest.mark.asyncio
async def test_probe_6_honeypot_bot_defense(client: AsyncClient, auth_headers: dict):
    """
    PROBE 6 — Fill the honeypot field like a bot would
    -> the submission is silently dropped or rejected.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Probe 6 Widget",
        "widget_type": "signup",
        "title": "Probe 6 Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    bot_resp = await client.post(
        "/submissions",
        json={
            "widget_id": widget_id,
            "data": {"email": "automated.spambot@spamfarm.com"},
            "website_hp": "automated honeypot spam input"
        }
    )
    assert bot_resp.status_code == 400
    assert "honeypot trap triggered" in bot_resp.json()["error"]
