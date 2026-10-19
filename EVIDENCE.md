# 📋 EVIDENCE.md — Requirements Verification & Proof of Work

**Project:** `flyrank-capstone-widget-platform`  
**Engineer:** Shazil Ahmed Shaikh  
**Evaluation Standard:** FlyRank Internship · Backend Track Capstone Brief (Section 6 & Section 13)  
**Test Suite Result:** 18 PASSED in 15.66s (`python -m pytest -v`)  

---

## 📑 Section 6: Requirements Verification Matrix

### 1. Widget Management

#### [x] Authenticated CRUD endpoints for widgets; requests without valid auth are rejected.
- **Proof:** `tests/test_auth_and_tenancy.py::test_auth_rejected_without_credentials` & `tests/test_auth_and_tenancy.py::test_widget_crud_workflow`
- **Transcript:**
```text
tests/test_auth_and_tenancy.py::test_auth_rejected_without_credentials PASSED [ 50%]
tests/test_auth_and_tenancy.py::test_widget_crud_workflow PASSED         [ 55%]

$ curl.exe -s -i http://127.0.0.1:8000/api/widgets
HTTP/1.1 401 Unauthorized
content-type: application/json
{"error": "Missing authentication credentials", "status_code": 401}
```

---

#### [x] Multi-tenant isolation proven: tenant A cannot read or modify tenant B's widgets or submissions.
- **Proof:** `tests/test_auth_and_tenancy.py::test_multi_tenant_isolation_proven`
- **Transcript:**
```text
tests/test_auth_and_tenancy.py::test_multi_tenant_isolation_proven PASSED [ 61%]

Verification:
- Tenant A creates widget W_A.
- Tenant B attempts GET /api/widgets/W_A -> HTTP 404 Not Found.
- Tenant B attempts PUT /api/widgets/W_A -> HTTP 404 Not Found.
- Tenant B attempts DELETE /api/widgets/W_A -> HTTP 404 Not Found.
- Tenant A receives lead submission -> Tenant B dashboard shows 0 submissions; Tenant A dashboard shows 1 submission.
```

---

#### [x] Embed snippet generated per widget.
- **Proof:** `tests/test_widget_delivery.py::test_embed_snippet_and_config_delivery`
- **Transcript:**
```json
// Response from POST /api/widgets
{
  "id": "widget-demo-newsletter",
  "name": "Newsletter Lead Form",
  "snippet": "<script src=\"http://localhost:8000/widget.js?id=widget-demo-newsletter\" async></script>"
}
```

---

### 2. Widget Delivery

#### [x] Public config endpoint serves a small payload with correct HTTP cache headers.
- **Proof:** `tests/test_widget_delivery.py::test_embed_snippet_and_config_delivery`
- **Transcript:**
```http
GET /widgets/widget-demo-newsletter/config HTTP/1.1
Host: 127.0.0.1:8000

HTTP/1.1 200 OK
cache-control: public, max-age=60
access-control-allow-origin: *
content-type: application/json
content-length: 567

{"id":"widget-demo-newsletter","widget_type":"signup","title":"Subscribe to Our Weekly Tech Brief","button_text":"Join Newsletter","fields":[{"name":"email","label":"Work Email","type":"email","required":true}],"submit_url":"http://localhost:8000/submissions"}
```

---

#### [x] Widget JavaScript is served as a versioned bundle (new version = new URL or cache-bust).
- **Proof:** `tests/test_widget_delivery.py::test_widget_loader_and_versioned_bundle_caching`
- **Transcript:**
```http
GET /static/widget.v1.js HTTP/1.1
Host: 127.0.0.1:8000

HTTP/1.1 200 OK
cache-control: public, max-age=31536000, immutable
access-control-allow-origin: *
content-type: application/javascript
content-length: 8352
```

---

#### [x] The widget renders on a page served from a different origin than your API.
- **Proof:** `tests/test_acceptance_probes.py::test_probe_1_second_origin_submission` & Customer Test Site at `customer_site/index.html` (hosted on `http://localhost:5500`, API on `http://localhost:8000`).
- **Transcript:**
```text
tests/test_acceptance_probes.py::test_probe_1_second_origin_submission PASSED [ 16%]

Origin: http://localhost:5500
Referer: http://localhost:5500/index.html
Result: Widget successfully fetches config and renders DOM on separate origin.
```

---

### 3. Public Submission API

#### [x] Cross-origin submissions work: CORS headers correct, preflight (OPTIONS) handled.
- **Proof:** `tests/test_submissions_and_boundaries.py::test_cors_preflight_and_submission`
- **Transcript:**
```http
OPTIONS /submissions HTTP/1.1
Origin: http://localhost:5500
Access-Control-Request-Method: POST

HTTP/1.1 200 OK
access-control-allow-origin: *
access-control-allow-methods: GET, POST, PUT, DELETE, OPTIONS, HEAD
access-control-max-age: 600
```

---

#### [x] All incoming input validated; malformed and oversized payloads rejected with appropriate 4xx codes and JSON errors.
- **Proof:** `tests/test_submissions_and_boundaries.py::test_boundary_validation_malformed_and_oversized`
- **Transcript:**
```text
1. Malformed JSON Body:
HTTP/1.1 400 Bad Request
{"error": "Malformed JSON payload received", "status_code": 400}

2. Oversized Payload (>64 KB):
HTTP/1.1 413 Content Too Large
{"error": "Payload exceeds maximum allowable size of 65536 bytes", "status_code": 413}

3. Missing Required Form Field:
HTTP/1.1 400 Bad Request
{"error": "Missing required field: 'email'", "status_code": 400}

4. Invalid Email Format:
HTTP/1.1 400 Bad Request
{"error": "Invalid email address provided for field: 'email'", "status_code": 400}
```

---

#### [x] Valid submissions stored safely, linked to the right widget and tenant.
- **Proof:** `tests/test_acceptance_probes.py::test_probe_1_second_origin_submission`
- **Transcript:**
```http
POST /submissions HTTP/1.1
Origin: http://localhost:5500
Content-Type: application/json

{"widget_id": "widget-demo-newsletter", "data": {"email": "alex@mercer.io", "name": "Alex Mercer"}, "website_hp": ""}

HTTP/1.1 201 Created
access-control-allow-origin: *
{"success": true, "submission_id": "571a9fd3-ac61-49ee-93a7-f72a8414c25f", "status": "accepted", "message": "Submission successfully captured and enriched"}
```

---

### 4. Abuse Protection

#### [x] Rate limiting per IP and/or per widget returns 429 under a burst — and the API keeps serving legitimate traffic.
- **Proof:** `tests/test_abuse_and_spam.py::test_rate_limiting_burst_and_recovery_probe3` & `tests/test_acceptance_probes.py::test_probe_3_rate_limiting_burst`
- **Transcript:**
```text
Burst Submissions 1 to 5 from IP 192.168.1.100 -> HTTP 201 Created
Burst Submission 6 from IP 192.168.1.100       -> HTTP 429 Too Many Requests
Header: Retry-After: 10
Response: {"error": "Rate limit exceeded for IP. Please wait 10 seconds.", "status_code": 429}

Legitimate submission immediately after from IP 192.168.1.200 -> HTTP 201 Created (Unblocked!)
```

---

#### [x] At least one spam-prevention technique (honeypot field, token, or heuristic) demonstrably blocks a spam submission.
- **Proof:** `tests/test_abuse_and_spam.py::test_honeypot_spam_prevention_probe6` & `tests/test_acceptance_probes.py::test_probe_6_honeypot_bot_defense`
- **Transcript:**
```http
POST /submissions HTTP/1.1
Content-Type: application/json

{"widget_id": "widget-demo-newsletter", "data": {"email": "bot@spammer.org"}, "website_hp": "automated bot content"}

HTTP/1.1 400 Bad Request
access-control-allow-origin: *
{"error": "Spam submission rejected: honeypot trap triggered", "status_code": 400}
```

---

### 5. Enrichment & Safe Side Effects

#### [x] IP->geo enrichment uses a provider fallback chain: provider A down -> provider B answers -> submission enriched.
- **Proof:** `tests/test_geo_and_side_effects.py::test_geo_fallback_chain_probe4` & `tests/test_acceptance_probes.py::test_probe_4_geo_provider_fallback_chain`
- **Transcript:**
```http
POST /submissions HTTP/1.1
X-Simulate-Geo-A: down
Content-Type: application/json

{"widget_id": "widget-demo-newsletter", "data": {"email": "fallback.b@test.com"}}

HTTP/1.1 201 Created
{"success": true, "submission_id": "392b01d5-4e2b-4b01-bfc8-de7bf54dc904", "status": "accepted"}

Dashboard Record Inspection:
- id: "392b01d5-4e2b-4b01-bfc8-de7bf54dc904"
- geo_provider: "provider_b"
- geo_country: "United States"
- geo_city: "Local City"
```

---

#### [x] All providers down -> submission still succeeds (without geo). Degrade, never fail.
- **Proof:** `tests/test_geo_and_side_effects.py::test_geo_fallback_chain_probe4`
- **Transcript:**
```http
POST /submissions HTTP/1.1
X-Simulate-Geo-A: down
X-Simulate-Geo-B: down
Content-Type: application/json

{"widget_id": "widget-demo-newsletter", "data": {"email": "bothdown@test.com"}}

HTTP/1.1 201 Created
{"success": true, "submission_id": "c88bc016-ddd3-4c44-acc6-d85621dcf292", "status": "accepted"}

Dashboard Record Inspection:
- id: "c88bc016-ddd3-4c44-acc6-d85621dcf292"
- geo_provider: "none"
- geo_country: null
- geo_city: null
- status: "accepted"
```

---

#### [x] A failing confirmation email / webhook does not prevent the submission from being stored.
- **Proof:** `tests/test_geo_and_side_effects.py::test_safe_side_effects_isolation_probe5` & `tests/test_acceptance_probes.py::test_probe_5_side_effect_failure_isolation`
- **Transcript:**
```http
POST /submissions HTTP/1.1
X-Simulate-Side-Effect-Fail: true
Content-Type: application/json

{"widget_id": "widget-demo-newsletter", "data": {"email": "broken.notifier@test.com"}}

HTTP/1.1 201 Created
{"success": true, "submission_id": "fbd2ace4-8fd8-4472-a1e3-606655acb7b5", "status": "accepted"}

Server Log:
[SIDE_EFFECT_RETRY] Attempt 1/2 failed for submission fbd2ace4...: Simulated notification failure
[SIDE_EFFECT_RETRY] Attempt 2/2 failed for submission fbd2ace4...: Simulated notification failure
[SIDE_EFFECT_FAILURE_ALERT] All 2 notification attempts failed for submission fbd2ace4... Lead is safely stored in database.
```

---

### 6. Documentation & Submission Pack

#### [x] README with architecture diagram, setup instructions, and API documentation; the required files from Section 11 present.
- **Proof:** Verified present files:
  - `README.md`
  - `capstone.yaml`
  - `EVIDENCE.md`
  - `BUILDLOG.md`
  - `.env.example`
  - `.gitignore`
  - `LICENSE`
  - `DESIGN.md`

---

## 🎯 Acceptance Probes Summary Table (Section 13 Layer 2)

| Probe | Test Case | Behavioral Promise | Verified Result |
| :--- | :--- | :--- | :--- |
| **PROBE 1** | `test_probe_1_second_origin_submission` | POST submission from 2nd origin (`http://localhost:5500`) -> 2xx, stored, visible in dashboard | **PASS** (HTTP 201, stored & listed in `/api/dashboard/submissions`) |
| **PROBE 2** | `test_probe_2_malformed_and_oversized_payloads` | Send malformed & oversized payload -> clean 4xx JSON errors, NEVER 500 | **PASS** (Malformed: 400 Bad Request, Oversized: 413 Content Too Large) |
| **PROBE 3** | `test_probe_3_rate_limiting_burst` | Fire burst of rapid submissions -> 429s appear, normal request right after succeeds | **PASS** (1-5: 201, 6+: 429 with `Retry-After: 10`, unthrottled IP: 201) |
| **PROBE 4** | `test_probe_4_geo_provider_fallback_chain` | Disable Provider A -> Provider B enriches; Disable both -> stored without geo | **PASS** (Degrades gracefully: Provider B used when A down; `geo_country=None` when both down) |
| **PROBE 5** | `test_probe_5_side_effect_failure_isolation` | Force email/webhook side effect to throw -> submission still returns 201 and is stored | **PASS** (Exception caught & alerted off-thread; database transaction commits HTTP 201) |
| **PROBE 6** | `test_probe_6_honeypot_bot_defense` | Fill honeypot field like a bot -> submission is rejected or dropped | **PASS** (HTTP 400 Bad Request: "honeypot trap triggered") |
