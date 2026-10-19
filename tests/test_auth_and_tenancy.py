"""
Tests for Authentication and Strict Multi-Tenant Isolation.
Validates:
- Requests without valid auth are rejected with HTTP 401.
- Full CRUD for widgets under authenticated tenant.
- Tenant A cannot read, update, or delete Tenant B's widgets (HTTP 404).
- Tenant A cannot access Tenant B's submissions in the dashboard.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_auth_rejected_without_credentials(client: AsyncClient):
    """Requests without valid auth are strictly rejected with 401."""
    resp = await client.get("/api/widgets")
    assert resp.status_code == 401
    assert "Missing authentication credentials" in resp.json()["error"]

    resp = await client.post("/api/widgets", json={"name": "test", "title": "test"})
    assert resp.status_code == 401

    resp = await client.get("/api/dashboard/stats")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_widget_crud_workflow(client: AsyncClient, auth_headers: dict):
    """Authenticated tenant can perform full CRUD on their widgets."""
    # 1. Create Widget
    create_payload = {
        "name": "Signup Widget",
        "widget_type": "signup",
        "title": "Join Our Early Beta",
        "description": "Be the first to test our API.",
        "button_text": "Sign Up",
        "fields": [
            {"name": "email", "label": "Your Email", "type": "email", "required": True, "placeholder": "test@test.com"}
        ],
        "display_options": {"primary_color": "#2563eb"}
    }
    create_resp = await client.post("/api/widgets", json=create_payload, headers=auth_headers)
    assert create_resp.status_code == 201
    widget_data = create_resp.json()
    widget_id = widget_data["id"]
    assert widget_data["name"] == "Signup Widget"
    assert "<script" in widget_data["snippet"]

    # 2. List Widgets
    list_resp = await client.get("/api/widgets", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # 3. Get Widget Details
    get_resp = await client.get(f"/api/widgets/{widget_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == widget_id

    # 4. Update Widget
    update_resp = await client.put(f"/api/widgets/{widget_id}", json={"title": "Updated Title"}, headers=auth_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Title"

    # 5. Delete Widget
    del_resp = await client.delete(f"/api/widgets/{widget_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # 6. Verify Gone
    verify_resp = await client.get(f"/api/widgets/{widget_id}", headers=auth_headers)
    assert verify_resp.status_code == 404


@pytest.mark.asyncio
async def test_multi_tenant_isolation_proven(
    client: AsyncClient,
    auth_headers: dict,
    tenant_b_auth_headers: dict
):
    """
    Strict Tenant Isolation:
    Tenant B cannot view, edit, or delete Tenant A's widgets,
    and cannot see Tenant A's dashboard submissions.
    """
    # Tenant A creates a widget
    create_resp = await client.post("/api/widgets", json={
        "name": "Tenant A Secret Widget",
        "widget_type": "signup",
        "title": "Private Tenant A Form",
        "button_text": "Submit",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True}]
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    widget_a_id = create_resp.json()["id"]

    # Tenant B tries to read Tenant A's widget -> 404 Not Found
    b_read_resp = await client.get(f"/api/widgets/{widget_a_id}", headers=tenant_b_auth_headers)
    assert b_read_resp.status_code == 404

    # Tenant B tries to update Tenant A's widget -> 404 Not Found
    b_update_resp = await client.put(
        f"/api/widgets/{widget_a_id}",
        json={"title": "Hacked Title"},
        headers=tenant_b_auth_headers
    )
    assert b_update_resp.status_code == 404

    # Tenant B tries to delete Tenant A's widget -> 404 Not Found
    b_del_resp = await client.delete(f"/api/widgets/{widget_a_id}", headers=tenant_b_auth_headers)
    assert b_del_resp.status_code == 404

    # Tenant B's widget list should NOT include Tenant A's widget
    b_list_resp = await client.get("/api/widgets", headers=tenant_b_auth_headers)
    assert b_list_resp.status_code == 200
    assert len(b_list_resp.json()) == 0

    # Tenant A submits a lead through the public submission endpoint
    sub_resp = await client.post("/submissions", json={
        "widget_id": widget_a_id,
        "data": {"email": "visitor@domain.com"}
    })
    assert sub_resp.status_code == 201

    # Tenant B inspects their dashboard -> must see 0 submissions
    b_dash_resp = await client.get("/api/dashboard/stats", headers=tenant_b_auth_headers)
    assert b_dash_resp.status_code == 200
    assert b_dash_resp.json()["total_submissions"] == 0

    b_subs_resp = await client.get("/api/dashboard/submissions", headers=tenant_b_auth_headers)
    assert b_subs_resp.status_code == 200
    assert len(b_subs_resp.json()) == 0

    # Tenant A inspects their dashboard -> sees their 1 submission
    a_dash_resp = await client.get("/api/dashboard/stats", headers=auth_headers)
    assert a_dash_resp.status_code == 200
    assert a_dash_resp.json()["total_submissions"] == 1
