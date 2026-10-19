# 📐 Phase 1 Design Document: Embeddable Widget & Lead-Capture Platform

**Project:** `flyrank-capstone-widget-platform`  
**Author:** Shazil Ahmed Shaikh  
**Track:** FlyRank Internship · Backend Track Capstone  
**Target Architecture:** Python 3.12 · FastAPI · SQLite/SQLAlchemy · Uvicorn  

---

## 1. Problem Statement
Businesses need an ultra-simple mechanism to embed interactive lead capture widgets (contact forms, newsletter signups, CTA popovers) into any third-party website via a single line of `<script>` tag. The backend must ingest cross-origin submissions from untrusted browsers across the public internet, validate inputs strictly, throttle abusive traffic, defeat bot spam, enrich lead IP addresses with geographic data through a resilient fallback chain, and guarantee that non-critical side effects (like email/webhook alerts) never fail the customer transaction.

---

## 2. Core Architecture & Layer Sketch

The application strictly separates HTTP routing, domain business logic, and database persistence into decoupled layers:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL WORLD / CLIENTS                        │
└──────────────────┬─────────────────┬─────────────────┬─────────────────┘
                   │                 │                 │
  [Admin UI/Owner] │  [Browser Tag]  │ [Public Visitor]│
                   ▼                 ▼                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        HTTP & CONTROLLER LAYER                         │
│  - /api/auth/* (JWT Login, Registration)                               │
│  - /api/widgets/* (Tenant-isolated Admin CRUD)                         │
│  - /widget.js & /static/widget.v1.js (Cached JavaScript Bundle)        │
│  - /widgets/{id}/config (Cached, CORS Public Configuration)            │
│  - /submissions (Public CORS Submission Ingestion, Options Preflight)  │
│  - /api/dashboard/* (Metrics, Submission Aggregations)                 │
└──────────────────┬─────────────────┬─────────────────┬─────────────────┘
                   │                 │                 │
┌──────────────────▼─────────────────▼─────────────────▼─────────────────┐
│                      DOMAIN & SERVICE LAYER                            │
│  - Security & RateLimiter (In-memory token bucket/sliding window)      │
│  - SpamGuard (Honeypot detector & payload boundary sanitization)       │
│  - GeoEnrichmentService (Provider A [ip-api] -> Provider B [ipapi.co]) │
│  - SafeSideEffectWorker (Async background tasks with retry + alerts)   │
│  - TenantBoundaryService (Row-level multi-tenant security verification)│
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│                    DATA ACCESS & PERSISTENCE LAYER                     │
│  - SQLAlchemy async engine with SQLite WAL mode                        │
│  - Schema definitions: tenants, widgets, submissions, audit_logs       │
│  - Explicit indexing on (tenant_id), (widget_id, created_at)           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Models & Database Schema

### A. `tenants` Table
| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | VARCHAR(36) | Primary Key (UUIDv4) |
| `email` | VARCHAR(255) | Unique, Index, Not Null |
| `hashed_password` | VARCHAR(255) | Not Null |
| `company_name` | VARCHAR(255) | Nullable |
| `created_at` | TIMESTAMP | Default UTC now, Not Null |

### B. `widgets` Table
| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | VARCHAR(36) | Primary Key (UUIDv4) |
| `tenant_id` | VARCHAR(36) | Foreign Key -> `tenants.id`, Index, Not Null |
| `name` | VARCHAR(100) | Not Null |
| `widget_type` | VARCHAR(50) | 'signup', 'contact', 'cta' |
| `title` | VARCHAR(200) | Not Null |
| `description` | TEXT | Nullable |
| `button_text` | VARCHAR(50) | Default 'Submit' |
| `fields_json` | TEXT (JSON) | Form definition array (`[{"name": "email", "type": "email", "required": true}]`) |
| `display_options_json` | TEXT (JSON) | Theme color, position, trigger rules |
| `is_active` | BOOLEAN | Default True, Index |
| `created_at` | TIMESTAMP | Default UTC now, Index |
| `updated_at` | TIMESTAMP | Default UTC now, OnUpdate UTC now |

**Indexes:** `idx_widgets_tenant_id` ON (`tenant_id`), `idx_widgets_tenant_active` ON (`tenant_id`, `is_active`).

### C. `submissions` Table
| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | VARCHAR(36) | Primary Key (UUIDv4) |
| `widget_id` | VARCHAR(36) | Foreign Key -> `widgets.id`, Index, Not Null |
| `tenant_id` | VARCHAR(36) | Foreign Key -> `tenants.id`, Index, Not Null |
| `payload_json` | TEXT (JSON) | Clean user-submitted field values |
| `ip_hash` | VARCHAR(64) | SHA-256 hashed visitor IP (privacy compliance) |
| `geo_country` | VARCHAR(100) | Enriched country name (Nullable) |
| `geo_city` | VARCHAR(100) | Enriched city name (Nullable) |
| `geo_provider` | VARCHAR(50) | 'provider_a', 'provider_b', 'none' |
| `idempotency_key` | VARCHAR(128) | Optional header key for retry deduplication, Index |
| `status` | VARCHAR(30) | 'accepted', 'flagged_spam', 'processed' |
| `created_at` | TIMESTAMP | Default UTC now, Index |

**Indexes:** `idx_submissions_tenant_created` ON (`tenant_id`, `created_at`), `idx_submissions_widget_created` ON (`widget_id`, `created_at`), `idx_submissions_idempotency` ON (`widget_id`, `idempotency_key`).

---

## 4. The Embed Lifecycle Flow

1. **Snippet Generation:** The admin requests widget snippet. The API returns:
   `<script src="http://localhost:8000/widget.js?id=WIDGET_ID" async></script>`
2. **Script Load & Cache:** The browser executes `widget.js`. The response carries `Cache-Control: public, max-age=31536000, immutable` (for versioned bundle `widget.v1.js`).
3. **Config Retrieval:** The script performs an async fetch to `GET /widgets/{id}/config`. The server returns JSON with `Cache-Control: public, max-age=60` and `Access-Control-Allow-Origin: *`.
4. **DOM Rendering:** The script builds the isolated form DOM inside a scoped container (or Shadow DOM) to avoid CSS collisions. A hidden honeypot field (`website_hp`) is automatically injected into the form.
5. **Visitor Submit:**
   - Visitor fills form and clicks submit.
   - Script performs `POST /submissions` with `Content-Type: application/json`.
   - Preflight `OPTIONS /submissions` is handled automatically with CORS headers.
   - Server runs Pipeline:
     1. Size & syntax check (rejects payloads > 64KB with 413/400).
     2. Rate limit check (rejects excess bursts with 429).
     3. Honeypot check (silently drops or rejects with 400).
     4. Data validation against widget's required schema.
     5. Geolocation enrichment fallback (Provider A -> Provider B -> degrade gracefully).
     6. Persist to DB.
     7. Trigger safe async background notification (email/webhook); failure caught and logged without affecting the 201 response.
   - Returns `{ "success": true, "submission_id": "..." }` (201 Created).

---

## 5. API Contracts for the Three Request Paths

### Path 1: Widget Owner Management API (Authenticated, Tenant-Isolated)
- `POST /api/auth/register` -> `{ email, password, company_name }` -> `201 Created`
- `POST /api/auth/login` -> `{ email, password }` -> `{ access_token, token_type }` -> `200 OK`
- `GET /api/widgets` -> List all widgets for authenticated tenant -> `200 OK`
- `POST /api/widgets` -> Create new widget -> `201 Created`
- `GET /api/widgets/{id}` -> Fetch widget details + generated snippet -> `200 OK` (404/403 for other tenants)
- `PUT /api/widgets/{id}` -> Update widget configuration -> `200 OK`
- `DELETE /api/widgets/{id}` -> Delete widget -> `204 No Content`
- `GET /api/dashboard/stats` -> Counts over time, submissions per widget, geo breakdown -> `200 OK`
- `GET /api/dashboard/submissions` -> Paginated submissions list for tenant's widgets -> `200 OK`

### Path 2: Public Widget Delivery (Public, Cached, CORS)
- `GET /widget.js?id={id}` -> Lightweight loader script (`Cache-Control: public, max-age=3600`)
- `GET /static/widget.v1.js` -> Minified/complete widget bundle (`Cache-Control: public, max-age=31536000, immutable`)
- `GET /widgets/{id}/config` -> Returns public JSON configuration (`Cache-Control: public, max-age=60`, `Access-Control-Allow-Origin: *`)

### Path 3: Public Submission Endpoint (Public, CORS, Hardened)
- `OPTIONS /submissions` -> Preflight response with `204 No Content` / `200 OK`, CORS headers
- `POST /submissions` -> Ingest form data
  - Request Headers: `Content-Type: application/json`, Optional `Idempotency-Key`
  - Body: `{ "widget_id": "...", "data": { "email": "...", "name": "..." }, "website_hp": "" }`
  - Responses:
    - `201 Created`: `{ "success": true, "submission_id": "...", "status": "accepted" }`
    - `400 Bad Request`: `{ "error": "Validation failed", "details": [...] }`
    - `413 Payload Too Large`: `{ "error": "Payload exceeds 64KB limit" }`
    - `429 Too Many Requests`: `{ "error": "Rate limit exceeded. Try again in X seconds." }`

---

## 6. Explicit Non-Goal (Requirement Check)

**Non-Goal:** This system is NOT a full drag-and-drop WYSIWYG form builder SaaS. It will not provide a visual canvas builder for arbitrary nested CSS styling or hundreds of field plugins. Its explicit responsibility is backend resilience: rock-solid public API ingestion, cross-origin security, tenant data isolation, multi-provider degradation, and abuse resistance.
