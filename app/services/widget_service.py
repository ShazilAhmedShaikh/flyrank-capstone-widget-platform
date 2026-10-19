"""
Widget Management Service.
Handles tenant-scoped CRUD operations and embed snippet generation.
Guarantees tenant isolation: one tenant can never access or modify another tenant's widgets.
"""

import json
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Widget
from app.schemas import (
    WidgetCreate,
    WidgetUpdate,
    WidgetResponse,
    PublicWidgetConfigResponse,
    FormFieldSchema
)
from app.config import settings


class WidgetService:
    @staticmethod
    def generate_snippet(widget_id: str, base_url: str = settings.BASE_URL) -> str:
        """Generate embed snippet HTML script tag."""
        return f'<script src="{base_url}/widget.js?id={widget_id}" async></script>'

    @staticmethod
    def _model_to_response(widget: Widget, base_url: str = settings.BASE_URL) -> WidgetResponse:
        fields = [FormFieldSchema(**f) for f in json.loads(widget.fields_json or "[]")]
        display_options = json.loads(widget.display_options_json or "{}")
        snippet = WidgetService.generate_snippet(widget.id, base_url)

        return WidgetResponse(
            id=widget.id,
            tenant_id=widget.tenant_id,
            name=widget.name,
            widget_type=widget.widget_type,
            title=widget.title,
            description=widget.description,
            button_text=widget.button_text,
            fields=fields,
            display_options=display_options,
            is_active=widget.is_active,
            snippet=snippet,
            created_at=widget.created_at,
            updated_at=widget.updated_at
        )

    async def list_widgets(self, tenant_id: str, db: AsyncSession) -> List[WidgetResponse]:
        """List all widgets belonging strictly to the authenticated tenant."""
        stmt = select(Widget).where(Widget.tenant_id == tenant_id).order_by(Widget.created_at.desc())
        result = await db.execute(stmt)
        widgets = result.scalars().all()
        return [self._model_to_response(w) for w in widgets]

    async def create_widget(self, tenant_id: str, req: WidgetCreate, db: AsyncSession) -> WidgetResponse:
        """Create a new widget under the tenant's namespace."""
        fields_json = json.dumps([f.model_dump() for f in req.fields])
        display_options_json = json.dumps(req.display_options)

        widget = Widget(
            tenant_id=tenant_id,
            name=req.name,
            widget_type=req.widget_type,
            title=req.title,
            description=req.description,
            button_text=req.button_text,
            fields_json=fields_json,
            display_options_json=display_options_json,
            is_active=True
        )
        db.add(widget)
        await db.commit()
        await db.refresh(widget)
        return self._model_to_response(widget)

    async def get_widget_for_tenant(self, widget_id: str, tenant_id: str, db: AsyncSession) -> WidgetResponse:
        """Retrieve a specific widget, enforcing strict tenant ownership isolation."""
        stmt = select(Widget).where(Widget.id == widget_id, Widget.tenant_id == tenant_id)
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Widget '{widget_id}' not found"
            )
        return self._model_to_response(widget)

    async def update_widget(
        self,
        widget_id: str,
        tenant_id: str,
        req: WidgetUpdate,
        db: AsyncSession
    ) -> WidgetResponse:
        """Update widget fields, verifying tenant ownership."""
        stmt = select(Widget).where(Widget.id == widget_id, Widget.tenant_id == tenant_id)
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Widget '{widget_id}' not found"
            )

        if req.name is not None:
            widget.name = req.name
        if req.widget_type is not None:
            widget.widget_type = req.widget_type
        if req.title is not None:
            widget.title = req.title
        if req.description is not None:
            widget.description = req.description
        if req.button_text is not None:
            widget.button_text = req.button_text
        if req.fields is not None:
            widget.fields_json = json.dumps([f.model_dump() for f in req.fields])
        if req.display_options is not None:
            widget.display_options_json = json.dumps(req.display_options)
        if req.is_active is not None:
            widget.is_active = req.is_active

        await db.commit()
        await db.refresh(widget)
        return self._model_to_response(widget)

    async def delete_widget(self, widget_id: str, tenant_id: str, db: AsyncSession) -> None:
        """Delete widget and cascade associated submissions."""
        stmt = select(Widget).where(Widget.id == widget_id, Widget.tenant_id == tenant_id)
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Widget '{widget_id}' not found"
            )

        await db.delete(widget)
        await db.commit()

    async def get_public_config(self, widget_id: str, db: AsyncSession) -> PublicWidgetConfigResponse:
        """Fetch public widget configuration for client rendering."""
        stmt = select(Widget).where(Widget.id == widget_id, Widget.is_active == True)
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Widget not found or is currently inactive"
            )

        fields = [FormFieldSchema(**f) for f in json.loads(widget.fields_json or "[]")]
        display_options = json.loads(widget.display_options_json or "{}")

        return PublicWidgetConfigResponse(
            id=widget.id,
            widget_type=widget.widget_type,
            title=widget.title,
            description=widget.description,
            button_text=widget.button_text,
            fields=fields,
            display_options=display_options,
            submit_url=f"{settings.BASE_URL}/submissions"
        )


widget_service = WidgetService()
