"""Integration tests for frontend dashboard and static asset delivery."""

import pytest


@pytest.mark.asyncio
async def test_frontend_dashboard_served(client):
    res = await client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    html = res.text

    # Verify core branding & title
    assert "Unlimited OCR" in html
    assert "Enterprise Cloud" in html

    # Verify core workflows are present
    assert "Dashboard" in html
    assert "Convert Document" in html
    assert "Batch Processing" in html
    assert "Conversion History" in html

    # Verify developer & API management
    assert "API Keys" in html
    assert "API Documentation" in html
    assert "Webhooks" in html
    assert "Usage &amp; Quotas" in html or "Usage & Quotas" in html

    # Verify admin and platform settings
    assert "Settings" in html
    assert "Admin Console" in html

    # Verify split-screen viewer components
    assert "Source Document" in html
    assert "Markdown" in html
    assert "JSON Contract" in html
    assert "Tables" in html


@pytest.mark.asyncio
async def test_dashboard_route_alias(client):
    res = await client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


@pytest.mark.asyncio
async def test_api_info_endpoint(client):
    res = await client.get("/api")
    assert res.status_code == 200
    data = res.json()
    assert data["service"] == "Unlimited OCR Cloud"
    assert data["docs"] == "/docs"
    assert data["api_v1"] == "/v1"
