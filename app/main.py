"""
Main Application Entry Point.
Configures FastAPI application, CORS middleware, global exception handlers,
lifespan startup events, and route registrations.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn

from app.config import settings
from app.database import init_db
from app.routers import (
    auth,
    widgets,
    public_delivery,
    submissions,
    dashboard
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize database tables on startup."""
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Embeddable Widget & Lead-Capture Platform API",
    lifespan=lifespan
)

# ------------------------------------------------------------------------------
# CORS Middleware
# ------------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "Cache-Control"]
)


# ------------------------------------------------------------------------------
# Global Exception Handlers (Clean 4xx JSON errors, NEVER leak 500s on bad input)
# ------------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    headers = getattr(exc, "headers", None) or {}
    headers["Access-Control-Allow-Origin"] = "*"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
        headers=headers
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Transform schema validation errors into clean 4xx responses."""
    details = []
    for err in exc.errors():
        loc = " -> ".join([str(x) for x in err.get("loc", [])])
        msg = err.get("msg", "Invalid value")
        details.append(f"{loc}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation failed",
            "details": details,
            "status_code": 422
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )


# ------------------------------------------------------------------------------
# Routers Registration
# ------------------------------------------------------------------------------
app.include_router(public_delivery.router)
app.include_router(submissions.router)
app.include_router(auth.router)
app.include_router(widgets.router)
app.include_router(dashboard.router)


STATIC_DIR = Path(__file__).resolve().parent / "static"
CUSTOMER_SITE_DIR = Path(__file__).resolve().parent.parent / "customer_site"


@app.get("/", tags=["Frontend"])
@app.get("/dashboard", tags=["Frontend"])
async def serve_dashboard():
    """Serve the interactive SaaS owner dashboard frontend."""
    dashboard_path = STATIC_DIR / "dashboard.html"
    return FileResponse(dashboard_path)


@app.get("/demo", tags=["Demo"])
@app.get("/customer-site", tags=["Demo"])
async def serve_customer_demo():
    """Serve the customer demo website directly on port 8000."""
    customer_path = CUSTOMER_SITE_DIR / "index.html"
    return FileResponse(customer_path)


@app.get("/health", tags=["Health"])
async def health_check():
    """Service health verification endpoint."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
