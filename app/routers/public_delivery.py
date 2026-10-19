"""
Public Delivery Router.
Serves the embeddable JavaScript widget bundle and per-widget configuration
with appropriate HTTP caching headers (long-lived for versioned bundle, short-lived for config).
"""

from pathlib import Path
from fastapi import APIRouter, Depends, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import PublicWidgetConfigResponse
from app.services.widget_service import widget_service

router = APIRouter(tags=["Widget Delivery"])

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get("/widget.js")
async def serve_widget_loader(
    id: str = Query(..., description="Target Widget ID")
):
    """
    Public entry point script.
    Dynamically loads the versioned widget bundle and passes the widget ID context.
    HTTP Caching: public, max-age=3600.
    """
    loader_js = f"""/**
 * FlyRank Embeddable Widget Loader (v1.0.0)
 * Widget ID: {id}
 */
(function() {{
    'use strict';
    var scriptId = 'flyrank-widget-script';
    if (!document.getElementById(scriptId)) {{
        var script = document.createElement('script');
        script.id = scriptId;
        script.src = (window.FLYRANK_WIDGET_BASE_URL || '') + '/static/widget.v1.js';
        script.async = true;
        script.dataset.widgetId = '{id}';
        document.head.appendChild(script);
    }} else {{
        if (window.FlyRankWidget && typeof window.FlyRankWidget.init === 'function') {{
            window.FlyRankWidget.init('{id}');
        }}
    }}
}})();
"""
    return Response(
        content=loader_js,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/static/widget.v1.js")
async def serve_versioned_bundle():
    """
    Versioned widget bundle.
    HTTP Caching: public, max-age=31536000, immutable (1 year long-lived cache).
    """
    bundle_path = STATIC_DIR / "widget.v1.js"
    if bundle_path.exists():
        content = bundle_path.read_text(encoding="utf-8")
    else:
        content = "// Widget bundle placeholder"

    return Response(
        content=content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/widgets/{widget_id}/config", response_model=PublicWidgetConfigResponse)
async def get_widget_public_config(
    widget_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Public configuration endpoint.
    Serves a lightweight JSON payload enabling dynamic client rendering.
    HTTP Caching: public, max-age=60 (short-lived cache).
    """
    config = await widget_service.get_public_config(widget_id=widget_id, db=db)
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return config
