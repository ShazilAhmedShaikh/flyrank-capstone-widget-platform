# 🛠️ BUILDLOG.md — AI-Usage and Implementation Log

**Project:** `flyrank-capstone-widget-platform`  
**Engineer:** Shazil Ahmed Shaikh  
**Pair:** AI Assistant (Antigravity Co-Developer)  
**Standard:** Honesty is graded, perfection is not.

---

## 1. Setup & Design Phase (Phase 1)
- **Where AI helped:**
  - Helped scaffold the project architecture according to the FlyRank Capstone specification.
  - Sketched the layered architecture diagram, DB models, and API surface contracts in `DESIGN.md`.
  - Configured git ignore rules, manifest `capstone.yaml`, and environment variable templates (`.env.example`).
- **Where AI was wrong / Course Corrections:**
  - AI initially suggested using raw FastAPI background tasks without exception shielding for side effects. We corrected this by introducing a dedicated safe execution worker (`SafeSideEffectWorker`) with retry semantics, delay intervals, and graceful failure isolation so that side-effect failures never impact the user submission response.
  - AI assumed standard FastAPI 422 default error formatting for missing parameters; we introduced custom exception handlers in `app/main.py` to produce clean, unified 4xx JSON errors (`{"error": "Validation failed", "details": [...]}`) matching the capstone contract requirement that malformed requests never return unhandled responses or standard traceback leaks.
- **What was changed / Decided:**
  - Selected SQLite with `aiosqlite` and WAL mode for zero external dependency execution ($0 stack, zero credit card, docker-free local portability).
  - Designed mock fallback toggles (`SIMULATE_GEO_PROVIDER_A_DOWN`, `SIMULATE_GEO_PROVIDER_B_DOWN`, `SIMULATE_SIDE_EFFECT_FAILURE`) and HTTP headers (`X-Simulate-Geo-A`, `X-Simulate-Geo-B`, `X-Simulate-Side-Effect-Fail`) to make acceptance probe verification completely deterministic and automated.

---

## 2. Hardened Submission Path (Phase 2)
- **Where AI helped:**
  - Implemented boundary validation for incoming payloads, rejecting malformed JSON (400) and oversized bodies exceeding 64KB (413).
  - Implemented the in-memory sliding window rate limiter (`SlidingWindowRateLimiter`) with timestamp deques to protect against bursts (HTTP 429 + `Retry-After` header).
  - Wired honeypot anti-bot defense (`website_hp`) directly into the submission pipeline, trapping automated spam bots.
  - Implemented the geolocation enrichment fallback chain: Provider A (`ip-api.com`) -> Provider B (`ipapi.co`) -> graceful degradation without error.
- **Where AI was wrong / Course Corrections:**
  - In `app/services/geo_enrichment.py`, the initial implementation attempted live outbound network requests for arbitrary test IPs such as `192.168.1.100` and `10.0.0.99`. This introduced 2.5-second socket timeouts during rate-limit burst tests, which caused timestamps to artificially exceed the 10-second burst window. We resolved this by integrating Python's native `ipaddress` module to detect RFC 1918 private and loopback addresses, immediately providing deterministic mock geo responses without network latency.
  - In `app/routers/submissions.py`, Starlette's deprecated `HTTP_413_REQUEST_ENTITY_TOO_LARGE` was initially referenced. We upgraded to `HTTP_413_CONTENT_TOO_LARGE`.
  - In `app/seed.py`, `Submission` declarative model instantiation initially used positional arguments. We refactored all instances to explicit keyword arguments.

---

## 3. Delivery, Dashboard & Proof (Phase 3)
- **Where AI helped:**
  - Authored the embeddable JavaScript bundle (`app/static/widget.v1.js`) and loader (`/widget.js`) with responsive card styling, shadow DOM boundary immunity, and dynamic config binding.
  - Implemented HTTP caching headers: `Cache-Control: public, max-age=31536000, immutable` for versioned bundle, `max-age=60` for widget configuration.
  - Created the second-origin test website (`customer_site/index.html`) demonstrating real cross-origin form embedding from `http://localhost:5500`.
  - Implemented owner dashboard aggregation endpoints (`/api/dashboard/stats` and `/api/dashboard/submissions`) with strict tenant isolation.
  - Formulated a comprehensive pytest suite (`18/18 tests passing`) verifying all 6 acceptance probes and generating evidence transcripts for `EVIDENCE.md`.
