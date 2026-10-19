"""
Widget Management Router.
Authenticated admin API for creating and managing widgets.
Strictly tenant-isolated: requests without valid auth are rejected (401),
and one tenant can never access or modify another's widgets.
"""

from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Tenant
from app.schemas import WidgetCreate, WidgetUpdate, WidgetResponse
from app.security import get_current_tenant
from app.services.widget_service import widget_service

router = APIRouter(prefix="/api/widgets", tags=["Widget Management"])


@router.get("", response_model=List[WidgetResponse])
async def list_my_widgets(
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """List all widgets belonging to the authenticated tenant."""
    return await widget_service.list_widgets(tenant_id=current_tenant.id, db=db)


@router.post("", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
async def create_widget(
    req: WidgetCreate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Create a new widget for the authenticated tenant."""
    return await widget_service.create_widget(tenant_id=current_tenant.id, req=req, db=db)


@router.get("/{widget_id}", response_model=WidgetResponse)
async def get_widget_details(
    widget_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details and embed snippet for a specific tenant widget."""
    return await widget_service.get_widget_for_tenant(
        widget_id=widget_id,
        tenant_id=current_tenant.id,
        db=db
    )


@router.put("/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: str,
    req: WidgetUpdate,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Update widget configuration."""
    return await widget_service.update_widget(
        widget_id=widget_id,
        tenant_id=current_tenant.id,
        req=req,
        db=db
    )


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget(
    widget_id: str,
    current_tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Delete a widget belonging to the authenticated tenant."""
    await widget_service.delete_widget(
        widget_id=widget_id,
        tenant_id=current_tenant.id,
        db=db
    )
    return None
