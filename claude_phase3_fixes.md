# Phase 3 — security & access-control fixes

Applied on the `adopt-upstream` branch, on top of the adopted upstream backend.
Each entry maps to a bug in `backend/docs/bug_list.md` (and/or the claude review)
and lands as its **own commit** — `git log` on this branch is one commit per bug.
This file is intended to double as the basis for an **upstream pull request** to
MicroPyramid/Django-CRM.

**Deferred (discuss separately):** the org-API-key escalation chain —
`APIKeyAuthentication` + `OrganizationSerializer.api_key` exposure (review items ②③).

**Not in this phase (→ Phase 4: correctness / contract / tech-debt):** bugs
6–13, 15–21, 25, 26, 33.

**Note on RLS:** Phase 2 secured RLS (all 51 tables `FORCE`d, app runs as a
non-superuser role), which already blocks the *cross-tenant* class of several
bugs (4, 30). Those are fixed here as defense-in-depth / for the correct status
code, not because they are currently exploitable in this deployment.

---

## Fixes

### bug 23 — `RequireOrgContext.EXEMPT_PATHS` incomplete 🔴
Intended-public routes were blocked by the tenancy middleware with
`403 {"detail": "Organization context is required."}`, breaking real features.
Added the missing prefixes so each route reaches its own view, which enforces
its own auth (opaque portal token, api_setting apikey, or SNS signature).

- **Added prefixes:** `/schema/`, `/healthz/`, `/logout/`,
  `/api/public/` (widened from `/api/public/csat/`),
  `/api/leads/create-from-site/`, `/api/cases/inbound/`.
- **Files:** `common/middleware/rls_context.py`;
  `common/tests/test_exempt_paths.py` (new, anonymous-client regression tests).
- **Restores:** Swagger UI / ReDoc, health probe, logout, customer
  invoice/estimate portal, website lead capture, inbound-email webhook
  (also closes bugs 1, 2, 3, which share this root cause).
- **Upstream-relevant:** **yes.**
