"""
Database Seeding Script.
Populates demonstration tenants, widgets, and verified submissions.
Run with: python -m app.seed
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.database import AsyncSessionLocal, init_db
from app.models import Tenant, Widget, Submission
from app.security import hash_password, hash_ip


async def seed():
    print("[Seed] Initializing database schema...")
    await init_db()

    async with AsyncSessionLocal() as db:
        # Check if Tenant A already exists
        stmt = select(Tenant).where(Tenant.email == "tenant.a@example.com")
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            print("[Seed] Database already seeded. Skipping.")
            return

        print("[Seed] Creating demo tenants...")
        tenant_a = Tenant(
            id="tenant-alpha-001",
            email="tenant.a@example.com",
            hashed_password=hash_password("Password123!"),
            company_name="Alpha Innovations"
        )
        tenant_b = Tenant(
            id="tenant-beta-002",
            email="tenant.b@example.com",
            hashed_password=hash_password("Password123!"),
            company_name="Beta Ventures"
        )
        db.add_all([tenant_a, tenant_b])
        await db.commit()

        print("[Seed] Creating demo widgets...")
        widget_newsletter = Widget(
            id="widget-demo-newsletter",
            tenant_id=tenant_a.id,
            name="Newsletter Lead Form",
            widget_type="signup",
            title="Subscribe to Our Weekly Tech Brief",
            description="Get the latest engineering deep-dives straight to your inbox.",
            button_text="Join Newsletter",
            fields_json=json.dumps([
                {"name": "email", "label": "Work Email", "type": "email", "required": True, "placeholder": "alex@company.com"},
                {"name": "name", "label": "Full Name", "type": "text", "required": True, "placeholder": "Alex Mercer"}
            ]),
            display_options_json=json.dumps({
                "primary_color": "#2563eb",
                "position": "bottom-right"
            }),
            is_active=True
        )

        widget_contact = Widget(
            id="widget-demo-contact",
            tenant_id=tenant_a.id,
            name="Contact Sales Form",
            widget_type="contact",
            title="Talk to an Enterprise Specialist",
            description="Tell us about your team size and infrastructure needs.",
            button_text="Request Demo",
            fields_json=json.dumps([
                {"name": "email", "label": "Business Email", "type": "email", "required": True, "placeholder": "you@enterprise.com"},
                {"name": "company", "label": "Company Name", "type": "text", "required": True, "placeholder": "Acme Corp"},
                {"name": "message", "label": "Project Scope", "type": "textarea", "required": False, "placeholder": "Briefly describe your goals..."}
            ]),
            display_options_json=json.dumps({
                "primary_color": "#059669",
                "position": "bottom-right"
            }),
            is_active=True
        )

        widget_beta = Widget(
            id="widget-demo-beta",
            tenant_id=tenant_b.id,
            name="Beta Early Access",
            widget_type="popover",
            title="Join Beta Program",
            description="Beta test our new developer tools.",
            button_text="Request Invite",
            fields_json=json.dumps([
                {"name": "email", "label": "Email", "type": "email", "required": True, "placeholder": "dev@test.com"}
            ]),
            display_options_json=json.dumps({
                "primary_color": "#7c3aed",
                "position": "bottom-right"
            }),
            is_active=True
        )

        db.add_all([widget_newsletter, widget_contact, widget_beta])
        await db.commit()

        print("[Seed] Creating sample historical submissions...")
        now = datetime.now(timezone.utc)
        sample_submissions = [
            Submission(
                widget_id=widget_newsletter.id,
                tenant_id=tenant_a.id,
                payload_json=json.dumps({"email": "clara@techcorp.io", "name": "Clara Oswald"}),
                ip_hash=hash_ip("198.51.100.12"),
                geo_country="United States",
                geo_city="San Francisco",
                geo_provider="provider_a",
                status="accepted",
                created_at=now - timedelta(hours=2)
            ),
            Submission(
                widget_newsletter.id,
                tenant_a.id,
                json.dumps({"email": "johann@berlin-data.de", "name": "Johann Schmidt"}),
                hash_ip("203.0.113.45"),
                "Germany",
                "Berlin",
                "provider_a",
                None,
                "accepted",
                now - timedelta(hours=14)
            ),
            Submission(
                widget_contact.id,
                tenant_a.id,
                json.dumps({"email": "sarah@londonventures.co.uk", "company": "London Ventures", "message": "Evaluating 500 seat migration."}),
                hash_ip("198.51.100.88"),
                "United Kingdom",
                "London",
                "provider_b",
                None,
                "accepted",
                now - timedelta(days=2)
            )
        ]
        db.add_all(sample_submissions)
        await db.commit()

    print("[Seed] Database seed completed successfully!")
    print("\n--- Demo Credentials ---")
    print("Tenant A: tenant.a@example.com / Password123! (Widgets: widget-demo-newsletter, widget-demo-contact)")
    print("Tenant B: tenant.b@example.com / Password123! (Widgets: widget-demo-beta)")
    print("------------------------\n")


if __name__ == "__main__":
    asyncio.run(seed())
