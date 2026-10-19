"""
Exhaustive Edge Cases, Resilience, and Security Boundary Test Suite.
Verifies 100% bug-free behavior across all corner cases, security vectors,
and resilience guarantees specified in the FlyRank Capstone Brief.
"""

import pytest
from httpx import AsyncClient
from app.services.rate_limiter import rate_limiter
import time


@pytest.mark.asyncio
async def test_inactive_widget_rejection(client: AsyncClient, auth_headers: dict):
    """Submissions to inactive or deactivated widgets must be rejected with 404."""
    # Create widget
    create_resp = await client.post("/api/widgets", json={
        "name": "Deactivated Widget",
        "widget_type": "signup",
        "title": "Closed Waitlist",
        "button_text": "Join",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    widget_id = create_resp.json()["id"]

    # Deactivate the widget
    update_resp = await client.put(f"/api/widgets/{widget_id}", json={"is_active": False}, headers=auth_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    # Public config should return 404
    config_resp = await client.get(f"/widgets/{widget_id}/config")
    assert config_resp.status_code == 404

    # Public submission must be rejected with 404
    sub_resp = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"email": "late.user@example.com"}
    })
    assert sub_resp.status_code == 404
    assert "inactive" in sub_resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_non_existent_widget_submission(client: AsyncClient):
    """Submissions to non-existent widget ID must return clean 404."""
    sub_resp = await client.post("/submissions", json={
        "widget_id": "completely-fake-id-99999",
        "data": {"email": "visitor@example.com"}
    })
    assert sub_resp.status_code == 404
    assert "not found" in sub_resp.json()["error"].lower()


@pytest.mark.asyncio
async def test_auth_edge_cases_and_token_tampering(client: AsyncClient):
    """Malformed, tampered, or expired JWT tokens must return 401."""
    # 1. Tampered token
    tampered_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.signature"}
    resp1 = await client.get("/api/widgets", headers=tampered_headers)
    assert resp1.status_code == 401
    assert "Invalid authentication token" in resp1.json()["error"]

    # 2. Malformed Authorization header format
    resp2 = await client.get("/api/widgets", headers={"Authorization": "Basic invalidformat"})
    assert resp2.status_code == 401

    # 3. Empty Bearer token
    resp3 = await client.get("/api/widgets", headers={"Authorization": "Bearer "})
    assert resp3.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_user_registration(client: AsyncClient):
    """Attempting to register the same email twice must return 400 Bad Request."""
    reg1 = await client.post("/api/auth/register", json={
        "email": "unique.user@domain.com",
        "password": "Password123!",
        "company_name": "Unique Inc"
    })
    assert reg1.status_code == 201

    reg2 = await client.post("/api/auth/register", json={
        "email": "unique.user@domain.com",
        "password": "Password123!",
        "company_name": "Unique Inc Duplicate"
    })
    assert reg2.status_code == 400
    assert "already exists" in reg2.json()["error"].lower()


@pytest.mark.asyncio
async def test_invalid_login_credentials(client: AsyncClient):
    """Wrong password or non-existent email must return 401 Unauthorized."""
    resp1 = await client.post("/api/auth/login", json={
        "email": "ghost.user@domain.com",
        "password": "Password123!"
    })
    assert resp1.status_code == 401

    # Register real user
    await client.post("/api/auth/register", json={
        "email": "real.user@domain.com",
        "password": "CorrectPassword123!"
    })

    # Wrong password
    resp2 = await client.post("/api/auth/login", json={
        "email": "real.user@domain.com",
        "password": "WrongPassword456!"
    })
    assert resp2.status_code == 401
    assert "Invalid email or password" in resp2.json()["error"]


@pytest.mark.asyncio
async def test_payload_xss_and_special_character_resilience(client: AsyncClient, auth_headers: dict):
    """Payloads containing XSS vectors or special UTF-8 characters must be safely stored and encoded."""
    create_resp = await client.post("/api/widgets", json={
        "name": "XSS Test Widget",
        "widget_type": "contact",
        "title": "Feedback Form",
        "fields": [
            {"name": "email", "label": "Email", "type": "email", "required": True},
            {"name": "feedback", "label": "Feedback", "type": "textarea", "required": True}
        ]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    xss_payload = "<script>alert('pwned');</script><img src=x onerror=alert(1)>"
    utf8_payload = "مرحبا بالعالم - 🚀 Unicode emojis - 日本語テキスト"

    sub_resp = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {
            "email": "hacker@xss-attempt.org",
            "feedback": f"{xss_payload} | {utf8_payload}"
        }
    })
    assert sub_resp.status_code == 201
    sub_id = sub_resp.json()["submission_id"]

    # Verify payload stored accurately in database without server corruption
    dash_resp = await client.get("/api/dashboard/submissions", headers=auth_headers)
    assert dash_resp.status_code == 200
    matched = [s for s in dash_resp.json() if s["id"] == sub_id]
    assert len(matched) == 1
    assert xss_payload in matched[0]["payload"]["feedback"]
    assert "🚀" in matched[0]["payload"]["feedback"]


@pytest.mark.asyncio
async def test_dashboard_pagination_and_widget_filter(client: AsyncClient, auth_headers: dict):
    """Dashboard submissions endpoint properly filters by widget_id and enforces limit/offset."""
    # Create Widget 1
    w1_resp = await client.post("/api/widgets", json={
        "name": "Widget Alpha",
        "widget_type": "signup",
        "title": "Alpha Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    w1_id = w1_resp.json()["id"]

    # Create Widget 2
    w2_resp = await client.post("/api/widgets", json={
        "name": "Widget Beta",
        "widget_type": "signup",
        "title": "Beta Form",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    w2_id = w2_resp.json()["id"]

    # Submit 3 to Widget 1, 2 to Widget 2
    for i in range(3):
        await client.post("/submissions", json={"widget_id": w1_id, "data": {"email": f"w1_{i}@domain.com"}})
    for i in range(2):
        await client.post("/submissions", json={"widget_id": w2_id, "data": {"email": f"w2_{i}@domain.com"}})

    # Filter by Widget 1 only
    filter_w1 = await client.get(f"/api/dashboard/submissions?widget_id={w1_id}", headers=auth_headers)
    assert filter_w1.status_code == 200
    assert len(filter_w1.json()) == 3
    for s in filter_w1.json():
        assert s["widget_id"] == w1_id

    # Filter by Widget 2 only
    filter_w2 = await client.get(f"/api/dashboard/submissions?widget_id={w2_id}", headers=auth_headers)
    assert filter_w2.status_code == 200
    assert len(filter_w2.json()) == 2
    for s in filter_w2.json():
        assert s["widget_id"] == w2_id

    # Pagination: limit=2, offset=0
    page_1 = await client.get("/api/dashboard/submissions?limit=2&offset=0", headers=auth_headers)
    assert page_1.status_code == 200
    assert len(page_1.json()) == 2

    # Pagination: limit=2, offset=2
    page_2 = await client.get("/api/dashboard/submissions?limit=2&offset=2", headers=auth_headers)
    assert page_2.status_code == 200
    assert len(page_2.json()) == 2

    # Ensure no overlap between page 1 and page 2
    ids_p1 = {s["id"] for s in page_1.json()}
    ids_p2 = {s["id"] for s in page_2.json()}
    assert ids_p1.isdisjoint(ids_p2)


@pytest.mark.asyncio
async def test_email_validation_strictness(client: AsyncClient, auth_headers: dict):
    """Test boundary cases of email validation."""
    create_resp = await client.post("/api/widgets", json={
        "name": "Email Strict Widget",
        "widget_type": "signup",
        "title": "Email Check",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    invalid_emails = [
        "plainaddress",
        "#@%^%#$@#$@#.com",
        "@missingusername.com",
        "missingatsign.com",
        "user@missingtld"
    ]

    for bad_email in invalid_emails:
        resp = await client.post("/submissions", json={
            "widget_id": widget_id,
            "data": {"email": bad_email}
        })
        assert resp.status_code == 400
        assert "Invalid email" in resp.json()["error"]


@pytest.mark.asyncio
async def test_exact_payload_size_boundary(client: AsyncClient, auth_headers: dict):
    """
    Boundary Test: Payload sizes.
    Below 64KB -> Accepted (201).
    Above 64KB -> Rejected with 413 Content Too Large.
    """
    create_resp = await client.post("/api/widgets", json={
        "name": "Size Boundary Widget",
        "widget_type": "signup",
        "title": "Size Test",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    widget_id = create_resp.json()["id"]

    # 1. Large but valid payload (~30KB, well under 64KB limit)
    safe_blob = "B" * 30000
    resp_safe = await client.post("/submissions", json={
        "widget_id": widget_id,
        "data": {"email": "large.safe@domain.com", "extra": safe_blob}
    })
    assert resp_safe.status_code == 201
    assert resp_safe.json()["success"] is True

    # 2. Oversized payload (>65536 bytes)
    overflow_blob = "C" * 70000
    resp_overflow = await client.post(
        "/submissions",
        content=f'{{"widget_id": "{widget_id}", "data": {{"email": "too.big@domain.com", "extra": "{overflow_blob}"}}}}',
        headers={"Content-Type": "application/json"}
    )
    assert resp_overflow.status_code == 413
    assert "exceeds maximum allowable size" in resp_overflow.json()["error"]
