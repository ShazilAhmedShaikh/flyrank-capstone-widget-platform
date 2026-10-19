"""
Tests for Public Submission API, CORS, and Boundary Validation.
Validates:
- Cross-origin submissions with preflight (OPTIONS) support.
- Malformed payloads return clean 4xx JSON errors, NEVER 500.
- Oversized payloads (>64KB) return HTTP 413.
- Missing required fields return HTTP 400.
- Valid submissions safely stored and linked to widget/tenant.
- Idempotency key prevents duplicate row creation.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cors_preflight_and_submission(client: AsyncClient, auth_headers: dict):
    # Create widget
    create_resp = await client.post("/api/widgets", json={
        "name": "CORS Form",
        "widget_type": "contact",
        "title": "Contact Us",
        "button_text": "Send",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    widget_id = create_resp.json()["id"]

    # Test OPTIONS preflight
    preflight_resp = await client.options("/submissions", headers={
        "Origin": "http://localhost:5500",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, Idempotency-Key"
    })
    assert preflight_resp.status_code in (200, 204)
    assert preflight_resp.headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in preflight_resp.headers.get("Access-Control-Allow-Methods", "")

    # Test cross-origin POST submission
    sub_resp = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"email": "cors_tester@example.com"},
        "website_hp": ""
    }, headers={"Origin": "http://localhost:5500"})
    assert sub_resp.status_code == 201
    assert sub_resp.headers.get("Access-Control-Allow-Origin") == "*"
    assert sub_resp.json()["success"] is True
    assert sub_resp.json()["submission_id"] is not None


@pytest.mark.asyncio
async def test_boundary_validation_malformed_and_oversized(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/widgets", json={
        "name": "Boundary Form",
        "widget_type": "signup",
        "title": "Boundary Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # 1. Malformed JSON payload (HTTP 400, NEVER 500)
    malformed_resp = await client.post(
        "/submissions",
        content="This is plain invalid json {{{",
        headers={"Content-Type": "application/json"}
    )
    assert malformed_resp.status_code == 400
    assert "Malformed JSON" in malformed_resp.json()["error"]

    # 2. Oversized payload (>64KB -> HTTP 413)
    huge_data = "A" * (70 * 1024)  # 70 KB
    oversized_resp = await client.post(
        "/submissions",
        content=f'{{"widget_id": "{widget_id}", "data": {{"huge": "{huge_data}"}}}}',
        headers={"Content-Type": "application/json"}
    )
    assert oversized_resp.status_code == 413
    assert "exceeds maximum allowable size" in oversized_resp.json()["error"]

    # 3. Missing required field (HTTP 400)
    missing_resp = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"name": "No Email Provided"}
    })
    assert missing_resp.status_code == 400
    assert "Missing required field" in missing_resp.json()["error"]

    # 4. Invalid email format (HTTP 400)
    invalid_email_resp = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"email": "not-an-email-address"}
    })
    assert invalid_email_resp.status_code == 400
    assert "Invalid email" in invalid_email_resp.json()["error"]


@pytest.mark.asyncio
async def test_idempotency_key_replay(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post("/api/widgets", json={
        "name": "Idempotent Form",
        "widget_type": "signup",
        "title": "Idempotency Test",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    idempotency_key = "test-idem-key-999"

    # First attempt -> creates new submission
    resp1 = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"email": "idempotent.user@example.com"}
    }, headers={"Idempotency-Key": idempotency_key})
    assert resp1.status_code == 201
    sub_id_1 = resp1.json()["submission_id"]

    # Second attempt with same idempotency key -> returns existing submission
    resp2 = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"email": "idempotent.user@example.com"}
    }, headers={"Idempotency-Key": idempotency_key})
    assert resp2.status_code == 201
    sub_id_2 = resp2.json()["submission_id"]

    # Must match exactly
    assert sub_id_1 == sub_id_2
    assert "idempotent replay" in resp2.json()["message"]
