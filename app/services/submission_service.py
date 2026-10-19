"""
Submission Ingestion & Hardening Pipeline Service.
Coordinates boundary validation, rate limiting, anti-bot honeypot defense,
idempotency deduplication, resilient geo enrichment, and safe side effects.
"""

import json
import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Widget, Submission, Tenant
from app.schemas import PublicSubmissionRequest, PublicSubmissionResponse
from app.services.rate_limiter import rate_limiter
from app.services.geo_enrichment import geo_enrichment_service
from app.services.side_effects import side_effect_worker
from app.security import hash_ip

logger = logging.getLogger("submission_service")


class SubmissionService:
    async def process_submission(
        self,
        req: PublicSubmissionRequest,
        client_ip: str,
        idempotency_key: Optional[str],
        db: AsyncSession,
        force_geo_a_down: bool = False,
        force_geo_b_down: bool = False,
        force_side_effect_fail: bool = False
    ) -> PublicSubmissionResponse:
        """
        Executes the hardened 7-stage submission pipeline.
        """
        # -----------------------------------------------------------
        # Stage 1: Honeypot Anti-Bot Spam Detection
        # -----------------------------------------------------------
        if req.website_hp and req.website_hp.strip():
            logger.warning("Spam detected via filled honeypot field from IP: %s", client_ip)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Spam submission rejected: honeypot trap triggered"
            )

        # -----------------------------------------------------------
        # Stage 2: Abuse Protection & Rate Limiting
        # -----------------------------------------------------------
        allowed, retry_after, reason = rate_limiter.check_rate_limit(client_ip, req.widget_id)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=reason,
                headers={"Retry-After": str(retry_after)}
            )

        # -----------------------------------------------------------
        # Stage 3: Target Widget Lookup & Verification
        # -----------------------------------------------------------
        stmt = select(Widget).where(Widget.id == req.widget_id, Widget.is_active == True)
        result = await db.execute(stmt)
        widget = result.scalar_one_or_none()

        if not widget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Widget '{req.widget_id}' not found or is inactive"
            )

        # -----------------------------------------------------------
        # Stage 4: Form Field Boundary Validation
        # -----------------------------------------------------------
        declared_fields = json.loads(widget.fields_json or "[]")
        for f in declared_fields:
            fname = f.get("name")
            is_req = f.get("required", False)
            val = req.data.get(fname)

            if is_req and (val is None or str(val).strip() == ""):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: '{fname}'"
                )

            # Robust RFC-compliant email validation if field type is email
            if f.get("type") == "email" and val:
                import re
                val_str = str(val).strip()
                email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]{2,}$"
                if not re.match(email_regex, val_str) or val_str.endswith("."):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid email address provided for field: '{fname}'"
                    )

        # -----------------------------------------------------------
        # Stage 5: Idempotency Key Deduplication Check
        # -----------------------------------------------------------
        if idempotency_key:
            idem_stmt = select(Submission).where(
                Submission.widget_id == widget.id,
                Submission.idempotency_key == idempotency_key
            )
            idem_res = await db.execute(idem_stmt)
            existing = idem_res.scalar_one_or_none()
            if existing:
                logger.info("Idempotent replay detected for submission key %s", idempotency_key)
                return PublicSubmissionResponse(
                    success=True,
                    submission_id=existing.id,
                    status=existing.status,
                    message="Submission processed (idempotent replay)"
                )

        # -----------------------------------------------------------
        # Stage 6: Geolocation Enrichment (Fallback Chain)
        # -----------------------------------------------------------
        country, city, provider = await geo_enrichment_service.enrich_ip(
            ip=client_ip,
            force_a_down=force_geo_a_down,
            force_b_down=force_geo_b_down
        )

        # -----------------------------------------------------------
        # Stage 7: Persistence & Safe Async Side Effect
        # -----------------------------------------------------------
        ip_hashed = hash_ip(client_ip) if client_ip else None
        submission = Submission(
            widget_id=widget.id,
            tenant_id=widget.tenant_id,
            payload_json=json.dumps(req.data),
            ip_hash=ip_hashed,
            geo_country=country,
            geo_city=city,
            geo_provider=provider,
            idempotency_key=idempotency_key,
            status="accepted"
        )
        db.add(submission)
        await db.commit()
        await db.refresh(submission)

        # Fetch tenant email for notification
        tenant_stmt = select(Tenant).where(Tenant.id == widget.tenant_id)
        t_res = await db.execute(tenant_stmt)
        tenant = t_res.scalar_one_or_none()
        recipient_email = tenant.email if tenant else "admin@widgets.local"

        # Safe side effect: dispatched asynchronously with isolated error boundary
        # Never blocks or reverses the committed database row!
        await side_effect_worker.trigger_submission_notification(
            submission_id=submission.id,
            widget_id=widget.id,
            recipient_email=recipient_email,
            payload=req.data,
            force_fail=force_side_effect_fail
        )

        return PublicSubmissionResponse(
            success=True,
            submission_id=submission.id,
            status="accepted",
            message="Submission successfully captured and enriched"
        )


submission_service = SubmissionService()
