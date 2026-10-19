"""
Authentication Router.
Handles tenant registration and login with JWT token issuance.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Tenant
from app.schemas import TenantRegister, TenantLogin, TenantResponse, TokenResponse
from app.security import hash_password, verify_password, create_access_token, get_current_tenant
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def register_tenant(req: TenantRegister, db: AsyncSession = Depends(get_db)):
    """Register a new tenant account."""
    stmt = select(Tenant).where(Tenant.email == req.email)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A tenant with this email address already exists"
        )

    tenant = Tenant(
        email=req.email,
        hashed_password=hash_password(req.password),
        company_name=req.company_name
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.post("/login", response_model=TokenResponse)
async def login_tenant(req: TenantLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate tenant and return JWT bearer token."""
    stmt = select(Tenant).where(Tenant.email == req.email)
    res = await db.execute(stmt)
    tenant = res.scalar_one_or_none()

    if not tenant or not verify_password(req.password, tenant.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token(data={"sub": tenant.id, "email": tenant.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get("/me", response_model=TenantResponse)
async def get_current_user_profile(current_tenant: Tenant = Depends(get_current_tenant)):
    """Retrieve the currently authenticated tenant profile."""
    return current_tenant
