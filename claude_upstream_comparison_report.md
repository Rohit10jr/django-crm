# Upstream Django-CRM — Analysis & Comparison Report

**Subject:** `D:\02_Personal\01_OpenSource\03_Applications\DjangoCrm\Django-CRM\backend`
**Compared against:** the findings in [`claude_review_plan.md`](./claude_review_plan.md) (review of `D:\02_Personal\04_projects\07_crm\backend`)
**Date:** 2026-07-23

---

## 1. Executive summary

**Short answer to "does the new code solve all the problems in my review plan?" — No. It solves roughly two-thirds of them, and it introduces several new security problems of its own.**

The headline correction first: **upstream is actively maintained.** Last commit is 2026-06-06, and recent history shows live feature work (Personal Access Tokens, an MCP server for AI-agent integration, per-request auth transport). Your original premise — "the original repo hadn't been maintained and stopped mid-refactor" — was accurate about *the snapshot you forked*, but is no longer true of upstream. They finished the refactor you got stranded inside, and kept building.

What genuinely improved is the **infrastructure**: the project boots, has real migrations, a real test suite, enabled tenant middleware, working row-level security, and a complete auth/org HTTP surface. Those were the blocking problems in your fork, and they are fixed.

What did **not** improve is a specific cluster of **application-logic bugs that both codebases inherit from the same lineage**. `created_by` is still compared against `Profile` in 31 places, six attachment-delete endpoints still have cross-org IDOR, comment creation is still broken in two apps, and `BaseModel.save()` still contains the byte-identical audit bug I found in your fork. These aren't bugs you introduced — they're upstream bugs you inherited.

Most importantly, upstream contains a **live privilege-escalation chain** that I verified end-to-end: any ordinary `role="USER"` member can read their org's API key from an endpoint that doesn't check role, then replay it to authenticate as an org **admin**.

### Scale of the change

| | Your fork | Upstream | |
|---|---|---|---|
| App code (excl. migrations) | 17,743 LOC | **79,599 LOC** | ~4.5× |
| Python files | 128 | **297** | |
| Test files | 14 (all broken stubs) | **73** | |
| Test functions | ~0 runnable | **2,024** | |
| Migrations | **zero** | 7–27 per app | |
| Django | 5.2.8 | **≥6.0.5** | |
| `manage.py check` | **crashes** | **passes clean** | |
| Django apps | 8 (5 disabled) | **11 (all enabled)** | +`orders`, `business_hours`, `macros` |

### 1.1 Cross-check against Codex's independent review

Codex reviewed the same upstream code and read this report ([`updated_original_backend_review.md`](./updated_original_backend_review.md)). **The two reviews reach the same verdict independently** — upstream is much healthier but has not closed the review plan, and is not production-ready as-is. Codex explicitly agrees on the priority ordering: org API-key escalation, missing DRF default permissions, attachment-delete IDORs, wildcard production CORS, and misleading JWT rotation are release blockers.

Codex also independently ran `manage.py check --settings=crm.test_settings` and got the same clean result I did.

**Two corrections to my report, both verified and now folded in (§2.4):**
1. `common/tasks.py:204` still reads `user.has_marketing_access` on a `User` — so my C11b "FIXED" was too generous; downgraded to PARTIAL.
2. `leads/tasks.py:159` sets `lead.created_by = profile` into a `User` FK — a residual type bug in task code that my view-layer-focused pass missed.

**Reconciling three numeric discrepancies between the reviews** (I re-measured; these are my verified figures):

| Metric | Mine | Codex | Reconciliation |
|---|---|---|---|
| Test files | 73 | 93 | **73 is correct.** Total `test_*.py` excluding `.venv`/`__pycache__` is 74, of which one is `crm/test_settings.py` (matches the glob but is a settings module). Codex's higher count likely included cached or vendored paths. |
| `Profile == created_by` sites | 31 | 34 | **Both defensible.** Mine counted active-code comparisons in the 7 business apps; Codex used a broader regex that also picks up `common/views/document_views.py` (4 more sites, which I noted separately as out-of-scope). Treat **~34** as the true total to fix. |
| Python files | 297 | 426 | **Both correct, different scopes.** Mine excludes migrations and `__pycache__`; Codex's includes migrations. Upstream has 100+ migration files. |

**One useful recommendation from Codex I'm adopting:** `business_hours` and `macros` views declare only `IsAuthenticated` and lean on `RequireOrgContext` middleware for tenant safety. They should declare `HasOrgContext` explicitly, so the guarantee doesn't depend on middleware ordering staying correct.

---

## 2. Verdict against every finding in `claude_review_plan.md`

| # | Problem (from my review of your fork) | Upstream verdict |
|---|---|---|
| **C1** | Won't boot — installed apps import non-installed apps; URLConf includes disabled apps; 3 syntax errors | ✅ **FIXED** |
| **C2** | `common/views.py` empty, `common/urls.py` fully commented — no auth/org endpoints | ✅ **FIXED** |
| **C3** | Tenant middleware disabled; no `DEFAULT_PERMISSION_CLASSES` | ⚠️ **PARTIAL** |
| **C4** | Generic comments/attachments written to phantom FKs | ⚠️ **PARTIAL** |
| **C5** | `created_by` (User) compared to `request.profile` (Profile) | ❌ **NOT FIXED** |
| **C6** | Cross-org IDOR on `.get(pk=pk)` | ⚠️ **PARTIAL** |
| **C7** | Every app reinvents `BaseOrgModel` / view mixins / permissions | ⚠️ **SPLIT** |
| **C8** | Throwaway `Celery("redis://")`; empty `crm/__init__.py`; swapped task args | ✅ **FIXED** |
| **C9** | Old+new duplicate modules, dead code | ✅ **MOSTLY FIXED** |
| **C10** | API key = arbitrary-admin impersonation; plaintext; serialized to clients | ❌ **NOT FIXED** (+ new escalation) |
| **C11a** | `BaseModel.save()` sets `updated_by` on insert | ❌ **NOT FIXED** (byte-identical) |
| **C11b** | `jwt_payload_handler` references phantom `User` fields | ⚠️ **PARTIAL** (see §2.4) |
| **C12** | Dev-open settings (`DEBUG=True`, `ALLOWED_HOSTS=*`, wildcard CORS, dup `DEFAULT_AUTO_FIELD`, 365-day tokens) | ✅ **MOSTLY FIXED** |
| **RLS** | Row-level security never actually enforced | ✅ **FIXED in code** (deployment caveat) |
| **Migrations** | Zero migrations anywhere | ✅ **FIXED** |
| **Tests** | Empty stubs that couldn't import | ✅ **FIXED in quantity** (caveat below) |

### 2.1 What's genuinely fixed

**C1 — Boots cleanly.** I ran it: `manage.py check` → *"System check identified no issues (0 silenced)."* All 11 apps are in `INSTALLED_APPS`; URL includes match; the three syntax-error files are gone or fixed (`common/token_generator.py` deleted entirely).

**C2 — Full auth/org HTTP surface exists.** `common/views.py` is now a 12-module package and `common/urls.py` has 138 lines of live routes: token refresh, `me`, profile, org switch, Google OAuth callback, passwordless magic-link + OTP, org/org-settings CRUD, users, dashboard, activities, documents, teams, tags, api-settings, custom-fields, and notifications with an SSE stream. Note there is deliberately **no password login/register** — auth is Google OAuth + magic link by design.

**C8 — Celery correctly wired.** `crm/__init__.py:5` now has `from .celery import app as celery_app` with `__all__`. Zero `Celery("redis://")` throwaway apps remain; 8 modules use `@shared_task`. There's a real `beat_schedule` (recurring invoices, overdue checks, payment reminders, expired estimates, stale opportunities, goal milestones, SLA breach scan every 5 min, stale-timer cleanup every 30 min, notification purge daily).

**C11b — Phantom `User` fields *mostly* gone.** `jwt_payload_handler` and `file_prepend` no longer exist anywhere, and JWT claims are built by `OrgAwareRefreshToken` reading `role` from `Profile`, which is correct. `User` also gained a real `name` field (`common/models.py`), replacing the old `first_name`/`last_name` assumptions. **But one residual survives** — see §2.4.

**C12 — Settings hardened.** `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` are all env-driven; there's a `SECRET_KEY` guard that refuses an insecure key outside dev; `DEFAULT_AUTO_FIELD` appears exactly once; tokens are now 1 hour / 14 days (was 1 day / 365 days); HSTS added; no import-time `print()`.
⚠️ **One regression:** `crm/settings.py:148` does `from .server_settings import *` when `ENV_TYPE == "prod"`, and `crm/server_settings.py:27` unconditionally sets `CORS_ORIGIN_ALLOW_ALL = True`. **Wildcard CORS is restored in production** — the one setting you'd least want re-opened.

**RLS — actually enforced now.** The full chain works: middleware registered (`settings.py:63`) → `SELECT set_config('app.current_org', ...)` (`rls_context.py:170-172`) → policies applied by migration (`common/migrations/0002_enable_rls.py` + 5 more) with a fail-safe `NULLIF` predicate so empty context returns zero rows → context reset after response to prevent leakage across pooled connections. The `manage_rls --test` bug I flagged (querying table `company` instead of `organization`) is fixed.
⚠️ **Deployment caveat:** PostgreSQL superusers bypass all RLS, and the shipped `.env.example` sets `DBUSER=postgres`. `manage_rls --verify-user` exists to catch this but isn't enforced at boot. **RLS is real only if you change the DB user.**

**C9 — Dead code largely cleaned.** The duplicate `invoices/serializers.py` is gone (they kept `serializer.py`), `invoices/forms.py` gone, `common/token_generator.py` gone. `invoices/views.py` and `common/access_decorators_mixins.py` are now 2-line tombstone comments explaining the removal — good practice.
Remaining: `common/status.py` (62 lines duplicating DRF's `status`, **imported nowhere** — genuinely dead), and `invoices/tests_legacy.py` (521 lines). Note `leads/forms.py` survives but is **not** dead — it's imported at `leads/views/lead_interactions.py:12` for CSV upload validation.

**C7 (the good half) — `AssignableMixin` properly shared.** This is a real fix: one definition in `common/base.py:13-52`, inherited by 9 models (Account, Contact, Lead, Opportunity, Case, Task, Invoice, Estimate, RecurringInvoice). **Zero copy-pasted duplicates remain.**

### 2.2 What is NOT fixed — the bugs you'd inherit

**C5 — `created_by` vs `Profile`: not fixed in 6 of 7 apps.** `created_by` is an FK to `common.User`, but views still compare it to `request.profile`. 31 broken sites remain:

| App | Broken sites |
|---|---|
| accounts | `views.py:299, 465, 478, 490, 586, 653, 878` |
| contacts | `views.py:291, 436, 460, 465, 572, 649, 892` |
| opportunity | `opportunity_views.py:367,580,594,606,683,776`; `opportunity_interactions.py:162`; `kanban_views.py:162` |
| tasks | `task_views.py:283,315,405,482,634,797,959` |
| invoices | `api_views.py:255,551,605,832,1298,1804` |
| cases | `views.py:645, 1109` |
| **leads** | **none — fully fixed, use it as the reference pattern** |

Two consequences: ownership checks silently always fail (non-admin creators get 403 on their own records), and some sites **hard-crash** — `self.task_obj.created_by.user.email` dereferences `.user` on a `User`, which doesn't exist.

**C6 — Cross-org IDOR: one hole left, in all six apps.** Detail views and comment views are now properly org-scoped. But every `*AttachmentView.delete` is still unscoped:

```python
# cases/views.py:1104-1109 — identical shape in 5 other apps
def delete(self, request, pk, format=None):
    self.object = self.model.objects.get(pk=pk)          # ← no org filter
    if (request.profile.role == "ADMIN" or ...):          # ← checks YOUR role, not the row's org
```
An org-A admin passes their own `role == "ADMIN"` check and deletes an **org-B** attachment. Sites: `accounts:874`, `contacts:888`, `leads/lead_interactions:204`, `opportunity/opportunity_interactions:158`, `cases:1105`, `tasks:955`. **Only `invoices` got this right** (`api_views.py:1796` filters by org) — copy that pattern. Also `contacts/views.py:569` detail-POST is unscoped with no follow-up check.

**C4 — Generic relations: reads fixed, writes still broken in two apps.** All 7 apps now read via `ContentType.objects.get_for_model(...)` correctly, and attachment writes were converted. But comment creation still passes phantom kwargs in `accounts/views.py:599` (`save(account_id=...)`) and `contacts/views.py:585` (`save(contact_id=...)`). The comment is **silently dropped with HTTP 200**. Upstream fixed exactly this in `opportunity` and left a comment explaining it — they just didn't propagate it.
Also: no `GenericRelation` was ever added, so 6 phantom serializer fields (`account_attachment`, `contact_attachment`, `lead_attachment`, `lead_comments`, `task_attachment`, `task_comments`) resolve to nothing and are silently omitted from responses — the documented API contract is a lie. `Activity` is still string-based (`entity_type` + `entity_id`) while Comment/Attachments use ContentType, so the inconsistency I flagged persists. And with no `GenericRelation`, deleting a parent record **orphans** its comments and attachments rather than cascading.

**C11a — The audit bug is byte-identical.** `common/base.py:71-77`:
```python
if self._state.adding:
    self.created_by = user
    self.updated_by = None
self.updated_by = user      # ← outside the if; overwrites the None on every insert
```
Exactly the same defect as your fork.

**C3 — Still no default permissions.** Middleware is on (good), but `REST_FRAMEWORK` still has **no `DEFAULT_PERMISSION_CLASSES`**, so DRF's fail-open `AllowAny` remains the default. In practice most views set permissions explicitly (only 8 of 196 view classes don't, and 7 of those inherit a safe base), and `RequireOrgContext` provides a blanket 403 — but the fail-open default is still there.

**C7 (the bad half) — the shared view layer was deleted, not adopted.** `common/mixins.py` shrank from 424 to 46 lines because `OrgViewMixin`/`OrgFilterMixin` were **removed outright** — zero matches repo-wide. `BaseOrgModel` is inherited by exactly 3 models (`orders.Order`, `orders.OrderLineItem`, `common.PersonalAccessToken`) and by **no business app**; 103 hand-declared `org` FKs and indexes remain. `common/models.py:697-700` explicitly documents the refusal. There are **191 `APIView` subclasses and 0 DRF generics/ViewSets.** So the fat-view duplication I flagged is now permanent by design, not an accident. N+1 mitigation is partial: `leads`/`tasks`/`invoices`/kanban list views have `select_related`/`prefetch_related`; `accounts`/`contacts`/`opportunity`/`cases` lists and **all** detail views do not.

### 2.3 The test suite caveat — important

Upstream has **2,024 test functions** across 73 files, with `pytest.ini`, a separate `crm/test_settings.py`, 13 root fixtures, coverage reporting, and `slow`/`postgres_only` markers. That's a genuine transformation from your fork's 14 broken stubs.

**But the suite encodes several of the above bugs as expected behavior:**

```python
# tasks/tests/test_tasks_api.py:1393
with pytest.raises(AttributeError, match="has no attribute 'user'"):
    user_client.get(f"/api/tasks/{task.id}/")

# contacts/tests/test_contacts_api.py:1066
with pytest.raises(TypeError, match="contact_id"):
```

These are *passing tests that assert a crash is correct*. So **a green test run here does not mean those paths work** — it means the breakage is pinned. Treat coverage numbers from this suite with that in mind.

### 2.4 Residual `User`/`Profile` type bugs outside the view layer

A second independent review (Codex) caught two type-confusion bugs that my first pass missed because they live in **task/util code rather than views**. I verified both firsthand:

- **`common/tasks.py:204`** — `if user.has_marketing_access:` where `user` is a `User`. That flag lives on `Profile`, not `User`. This is the same phantom-field class of bug as the old `jwt_payload_handler`, which is why C11b is downgraded from FIXED to PARTIAL above.
- **`leads/tasks.py:159`** — `lead.created_by = profile` assigns a `Profile` into a `User` FK. Notably this is the *only* offender of its kind: every other `created_by=profile...` site in the codebase correctly writes `profile.user` (verified across 14 matches). So `leads` is clean at the view layer (as stated under C5) but **not** in its Celery task.

**Takeaway:** when fixing C5, don't grep only for `== created_by` comparisons in views — also audit **assignments** (`created_by=`, `updated_by=`) and `user.has_*_access` reads in `tasks.py`/`services/` modules.

### 2.5 Invoice bugs from my original review — all fixed

My review of your fork flagged several invoice-specific defects. Upstream resolved them, which I hadn't credited in the first draft of this report:

| Original invoice bug | Upstream status |
|---|---|
| Money computed in `float()` on `Decimal` fields | ✅ **FIXED** — zero `float(` calls remain in `invoices/api_views.py` |
| Malformed `Response({"error": True}, data)` (dict passed as HTTP status) | ✅ **FIXED** — pattern no longer present |
| `send_email.delay(recipients, invoice_id)` argument order swapped vs signature | ✅ **FIXED** — call site now matches `send_email(invoice_id, recipients, org_id, ...)` |
| Duplicate `serializer.py` / `serializers.py` | ✅ **FIXED** — the dead module is gone |
| `request.company` (a tenancy notion that didn't exist on the models) | ✅ **FIXED** — removed from active invoice APIs |

⚠️ One caveat worth testing: money is now `Decimal` throughout, but not every total calls `.quantize()` explicitly, so rounding policy should be pinned by a test rather than assumed.

Also resolved: **`leads.Company`** — the confusingly-named lead-company model that collided semantically with the `Org` tenant — **has been removed** from `leads/models.py`.

---

## 3. New security problems in upstream (not in my original review)

These are defects in the upstream code that your fork did not have or that I hadn't catalogued. Listed most severe first.

### 3.1 🔴 CRITICAL — Ordinary user → org admin privilege escalation

**I verified this chain end-to-end myself:**

```
common/views/organization_views.py:91    OrgUpdateView.permission_classes = (IsAuthenticated,)
                               :215-241  def get(...)  — docstring says "Only organization admins
                                                        can update", but GET checks only org
                                                        membership. No role check. (put/patch do.)
                               :239      returns OrganizationSerializer(org).data
common/serializer.py:96                  fields = ("id", "name", "api_key")   ← key exposed
common/external_auth.py:29-34,46         Org.objects.get(api_key=...) → Profile.objects.filter(
                                         org=..., role="ADMIN").first() → return (profile.user, None)
```

Any `role="USER"` member calls `GET /api/org/<their-own-org-id>/`, reads `api_key` from the JSON, then sends `Token: <api_key>` on subsequent requests and is authenticated as an arbitrary org **ADMIN**. Roles are only `ADMIN`/`USER`, so this is complete escalation. **This should be reported to MicroPyramid.**

### 3.2 🔴 C10 unfixed — API key is still admin impersonation

The new `common/pat_auth.py` (Personal Access Tokens) is genuinely well-built: `bcrm_pat_` prefix, SHA-256 hashed at rest, raw value returned exactly once, revoke/expiry checks, IDOR-guarded by both `org` and `profile`, and it authenticates as the *owning* profile. But it was added **alongside** the org-API-key path, not as a replacement. Both are registered in `DEFAULT_AUTHENTICATION_CLASSES`, the key is still plaintext (a plain `uuid4()`, not a CSPRNG secret), and still serialized to clients.
Note also: PAT `scopes` are stored but **not enforced** — the code says so explicitly: *"Do not treat `scopes` as a trust boundary until enforcement lands."*

### 3.3 🟠 JWT refresh rotation is inert

`settings.py:333-334` declares `ROTATE_REFRESH_TOKENS: True` and `BLACKLIST_AFTER_ROTATION: True`, but `rest_framework_simplejwt.token_blacklist` is **not in `INSTALLED_APPS`** and no blacklist call site exists. The custom `OrgAwareTokenRefreshView` mints a new pair but never invalidates the presented one. **A stolen refresh token stays valid for its full 14 days and can be replayed indefinitely.** The setting gives false assurance.

### 3.4 🟠 Magic-link tokens stored in plaintext

`common/views/auth_views.py:537` writes `secrets.token_hex(32)` unhashed, while the sibling OTP is properly PBKDF2-hashed. Read access to the DB yields live 10-minute account-takeover links. Entropy and single-use enforcement are otherwise correct.

### 3.5 🟠 `IsSuperAdmin` trusts an email suffix

`common/permissions.py:77`: `return request.user.email.endswith("@micropyramid.com")`. Platform-level authority derived from a hardcoded vendor domain on a self-asserted field — and registration is by magic link to any address that receives mail. Currently only referenced by tests, but it's exported and ready to be attached to a view.

### 3.6 🟡 Functional bug — public client portal is bricked

`RequireOrgContext.EXEMPT_PATHS` lists `/api/public/csat/` but **not** `/api/public/`. The invoice/estimate customer portal (`invoices/public_views.py`, deliberately `permission_classes = []`) is mounted at `/api/public/invoice/<token>/` and gets a 403 *"Organization context is required"* before reaching the view. `/healthz/` and `/schema/` are 403'd the same way.

### 3.7 🟡 Other

- **500 on a bad API key** — `get_company.py:178-180` raises DRF's `AuthenticationFailed` from inside middleware, where DRF's exception handler can't see it → HTTP 500 + stack trace when `DEBUG=True`.
- **No throttling** — no `DEFAULT_THROTTLE_CLASSES`. Magic-link request is limited per-email, but Google OAuth, token refresh and org enumeration have no IP-level limit.
- **`invoices/api_views.py:1775`** — `created_by=request.profile` assigns a `Profile` to a `User` FK → runtime error.

---

## 4. The three new Django apps

### 4.1 `business_hours` — working-hours calendar for SLA math

**What it does.** Lets each org define when it's actually open: per-weekday open/close times, an IANA timezone, and full-day holidays. This exists so SLAs are meaningful — a "4-hour first response SLA" means *4 working hours*, so a ticket filed Friday 4:30pm isn't auto-breached over the weekend.

**Models.** `BusinessCalendar` (14 nullable `TimeField`s for `{monday..sunday}_{open,close}`, validated IANA `timezone`, partial-unique "one default per org") and `BusinessHoliday` (full-day, unique per `(calendar, date)`).

**Core logic** — `calendar.py:44-108`, `add_business_hours(start, hours, calendar)`: a forward-walking working-time accumulator. It skips closed weekdays and holiday dates, fast-forwards to opening time when the cursor is before it (waiting-for-open never counts against SLA), consumes each day's open window until the budget is exhausted, and converts back to the caller's original timezone. DST-safe because it rebuilds tz-aware datetimes per local date rather than adding fixed offsets — explicitly tested across an America/New_York spring-forward. Guardrails: a 5-year loop cap, and graceful degradation to plain wall-clock when there's no calendar or no open windows (so orgs without a calendar keep 24/7 behavior).

**API.** 4 endpoints under `/api/business-hours/` — GET calendar (auto-creates a Mon–Fri 9–5 UTC default on first access), admin-only PUT, admin-only holiday add (idempotent) and delete.

**Maturity.** Shipped. 3 test files, and its initial migration does schema + RLS + a data backfill creating a default calendar for every existing org.

**Gaps.** An N+1 risk: `calendar.py:69` uses `.values_list()` which bypasses the `prefetch_related` set up by `get_default_calendar`, and `Case` recomputes the calendar on every SLA property access — a case list serializing 4 SLA fields can issue ~8 extra queries *per row*. `_get_or_create_default` is also racy (concurrent first-loads can collide on the unique constraint → 500).

### 4.2 `macros` — canned responses with placeholder substitution

**What it does.** Reusable reply templates for support agents. Templates contain `%token%` placeholders expanded server-side against a specific case and the acting agent, so "Hi %customer_name%, this is %agent_name% from %org_name%" comes out personalized.

**Model.** `Macro` with `title`, `body`, `scope` (`org` | `personal`), nullable `owner`, `is_active` soft-delete, and `usage_count`. A **DB `CheckConstraint`** enforces the scope/owner pairing (`org` ⇒ owner NULL, `personal` ⇒ owner NOT NULL) rather than trusting the view layer.

**Core logic** — `render.py`. Seven supported tokens (`customer_name`, `customer_email`, `case_id`, `case_subject`, `agent_name`, `agent_email`, `org_name`). The notable design decision: **unknown tokens are deliberately left literal** — `%priority%` renders as `%priority%` so the agent *sees* the mistake instead of silently sending damaged text, while known-but-empty tokens render as blank. A companion `find_unknown_placeholders()` surfaces typos as a soft warning at save time without blocking. Because this project's `User` has only `email`, `agent_name` resolves to the email local-part so signatures read naturally.

**API.** 6 endpoints under `/api/macros/`. Non-admins can only create `personal` macros; org macros are soft-deleted while personal ones are hard-deleted.

**Maturity.** Shipped, 3 test files, wired into the ticket composer UI (`MacroPicker.svelte`).

**Gaps.** Minor info leak — GET on someone else's personal macro returns 404 but PATCH/DELETE returns 403, letting a caller distinguish "exists but not yours" from "doesn't exist". Hard-coupled to `cases` (render *requires* a `case_id`), so macros can't be used for leads/contacts/opportunities.

### 4.3 `orders` — sales orders (⚠️ dormant / unfinished)

**What it's meant to do.** Represent sales orders — the record created after a deal is won, closing the Opportunity → Order → Invoice loop: what was bought, at what price, billing/shipping addresses, and a Draft → Activated → Completed → Cancelled lifecycle.

**Models.** `Order` and `OrderLineItem`, both on `BaseOrgModel` (the only new app that uses it). Links to `Account` (CASCADE, required), `Contact` and `Opportunity` (SET_NULL). Money is correctly `Decimal(15,2)`. Reuses `invoices.Product` for the catalog rather than defining its own. `OrderLineItem.save()` inherits `org` from the parent, guards cross-tenant mismatch, and recomputes `total = quantity × unit_price − discount`.

**⚠️ It has no API at all.** No `views.py`, no `serializers.py`, no `urls.py`; not in the URL tree; **zero inbound references from any other app**; no frontend page. The only interface is the Django admin.

**Other gaps if you adopt it.** Header `subtotal`/`total_amount` are **never recomputed** from line items, so they can silently diverge from the sum. No status-transition validation, no date automation, no order→invoice conversion, no `order_number` uniqueness or generation. Its cross-tenant guard raises a bare `ValueError` (would surface as a 500, not a 400). Tests cover models only — 28 tests, no API tests because there's no API.

### 4.4 An architectural inconsistency worth knowing

`orders` uses `BaseOrgModel`; `business_hours` and `macros` deliberately do **not** — they use `BaseModel` + a hand-declared `org` FK, both citing the same design-decision doc, relying on RLS for isolation. So the "always use `BaseOrgModel`" convention I recommended for your fork **is not followed upstream either**. If you adopt upstream, adopt their convention rather than mine, or you'll fight the codebase.

---

## 5. The rebuilt `cases` app (not new, but transformed)

`cases` went from ~4 modules to ~30 — from a CRUD ticket table to a **full helpdesk/ITSM engine**, built in explicit tiers.

| Feature | What it does |
|---|---|
| **SLA + pause** | First-response/resolution deadlines from priority, computed in *business hours*; clock **pauses** while status is `Pending` (waiting on customer). Pause time added back as real elapsed time, deliberately not re-walked through the calendar. |
| **Escalation** | Celery beat every 5 min finds breached non-terminal cases; per-priority notify/reassign policies; capped at 3 escalations with a 1h cooldown. |
| **Auto-routing** | Rules match on priority/type/account/tags/sender-domain/mailbox/custom-fields; assign via round-robin, least-busy, direct, or by-team. Round-robin takes `SELECT … FOR UPDATE` on a cursor row so concurrent case creation can't double-assign. Has a dry-run endpoint. |
| **Inbound email → ticket** | Public AWS SNS webhook with real signature verification (host-pinned cert fetch — the defence against a forged `SigningCertURL`), RFC-5322 parsing, spam/bounce/autoresponder filtering, 4-tier thread matching, auto-contact creation, idempotent on `Message-ID`. |
| **Approvals** | Closing a case can require sign-off, enforced in `Case.clean()`. Double-approval races prevented by `select_for_update` + state re-check. |
| **Merge / unmerge** | Merge relocates comments/attachments/emails and inherits email thread IDs (so replies to the duplicate land on the primary); unmerge fully reverses it from a stored JSON audit blob. Merge chains forbidden. |
| **Time tracking** | Partial unique index `one_active_timer_per_profile` makes two concurrent timers impossible at the DB level. Billable flag with rate **snapshotting**, convertible into invoice line items. Forgotten timers auto-stopped after 12h. |
| **CSAT** | 30-min-delayed post-close survey (so close-then-reopen doesn't spam), signed one-time link, **only the SHA-256 hash stored**, anonymous 1–5 rating editable for 24h. |
| **Knowledge base** | Draft→reviewed→approved→published articles, plus an agent-side suggester that seeds from the case text when no query is given. |
| **Parent/child** | ITIL problem→incident trees, max depth 3, with cycle detection. |
| **Kanban** | Status mode or custom pipelines with WIP limits; fractional ordering (`Decimal(15,6)` midpoint insertion) so a drag writes only the moved row. |
| **Analytics** | FRT/MTTR/backlog/per-agent/SLA-breach with percentiles, drilldown, and streaming CSV export. Percentiles computed in Python because SQLite (test DB) lacks `percentile_cont`. |
| **CSV import** | Two-phase preview→commit, all-or-nothing, with bulk-prefetched reference maps (~6 queries for 5,000 rows instead of ~25k). |

**New `common` infrastructure:** per-org **custom fields** (schema extension with no migration, with PATCH-safe merge semantics and soft-delete value preservation), **duplicate detection** (fuzzy contact/lead/account matching — built and tested but not yet wired into any view), **in-app notifications** (Redis pub/sub on an org-scoped channel + SSE stream, with publish failures deliberately swallowed so they can't break the originating request), **PAT auth**, and a **security audit log** separate from the business activity log.

**Multi-tenancy discipline is good in the new code:** every path that bypasses request middleware — the SNS webhook, public CSAT endpoints, and all Celery beat tasks — manually calls `set_rls_context(org_id)`, and the org-iterating tasks explicitly clear it afterward so a worker connection can't leak org context between tasks.

---

## 6. Recommendation

**Adopt upstream as your base rather than continuing to repair your fork.** The reasoning:

1. Your fork's blocking problems (won't boot, no migrations, no auth surface, no tests, disabled middleware) are exactly what upstream fixed. Repairing them yourself was the multi-week Phase 0–2 effort in `claude_review_plan.md`; upstream has already done it.
2. Upstream is ~4.5× the functionality and is actively maintained, so you'd get future fixes rather than diverging further.
3. The bugs that *remain* are the same bugs your fork has — you gain nothing by keeping your version, and you'd still have to fix them either way.

**But adopt with your eyes open.** The work in `claude_review_plan.md` isn't wasted — it becomes your hardening checklist against upstream. Before putting it in front of real data:

**Must fix before any production use:**
1. **The privilege-escalation chain (§3.1)** — remove `api_key` from `OrganizationSerializer`, or add an admin check to `OrgUpdateView.get`. Do both.
2. **Retire the org-API-key auth path (§3.2)** — PAT already does this job properly. Delete `APIKeyAuthentication` from `DEFAULT_AUTHENTICATION_CLASSES`.
3. **Change `DBUSER` off `postgres`** — otherwise RLS, the entire defence-in-depth story, is inert.
4. **Fix the 6 attachment-delete IDORs (C6)** — copy the `invoices/api_views.py:1796` pattern.
5. **Add `DEFAULT_PERMISSION_CLASSES` (C3)** — `[IsAuthenticated, HasOrgContext]`, then mark public endpoints `AllowAny` explicitly.
6. **Remove `CORS_ORIGIN_ALLOW_ALL = True` from `server_settings.py`** — it silently re-opens wildcard CORS in prod.
7. **Install `token_blacklist` or drop the rotation settings (§3.3)** — don't ship a setting that implies protection it doesn't provide.

**Should fix soon:**
8. The **~34** `created_by` comparisons (C5) — mechanical, and `leads`' view layer is the proven reference. Best done once as a shared `is_creator(profile, obj)` helper or a single object-permission class, rather than 34 inline edits.
9. **Audit task/service code for the same type confusion (§2.4)** — not just views. Concretely: `leads/tasks.py:159` (`created_by = profile`) and `common/tasks.py:204` (`user.has_marketing_access`). Grep for `created_by=`, `updated_by=`, and `user.has_*_access` outside view modules.
10. Comment creation in `accounts`/`contacts` (C4) — copy the fix upstream already applied in `opportunity`.
11. `BaseModel.save()` audit bug (C11a) — a one-line `else`.
12. Hash magic-link tokens (§3.4); scope `IsSuperAdmin` off an email suffix (§3.5); exempt `/api/public/` from `RequireOrgContext` (§3.6).
13. Declare `HasOrgContext` explicitly on `business_hours` and `macros` views instead of relying on middleware ordering.
14. Pin invoice rounding policy with a test (money is `Decimal` now, but `.quantize()` isn't universal).
15. Delete dead `common/status.py`; decide on `invoices/tests_legacy.py`.

**Then, and only then**, consider whether you want `orders` at all — it's dormant and would need a full API layer built.

**One process note:** because upstream's test suite pins several bugs as expected behavior, fixing items 8–10 will make those tests *fail*. That's correct — update the tests to assert the fixed behavior rather than reverting the fix.

---

## Appendix — how this was verified

- `manage.py check` executed against both codebases (yours crashes; upstream passes clean).
- Line/file/test counts measured directly.
- Git history and commit dates read from the upstream repo.
- The privilege-escalation chain (§3.1), the `BaseModel.save()` bug, the API-key impersonation path, and the `OrganizationSerializer` field list were each read and confirmed firsthand at the cited `file:line`, not taken on trust.
- Five parallel deep analyses covered: the three new apps; config/auth/security (C1, C2, C3, C10, C11, C12, RLS); the data layer (C4, C5, C6, C7) per app; the rebuilt `cases` app and new `common` infrastructure; and Celery/dead-code/tests (C8, C9).
- The Celery/dead-code/test analysis was stopped after it blocked attempting to run the full 2,024-test suite (which needs a live database); its static findings were complete, and I re-verified C8, C9 and the test-suite survey directly.
- **Cross-checked against a second independent review** (Codex, `updated_original_backend_review.md`), which reached the same verdict and the same blocker ordering. Its two corrections to this report (`common/tasks.py:204`, `leads/tasks.py:159`) were verified firsthand and folded into §2.4; three numeric discrepancies were re-measured and reconciled in §1.1.
- **Not verified:** no test suite was executed and no runtime request was made against either codebase — findings are from static analysis plus `manage.py check`. Claims about runtime behavior (e.g. the escalation chain) are read from code paths, not exploited. The escalation chain in particular is a *code-path* finding: I confirmed each link (no role check on GET → `api_key` in serializer fields → API-key auth returns an admin profile) but did not execute the exploit.
