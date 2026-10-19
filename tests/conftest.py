"""
Pytest Fixtures and Test Harness.
Configures an isolated SQLite test database and an asynchronous HTTP test client.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.database import Base, get_db
from app.services.rate_limiter import rate_limiter

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_widget_platform.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Create fresh tables for every test session and reset rate limiter."""
    rate_limiter.reset()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async HTTP client bound to the FastAPI ASGI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    """Register and authenticate Tenant A, returning authorization headers."""
    reg_resp = await client.post("/api/auth/register", json={
        "email": "tenant.a@test.com",
        "password": "Password123!",
        "company_name": "Tenant Alpha Inc"
    })
    assert reg_resp.status_code == 201

    login_resp = await client.post("/api/auth/login", json={
        "email": "tenant.a@test.com",
        "password": "Password123!"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def tenant_b_auth_headers(client: AsyncClient):
    """Register and authenticate Tenant B, returning authorization headers."""
    reg_resp = await client.post("/api/auth/register", json={
        "email": "tenant.b@test.com",
        "password": "Password123!",
        "company_name": "Tenant Beta LLC"
    })
    assert reg_resp.status_code == 201

    login_resp = await client.post("/api/auth/login", json={
        "email": "tenant.b@test.com",
        "password": "Password123!"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
