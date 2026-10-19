"""
Owner Dashboard & Analytics Router.
Authenticated endpoints providing tenant-scoped metrics, aggregations,
and submission records.
"""

from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.database import get_db
from app.models import Tenant, Widget, Submission
from app.schemas import (
    DashboardStatsResponse,
    WidgetStatItem,
    GeoStatItem,
    SubmissionDetailResponse
)
from app.security import get_current_tenant
import json

router = APIRouter(prefix="/api/dashboard", tags=["Owner Dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve aggregated metrics for the authenticated tenant:
    - Total submissions
    - Submissions in last 24h
    - Submissions in last 7 days
    - Per-widget volume breakdown
    - Geolocation breakdown
    """
    tenant_id = current_tenant.id
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)

    # Total submissions
    stmt_total = select(func.count(Submission.id)).where(Submission.tenant_id == tenant_id)
    res_total = await db.execute(stmt_total)
    total_count = res_total.scalar() or 0

    # Last 24 hours
    stmt_24h = select(func.count(Submission.id)).where(
        Submission.tenant_id == tenant_id,
        Submission.created_at >= one_day_ago
    )
    res_24h = await db.execute(stmt_24h)
    count_24h = res_24h.scalar() or 0

    # Last 7 days
    stmt_7d = select(func.count(Submission.id)).where(
        Submission.tenant_id == tenant_id,
        Submission.created_at >= seven_days_ago
    )
    res_7d = await db.execute(stmt_7d)
    count_7d = res_7d.scalar() or 0

    # Per-widget breakdown
    stmt_widgets = (
        select(Widget.id, Widget.name, func.count(Submission.id).label("sub_count"))
        .outerjoin(Submission, Submission.widget_id == Widget.id)
        .where(Widget.tenant_id == tenant_id)
        .group_by(Widget.id, Widget.name)
        .order_by(desc("sub_count"))
    )
    res_widgets = await db.execute(stmt_widgets)
    per_widget = [
        WidgetStatItem(widget_id=r[0], widget_name=r[1], submission_count=r[2])
        for r in res_widgets.all()
    ]

    # Geolocation breakdown
    stmt_geo = (
        select(
            func.coalesce(Submission.geo_country, "Unknown").label("country"),
            func.count(Submission.id).label("country_count")
        )
        .where(Submission.tenant_id == tenant_id)
        .group_by("country")
        .order_by(desc("country_count"))
        .limit(10)
    )
    res_geo = await db.execute(stmt_geo)
    geo_breakdown = [
        GeoStatItem(country=r[0], count=r[1])
        for r in res_geo.all()
    ]

    return DashboardStatsResponse(
        total_submissions=total_count,
        last_24h_count=count_24h,
        last_7d_count=count_7d,
        per_widget=per_widget,
        geo_breakdown=geo_breakdown
    )


@router.get("/submissions", response_model=List[SubmissionDetailResponse])
async def list_dashboard_submissions(
    widget_id: Optional[str] = Query(None, description="Filter by specific widget ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve paginated submission records belonging to the authenticated tenant.
    """
    stmt = select(Submission).where(Submission.tenant_id == current_tenant.id)

    if widget_id:
        stmt = stmt.where(Submission.widget_id == widget_id)

    stmt = stmt.order_by(Submission.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(stmt)
    submissions = res.scalars().all()

    output = []
    for s in submissions:
        payload = {}
        try:
            payload = json.loads(s.payload_json or "{}")
        except Exception:
            pass

        output.append(SubmissionDetailResponse(
            id=s.id,
            widget_id=s.widget_id,
            payload=payload,
            geo_country=s.geo_country,
            geo_city=s.geo_city,
            geo_provider=s.geo_provider,
            status=s.status,
            created_at=s.created_at
        ))

    return output
