# 🚀 Embeddable Widget & Lead-Capture Platform

> **FlyRank Internship · Backend Track Capstone**  
> A hardened, multi-tenant backend platform allowing customers to embed lead-capture widgets on any website with a single `<script>` line, safely ingesting, validating, spam-filtering, geo-enriching, and storing public submissions.

---

## 📌 Architecture Overview

```
Widget Owner (authenticated)
  → /api/widgets (Tenant-Isolated CRUD) 
  → /api/dashboard (Stats & Aggregations)
  → Embed snippet generated

Customer Website (Any Origin, e.g. http://localhost:5500)
  <script src="http://localhost:8000/widget.js?id=w_123"></script>
  → GET /widgets/:id/config (Public, Cached, CORS)
  → Render Isolated Widget Form

Website Visitor
  → POST /submissions (Public, Cross-Origin CORS)
      │
      ├── 1. Boundary Validation (Malformed/Oversized → 4xx, never 500)
      ├── 2. Abuse Protection (Sliding window rate limit → 429)
      ├── 3. Bot Defense (Honeypot trap → dropped/rejected)
      ├── 4. Geo Enrichment Chain (Provider A → Provider B → store anyway)
      ├── 5. Atomic Storage (Linked to Widget & Tenant)
      └── 6. Safe Async Side Effects (Email/Webhook failure never blocks 201)
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.12+
- `pip`

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/shazilahmed/flyrank-capstone-widget-platform.git
cd flyrank-capstone-widget-platform

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
copy .env.example .env
```

### 3. Seed Demo Data
```bash
python -m app.seed
```
This populates sample tenants, widgets, and verified submissions for testing.

### 4. Run the API Server
```bash
python -m app.main
```
The server starts at `http://localhost:8000`. Swagger API docs are available at `http://localhost:8000/docs`.

### 5. Run the Customer Test Site (Second Origin)
```bash
# In a separate terminal, serve the demo page on port 5500:
python -m http.server 5500 --directory customer_site
```
Open `http://localhost:5500` in your browser to interact with the embeddable widget running against your backend!

### 6. Run the Test Suite
```bash
pytest -v
```

---

## ⚠️ Limitations & Trade-Offs

- **Database:** Defaults to SQLite with WAL mode (`aiosqlite`) for zero-cost, zero-dependency portability without requiring Docker. Production deployments can switch to PostgreSQL via `DATABASE_URL`.
- **Side Effects:** Notifications (emails/webhooks) are queued via asynchronous background tasks with console output logging.
- **Rate Limiter:** Built using an in-memory sliding window algorithm. For distributed multi-instance clustering, Redis can be dropped in behind the same interface.
