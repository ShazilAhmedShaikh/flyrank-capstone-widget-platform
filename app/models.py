"""
SQLAlchemy ORM models representing Tenants, Widgets, and Submissions.
Includes schema constraints, foreign keys, and indexes for multi-tenant query isolation.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index
)
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    """Generate a random UUID4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return current timestamp in UTC timezone."""
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    widgets = relationship("Widget", back_populates="tenant", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="tenant", cascade="all, delete-orphan")


class Widget(Base):
    __tablename__ = "widgets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    widget_type = Column(String(50), nullable=False, default="signup")  # signup, contact, cta
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    button_text = Column(String(50), nullable=False, default="Submit")
    fields_json = Column(Text, nullable=False, default="[]")  # JSON-encoded array of fields
    display_options_json = Column(Text, nullable=False, default="{}")  # JSON-encoded styles & triggers
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="widgets")
    submissions = relationship("Submission", back_populates="widget", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_widgets_tenant_active", "tenant_id", "is_active"),
    )


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    widget_id = Column(String(36), ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)  # Sanitized form payload
    ip_hash = Column(String(64), nullable=True, index=True)
    geo_country = Column(String(100), nullable=True)
    geo_city = Column(String(100), nullable=True)
    geo_provider = Column(String(50), nullable=True)  # provider_a, provider_b, none
    idempotency_key = Column(String(128), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="accepted")  # accepted, flagged_spam, processed
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    # Relationships
    widget = relationship("Widget", back_populates="submissions")
    tenant = relationship("Tenant", back_populates="submissions")

    __table_args__ = (
        Index("idx_submissions_tenant_created", "tenant_id", "created_at"),
        Index("idx_submissions_widget_created", "widget_id", "created_at"),
        Index("idx_submissions_widget_idempotency", "widget_id", "idempotency_key"),
    )
