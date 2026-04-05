# Buddha Korea Admin Panel - Comprehensive Test Plan

> **Date:** April 5, 2026
> **Scope:** End-to-end MVP Admin Console (`/admin/` UI and `/api/admin/*` backend)
> **Reference:** `docs/ADMIN_PANEL.md`, `docs/PLAN_PLAYWRIGHT_TESTING.md`

## 1. Methodology & Global Standards

This test plan follows the **Test Automation Pyramid** methodology, integrating with the established Playwright E2E strategy and the FastAPI/Pytest backend ecosystem. 

**Core Principles:**
1. **Shift-Left Security:** Role-Based Access Control (RBAC) and authentication must be tested at the API integration level.
2. **Behavior-Driven E2E:** UI tests should focus on operator workflows (e.g., investigating costs, banning users).
3. **Auditability Validation:** State changes must strictly verify the side-effect of audit log creation.
4. **PII Compliance:** Assure no raw PII leaks into the admin responses.

---

## 2. Test Pyramid Breakdown

### 2.1. Unit Tests (Backend - `pytest`)
**Objective:** Validate core logic and models in isolation.
**Target Files:** `tests/test_admin_models.py`, `tests/test_dependencies.py`

*   **Model (`admin_audit_log.py`):**
    *   Verify model instantiation with required fields (`admin_user_id`, `action`, `target_type`, `target_id`).
    *   Verify `before_state` and `after_state` JSONB constraints.
*   **Dependencies (`dependencies.py`):**
    *   `verify_admin_role`: 
        *   Mock valid admin user -> returns user.
        *   Mock valid user with no admin role -> raises `403 Forbidden`.
        *   Mock unauthenticated request -> raises `401 Unauthorized`.
        *   Test role hierarchy boundaries (e.g., ops vs analyst).

### 2.2. Integration Tests (Backend API - `pytest` + `TestClient`)
**Objective:** Validate API contract, RBAC gating, and database side-effects (Audit Logs).
**Target Files:** `tests/test_admin_api.py`

*   **Authentication & Authorization:**
    *   `GET /api/admin/*` endpoints without cookies -> Expect `401`.
    *   `GET /api/admin/*` endpoints as standard `user` -> Expect `403`.
    *   `GET /api/admin/*` endpoints as `admin`/`ops` -> Expect `200`.
*   **Data Fetching & Masking:**
    *   `GET /api/admin/queries`: Validate response payloads are truncated and PII-masked (e.g., verify email/phone regex masking).
    *   `GET /api/admin/summary`: Validate aggregation logic against seeded test DB.
*   **State Mutation & Audit Trail:**
    *   `PATCH /api/admin/users/{user_id}`:
        *   Request as `ops` to change `daily_chat_limit`.
        *   Verify response is `200 OK`.
        *   **Crucial:** Query `admin_audit_logs` table to verify a new row was inserted with the correct `before_state`, `after_state`, and `admin_user_id`.
    *   `PATCH /api/admin/users/{user_id}` as `analyst` (Read-only) -> Expect `403`.

### 2.3. End-to-End (E2E) UI Tests (Frontend - `Playwright`)
**Objective:** Validate the operator UI experience using real browser contexts.
**Target Files:** `frontend/tests/e2e/admin.spec.ts` (Aligns with `PLAN_PLAYWRIGHT_TESTING.md`)

*   **Setup:** Use Playwright `storageState` to bypass login and inject an `admin` role session.
*   **Navigation & Layout:**
    *   Load `http://localhost:3000/admin/`.
    *   Verify Nginx successfully serves the static assets (`css/admin.css`, `js/admin.js`).
    *   Verify left-hand navigation and routing between Dashboard, Users, Queries, and Audit Logs.
*   **Role-Aware UI Rendering:**
    *   Login as `analyst`: Verify that "Edit" and "Suspend" buttons in the Users table are hidden or disabled.
    *   Login as `admin`: Verify all edit controls are visible.
*   **Operator Workflows:**
    *   **Workflow: Update User Quota**
        *   Navigate to "Users" tab.
        *   Search for a test user.
        *   Click "Edit", change `daily_chat_limit`, and save.
        *   Verify the UI reflects the new limit.
        *   Navigate to "Audit Logs" tab and verify the change appears at the top of the list.
    *   **Workflow: Monitor Queries**
        *   Navigate to "Queries" tab.
        *   Verify the table populates with recent masked chat logs.

---

## 3. Test Execution & CI/CD

### 3.1. Local Development Execution
```bash
# 1. Run Unit & API Integration Tests
cd backend
pytest tests/test_admin_models.py tests/test_dependencies.py tests/test_admin_api.py -v

# 2. Run E2E Playwright Tests
cd ../frontend
npm run test:ui --grep "admin"
```

### 3.2. CI/CD Integration
*   The backend API tests will automatically be included in the standard `pytest` workflow.
*   Update the existing Playwright GitHub Action (`.github/workflows/playwright.yml`) to ensure `/admin/` routes are reachable in the CI test server environment.

---

## 4. Risk & Edge Case Checklist
Before deploying the MVP, ensure tests cover these edge cases:
- [ ] **Missing Token Stats:** If a query was cached or failed, token usage might be null. Ensure `/api/admin/usage-stats` handles missing token payloads gracefully.
- [ ] **Pagination/Scale:** The `users` and `audit-logs` APIs must implement pagination. E2E tests should verify the "Next Page" button works.
- [ ] **Self-Lockout:** Prevent an admin from modifying their own `is_active` status to `false`.
- [ ] **Cross-Site Scripting (XSS):** Ensure the UI escapes user-generated content (like chat queries) when rendering the Query Monitor table.