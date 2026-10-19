# 🛠️ BUILDLOG.md — AI-Usage and Implementation Log

**Project:** `flyrank-capstone-widget-platform`  
**Engineer:** Shazil Ahmed Shaikh  
**Pair:** AI Assistant (Antigravity Co-Developer)  

---

## 1. Setup & Design Phase (Phase 1)
- **Where AI helped:**
  - Helped scaffold the project architecture according to the FlyRank Capstone specification.
  - Sketched the layered architecture diagram, DB models, and API surface contracts in `DESIGN.md`.
  - Configured git ignore rules, manifest `capstone.yaml`, and environment variable templates.
- **Where AI was wrong / Course Corrections:**
  - AI initially suggested using raw FastAPI background tasks without exception shielding for side effects. We corrected this by introducing a dedicated safe execution wrapper with retry semantics and graceful degradation so that side-effect failures never impact the user submission response.
  - AI assumed standard FastAPI 422 default error formatting for missing parameters; we introduced a custom exception handler to produce clean, unified 4xx JSON errors (`{"error": "Validation failed", "details": [...]}`) matching the capstone contract requirement that malformed requests never return unhandled responses or standard traceback leaks.
- **What was changed / Decided:**
  - Selected SQLite with `aiosqlite` and WAL mode for zero external dependency execution ($0 stack, zero credit card, docker-free local portability).
  - Designed mock fallback toggles (`SIMULATE_GEO_PROVIDER_A_DOWN`, `SIMULATE_GEO_PROVIDER_B_DOWN`, `SIMULATE_SIDE_EFFECT_FAILURE`) to make acceptance probe verification completely deterministic and automated.

---

## 2. Hardened Submission Path (Phase 2)
*(To be updated during Phase 2 implementation)*

---

## 3. Delivery, Dashboard & Proof (Phase 3)
*(To be updated during Phase 3 implementation)*
