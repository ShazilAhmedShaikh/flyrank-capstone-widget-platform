"""
Tests for Abuse Protection and Spam Defense.
Validates:
- Rapid burst submissions trigger HTTP 429 Too Many Requests (Probe 3).
- Legitimate requests from a different IP still succeed during active rate limiting.
- Honeypot anti-bot field trap blocks spam submissions with HTTP 400 (Probe 6).
"""

import pytest
from httpx import AsyncClient
from app.services.rate_limiter import rate_limiter


@pytest.mark.asyncio
async def test_honeypot_spam_prevention_probe6(client: AsyncClient, auth_headers: dict):
    """
    PROBE 6: Fill the honeypot field like a bot would -> submission is rejected.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Spam Guard Form",
        "widget_type": "signup",
        "title": "Spam Guard Test",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # Bot fills out the hidden honeypot field
    bot_payload = {
        "widget_id": widget_id,
        "data": {"email": "bot@spammer-domain.net"},
        "website_hp": "http://malicious-spam-url.com/promote"
    }

    resp = await client.post("/submissions", json=bot_payload)
    assert resp.status_code == 400
    assert "honeypot trap triggered" in resp.json()["error"]


@pytest.mark.asyncio
async def test_rate_limiting_burst_and_recovery_probe3(client: AsyncClient, auth_headers: dict):
    """
    PROBE 3: Fire a burst of rapid submissions -> 429s appear,
    and a normal request right after (from another client or after limit) still succeeds.
    """
    rate_limiter.reset()

    create_resp = await client.post("/api/widgets", json={
        "name": "Rate Limit Form",
        "widget_type": "contact",
        "title": "Rate Limit Test",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # Send rapid burst of submissions from IP 192.168.1.100 (burst limit is 5)
    abuser_ip = "192.168.1.100"
    legit_ip = "192.168.1.200"

    responses = []
    for i in range(8):
        resp = await client.post(
            "/submissions",
            json={
                "widget_id": widget_id,
                "data": {"email": f"burst_{i}@flood.com"}
            },
            headers={"X-Forwarded-For": abuser_ip}
        )
        responses.append(resp.status_code)

    # First 5 should succeed (201), 6th+ must return 429
    assert responses[:5] == [201, 201, 201, 201, 201]
    assert 429 in responses[5:]

    # Verify that a legitimate user from a different IP can still submit successfully!
    legit_resp = await client.post(
        "/submissions",
        json={
            "widget_id": widget_id,
            "data": {"email": "legit.user@company.com"}
        },
        headers={"X-Forwarded-For": legit_ip}
    )
    assert legit_resp.status_code == 201
    assert legit_resp.json()["success"] is True
