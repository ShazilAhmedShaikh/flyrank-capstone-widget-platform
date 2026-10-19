"""
Public Submission Router.
Hardened submission endpoint accepting cross-origin requests from external websites.
Implements preflight OPTIONS handling, boundary size limits, abuse protection,
geo enrichment fallback, and resilient side-effect isolation.
"""

from typing import Optional
from fastapi import APIRouter, Request, Response, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import settings
from app.schemas import PublicSubmissionRequest, PublicSubmissionResponse
from app.services.submission_service import submission_service

router = APIRouter(tags=["Public Submissions"])


@router.options("/submissions")
async def options_submissions():
    """
    Handle CORS preflight requests for the public submission endpoint.
    Explicitly responds with accepted headers, methods, and origin allowance.
    """
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Idempotency-Key, X-Simulate-Geo-A, X-Simulate-Geo-B, X-Simulate-Side-Effect-Fail",
            "Access-Control-Max-Age": "86400"
        }
    )


@router.post("/submissions", response_model=PublicSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_simulate_geo_a: Optional[str] = Header(None, alias="X-Simulate-Geo-A"),
    x_simulate_geo_b: Optional[str] = Header(None, alias="X-Simulate-Geo-B"),
    x_simulate_side_effect_fail: Optional[str] = Header(None, alias="X-Simulate-Side-Effect-Fail")
):
    """
    Public ingestion endpoint for external web forms.
    Enforces payload size constraints, rate limiting, anti-bot honeypot check,
    geo enrichment fallback chain, and safe side effects.
    """
    # 1. CORS headers on response
    response.headers["Access-Control-Allow-Origin"] = "*"

    # 2. Check content length boundary
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.MAX_PAYLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Payload exceeds maximum allowable size of {settings.MAX_PAYLOAD_SIZE_BYTES} bytes"
        )

    # Read raw body to guard against unannounced oversized chunked streaming
    raw_body = await request.body()
    if len(raw_body) > settings.MAX_PAYLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Payload exceeds maximum allowable size of {settings.MAX_PAYLOAD_SIZE_BYTES} bytes"
        )

    # 3. Parse JSON safely (malformed JSON -> 400 Bad Request, never 500)
    try:
        body_dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload received"
        )

    try:
        sub_req = PublicSubmissionRequest(**body_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema validation error: {str(exc)}"
        )

    # 4. Resolve client IP (respecting forward proxies if present)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    # 5. Process through the hardened submission pipeline
    force_a_down = (x_simulate_geo_a == "down")
    force_b_down = (x_simulate_geo_b == "down")
    force_side_fail = (x_simulate_side_effect_fail == "true")

    result = await submission_service.process_submission(
        req=sub_req,
        client_ip=client_ip,
        idempotency_key=idempotency_key,
        db=db,
        force_geo_a_down=force_a_down,
        force_geo_b_down=force_b_down,
        force_side_effect_fail=force_side_fail
    )

    return result
