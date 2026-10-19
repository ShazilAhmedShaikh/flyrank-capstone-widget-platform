"""
Tests for Widget Delivery & HTTP Caching.
Validates:
- Embed snippet generation.
- Public config endpoint returns small JSON payload with short-lived cache headers.
- Versioned JavaScript bundle served with long-lived immutable cache headers.
- Proper CORS access on public assets.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_embed_snippet_and_config_delivery(client: AsyncClient, auth_headers: dict):
    # 1. Create a widget
    create_resp = await client.post("/api/widgets", json={
        "name": "Delivery Test Widget",
        "widget_type": "signup",
        "title": "Stay In The Loop",
        "button_text": "Join",
        "fields": [
            {"name": "email", "label": "Email", "type": "email", "required": True}
        ]
    }, headers=auth_headers)
    assert create_resp.status_code == 201
    widget_id = create_resp.json()["id"]

    # 2. Verify Embed Snippet
    snippet = create_resp.json()["snippet"]
    assert f"/widget.js?id={widget_id}" in snippet
    assert "<script" in snippet

    # 3. Test Public Config Delivery with Cache Headers
    config_resp = await client.get(f"/widgets/{widget_id}/config")
    assert config_resp.status_code == 200
    assert config_resp.headers.get("Cache-Control") == "public, max-age=60"
    assert config_resp.headers.get("Access-Control-Allow-Origin") == "*"

    config_data = config_resp.json()
    assert config_data["id"] == widget_id
    assert config_data["title"] == "Stay In The Loop"
    assert len(config_data["fields"]) == 1
    assert config_data["submit_url"].endswith("/submissions")


@pytest.mark.asyncio
async def test_widget_loader_and_versioned_bundle_caching(client: AsyncClient):
    # 1. Test /widget.js loader
    loader_resp = await client.get("/widget.js?id=test-widget-123")
    assert loader_resp.status_code == 200
    assert "application/javascript" in loader_resp.headers.get("Content-Type", "")
    assert loader_resp.headers.get("Cache-Control") == "public, max-age=3600"
    assert "test-widget-123" in loader_resp.text

    # 2. Test /static/widget.v1.js versioned bundle
    bundle_resp = await client.get("/static/widget.v1.js")
    assert bundle_resp.status_code == 200
    assert "application/javascript" in bundle_resp.headers.get("Content-Type", "")
    assert bundle_resp.headers.get("Cache-Control") == "public, max-age=31536000, immutable"
    assert "FlyRankWidget" in bundle_resp.text
