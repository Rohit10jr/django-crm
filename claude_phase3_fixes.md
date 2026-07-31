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

### bug 27 — `APISettingsListSerializer` leaks `apikey`, omits `id` 🟠
The lead-capture `apikey` (a secret) was returned to **any** authenticated org
member, and the serialized rows had **no `id`**, so a listed row couldn't be
edited or deleted from the list response.
- **Fix:** add `id` to the fields; drop `apikey` from reads for non-admins via
  a role-aware `to_representation` (admins still receive it). Pass request
  context in `DomainList.get` / `DomainDetailView.get`.
- **Files:** `common/serializer.py`, `common/views/settings_views.py`,
  `common/tests/test_apisettings_apikey.py` (new).
- **Note:** this serializer *also* nests `OrganizationSerializer`, which leaks
  the org `api_key` — left untouched here (that's the deferred ②③ item).
- **Upstream-relevant:** **yes.**

### bug 14 — `InboundMailboxSerializer` leaks `webhook_secret` 🟠
The mailbox list/detail reads returned `webhook_secret` (which authenticates
inbound-email webhooks) to any authenticated org member, letting them forge
inbound mail for the org.
- **Fix:** drop `webhook_secret` from reads for non-admins via a role-aware
  `to_representation` (admins still receive it — including the create response
  that reveals the auto-generated secret once). Pass request context in the
  mailbox list/detail/create/update views.
- **Files:** `cases/serializer.py`, `cases/inbound_views.py`,
  `cases/tests/test_mailbox_secret.py` (new).
- **Upstream-relevant:** **yes.**

### bug 5 — dead `created_by` ownership check (30 sites) 🟠
`request.profile == <obj>.created_by` compared a `Profile` to a `User` FK, which
is never equal, so a record's non-admin **creator was locked out of their own
record**. Replaced with `request.profile.user == …created_by` across 30 sites.
- **Files:** `accounts/views.py`, `contacts/views.py`,
  `opportunity/views/{opportunity_views,opportunity_interactions,kanban_views}.py`,
  `tasks/views/task_views.py`, `invoices/api_views.py`, `cases/views.py`,
  `common/views/document_views.py`.
- **Upstream-relevant:** **yes.**

### bug 29 — accounts `PUT` validates before permission check 🟡
The ownership check sat inside `if serializer.is_valid()`, so an unauthorized
caller sending a malformed body got a `400` leaking serializer constraints
instead of `403`. Moved the check above validation (`accounts/views.py`).
- **Upstream-relevant:** **yes.**

### bug 28 — leads `PUT` missing ownership check 🟠
`LeadDetailView.put` checked only org-match, so a non-admin blocked by `PATCH`
could send the same change as `PUT` and fully overwrite/convert any lead in the
org. Added the same ownership gate `PATCH` enforces, before validation
(`leads/views/lead_views.py`).
- **Upstream-relevant:** **yes.**

### bug 31 — lead creator wrongly denied 🟠
`get_context_data` appended `profile.user` (a User) to a list of Profile ids, so
a lead's creator failed the `profile.id` membership test and got `403`. Append
`profile.id` (`leads/views/lead_views.py`).
- **Upstream-relevant:** **yes.**

### bug 30 — contacts `POST` not org-scoped 🟢 (downgraded by RLS)
`Contact.objects.get(pk=pk)` had no org filter. RLS already blocks the
cross-tenant write; the fix adds the explicit `get_object_or_404(..., org=…)`
and turns a 500-on-unknown-pk into a 404 (`contacts/views.py`).
- **Upstream-relevant:** **yes.**

### bug 4 — attachment-delete lookups not org-scoped (6 sites) 🟢 (defense-in-depth)
The 6 attachment-delete handlers did `self.model.objects.get(pk=pk)` with no org
filter. RLS already blocks cross-tenant delete; added
`get_object_or_404(self.model, pk=pk, org=request.profile.org)` for an explicit
check + proper 404 (accounts/contacts/leads/opportunity/cases/tasks).
- **Upstream-relevant:** **yes.**

### bug 32 — soft-deleted lead pipelines writable by id 🟡
`get_object`, stage-create and stage-reorder looked up `LeadPipeline` without an
`is_active` filter, so archived pipelines stayed editable by id. Added
`is_active=True` (`leads/views/kanban_views.py`). *Follow-up:* check Case/Task
pipeline siblings for the same pattern.
- **Upstream-relevant:** **yes.**

### ④ default DRF permission = IsAuthenticated 🟠
`DEFAULT_PERMISSION_CLASSES` was unset (DRF default AllowAny), so a view could be
public by omission. Set it to `IsAuthenticated` (defense-in-depth behind the
tenancy middleware). Intended-anonymous views already declare permissions
explicitly; `CreateLeadFromSite` relied on the old default, so it got an explicit
`AllowAny` (`crm/settings.py`, `leads/views/lead_interactions.py`).
- **Upstream-relevant:** **yes.**

### CORS — misleading `CORS_ORIGIN_ALLOW_ALL = True` 🟢 (not a live bug)
In `server_settings.py` (prod), overridden by the env-based CORS config in
`settings.py` imported earlier — dead code that read as an allow-all. Replaced
with a clarifying comment.
- **Upstream-relevant:** **yes.**

### Deferred (not done — discuss separately)
- **②③ org-API-key escalation chain** — `APIKeyAuthentication` authenticates as
  an arbitrary org admin, and `OrganizationSerializer` leaks the org `api_key`.
  Left untouched pending a decision on removing vs securing the org-key auth.

---

## Result

Full test suite (`crm.test_settings`, SQLite) after all Phase 3 fixes:
**16 failed · 2033 passed · 16 skipped** — vs the Phase 2 baseline of
**50 failed · 1986 passed**. That is **34 baseline failures fixed, 0
regressions**, plus 13 new regression tests added. The 16 remaining failures are
Phase 4 correctness items (bugs 6–13, 15–21), not touched here.
