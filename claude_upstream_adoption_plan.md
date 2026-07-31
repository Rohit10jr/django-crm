# Upstream Adoption Plan — Step-by-Step

**Goal:** bring the updated upstream Django-CRM backend into this repository, and apply every fix recommended in [`upstream_comparison_report.md`](./upstream_comparison_report.md).

**Source (upstream):** `D:\02_Personal\01_OpenSource\03_Applications\DjangoCrm\Django-CRM\backend`
**Target (yours):** `D:\02_Personal\04_projects\07_crm\backend`
**Companion docs:** [`claude_review_plan.md`](./claude_review_plan.md) · [`upstream_comparison_report.md`](./upstream_comparison_report.md) · [`codex_review_plan.md`](./codex_review_plan.md) · [`updated_original_backend_review.md`](./updated_original_backend_review.md)

---

## 0. Read this first — what "combining" actually means here

I measured the delta between the two codebases before writing this plan. The result changes the strategy:

**Only 18 Python files exist in your fork but not upstream — and 16 of them are files upstream deliberately deleted or restructured:**

| Fork-only file | Why it's not in upstream |
|---|---|
| `common/views.py` | became the `common/views/` **package** |
| `leads/views.py`, `opportunity/views.py`, `tasks/views.py` | became `views/` **packages** |
| `common/token_generator.py` | deleted (was the file with the IndentationError) |
| `invoices/forms.py`, `invoices/serializers.py` | deleted as dead code |
| `accounts/tests.py`, `common/tests.py`, `contacts/tests.py`, `leads/tests.py`, `opportunity/tests.py`, `tasks/tests.py`, `invoices/tests.py` | replaced by per-app `tests/` directories |
| `main.py` | scaffolding placeholder |

**Genuinely unique to you — the entire port-back list:**
1. `common/management/commands/migrate_from_prisma.py` — your Prisma ETL command (upstream has no equivalent)
2. `common/templatetags/common_tags.py` — document file-type helpers (upstream has no `templatetags/` at all)
3. **226 `[??]` / `[!!]` review annotations** across your code — valuable *knowledge*, but not code to carry over

**Therefore: this is an adoption, not a merge.** Your fork is an older upstream snapshot that you re-typed and annotated; it contains essentially no unique product code. Attempting a literal `git merge` of two unrelated histories with identical file paths would produce thousands of meaningless conflicts for zero benefit.

**The strategy is: make upstream the new contents of `backend/` in *your* repo, port back the 2 unique files, then apply the fixes.** Your repository, your history, your remote — upstream's code.

> **If you disagree** and want specific fork behaviour preserved, do Phase 0 Step 3 carefully and tell me what to keep — everything else in this plan still applies.

### Effort estimate

| Phase | What | Effort |
|---|---|---|
| 0–2 | Prepare, adopt, get running | 0.5–1 day |
| 3 | **Security blockers (7 items)** | 1–2 days |
| 4 | Correctness fixes (8 items) | 2–3 days |
| 5–6 | Port-back + test reconciliation | 1–2 days |
| 7 | Data migration (if needed) | 1–3 days |
| 8 | Frontend decision | varies |
| 9–10 | Sync workflow + prod readiness | 1 day |

**Do not skip Phase 3.** Everything before it is mechanical; Phase 3 is what makes the result safe to point at real data.

---

## Phase 0 — Prepare and preserve

**Goal:** nothing is lost, and you can always get back.

### Step 0.1 — Tag your current state

```bash
cd D:/02_Personal/04_projects/07_crm
git status                      # confirm what's uncommitted
git add -A
git commit -m "chore: snapshot before upstream adoption"
git tag pre-upstream-adoption
```

This tag is your rollback point for the whole exercise.

### Step 0.2 — Capture your review annotations before they're overwritten

Your 226 `[??]`/`[!!]` markers are real analysis. Extract them to a file so the knowledge survives:

```bash
cd D:/02_Personal/04_projects/07_crm
grep -rn "\[??\]\|\[!!\]" --include=*.py backend > fork_review_annotations.txt
git add fork_review_annotations.txt
git commit -m "docs: preserve fork review annotations before adoption"
```

Then, as you work through Phases 3–4, check whether any annotation describes a bug that still exists upstream. Several will — they're the same lineage.

### Step 0.3 — Confirm the port-back list

Verify nothing else is unique (the list should match §0 above):

```bash
cd D:/02_Personal/04_projects/07_crm/backend
find . -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" | sed 's|^\./||' | sort > /tmp/fork.txt
cd D:/02_Personal/01_OpenSource/03_Applications/DjangoCrm/Django-CRM/backend
find . -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" -not -path "*/migrations/*" | sed 's|^\./||' | sort > /tmp/up.txt
comm -23 /tmp/fork.txt /tmp/up.txt
```

Copy the two keepers somewhere safe:

```bash
mkdir -p D:/02_Personal/04_projects/07_crm/_portback
cp backend/common/management/commands/migrate_from_prisma.py _portback/
cp -r backend/common/templatetags _portback/
```

### Step 0.4 — Decide the data question

Answer before Phase 2:

- **Is there a database with data you must keep?** If it's a throwaway dev DB → fresh migrations, easy path. If there's real data (or a Prisma source you already imported) → Phase 7 applies and you must not run destructive commands.
- **Note:** your fork has *zero* migrations, so its schema was never formally defined. Any existing DB was created ad-hoc and will almost certainly not match upstream's 100+ migrations. Assume a fresh database unless you have a specific reason not to.

### Step 0.5 — Install prerequisites

Upstream requires more than your fork did:

- **Python ≥3.12** (upstream `requires-python = ">=3.12"`; your fork was 3.11)
- **[uv](https://docs.astral.sh/uv/)** — upstream is uv-managed (`uv.lock`), not `requirements.txt`
- **PostgreSQL** + **Redis**
- **WeasyPrint system libs** (for invoice PDFs) — on Windows follow the [WeasyPrint Windows guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows). Skipping this is fine; PDF download degrades to "unavailable".

**Exit criteria:** tagged snapshot exists; annotations extracted; port-back files copied; data decision made; toolchain installed.

---

## Phase 1 — Adopt the upstream backend

**Goal:** `backend/` in your repo contains upstream's code, on a branch, in one reviewable commit.

### Step 1.1 — Add upstream as a git remote

Do this even though you're copying files — it makes Phase 9 (staying in sync) possible.

```bash
cd D:/02_Personal/04_projects/07_crm
git remote add upstream https://github.com/MicroPyramid/Django-CRM.git
git fetch upstream
git remote -v          # origin = yours, upstream = MicroPyramid
```

### Step 1.2 — Create the adoption branch

```bash
git checkout -b adopt-upstream
```

### Step 1.3 — Replace `backend/` with upstream's

```bash
cd D:/02_Personal/04_projects/07_crm
rm -rf backend
cp -r "D:/02_Personal/01_OpenSource/03_Applications/DjangoCrm/Django-CRM/backend" backend
```

Then **remove artifacts that must not be committed** — upstream's checkout has runtime junk in it:

```bash
cd backend
rm -rf .venv __pycache__ **/__pycache__
rm -f dump.rdb server.log security_audit.log .env
find . -name "*.pyc" -delete
```

> ⚠️ **Delete `backend/.env`.** Upstream's checked-in `.env` contains their local values including `DBUSER="postgres"` — the superuser that defeats RLS. You'll create your own from `.env.example` in Phase 2.

### Step 1.4 — Verify your repo's own files survived

The review docs live at repo root, not in `backend/`, so they're untouched. Confirm:

```bash
cd D:/02_Personal/04_projects/07_crm
ls *.md          # claude_review_plan, codex_review_plan, upstream_comparison_report,
                 # updated_original_backend_review, upstream_adoption_plan, fork_review_annotations
```

### Step 1.5 — Update `.gitignore`

Make sure it covers upstream's artifacts:

```gitignore
.venv/
__pycache__/
*.pyc
.env
*.log
dump.rdb
htmlcov/
coverage.xml
.coverage
staticfiles/
media/
```

### Step 1.6 — Commit as one clearly-labelled change

```bash
git add -A
git commit -m "feat: adopt upstream Django-CRM backend

Replaces the partially-refactored fork snapshot with upstream MicroPyramid/
Django-CRM backend (Django 6, 11 apps, full migrations, 2024 tests).

Rationale: fork did not boot (manage.py check failed), had zero migrations,
and no auth/org HTTP surface. See upstream_comparison_report.md.

Port-backs and security fixes follow in subsequent commits."
```

**Exit criteria:** `backend/` is upstream's code; no `.env`/`.venv`/logs committed; single adoption commit on `adopt-upstream`.

---

## Phase 2 — Get it running and establish a baseline

**Goal:** it boots, migrates, serves, and you know exactly which tests pass *before* you change anything.

### Step 2.1 — Create the database with a **non-superuser** role

This is a security fix, not just setup — RLS is bypassed entirely by superusers.

```sql
CREATE DATABASE bottlecrm;
CREATE USER crm_app WITH PASSWORD 'choose_a_strong_password';
GRANT CONNECT ON DATABASE bottlecrm TO crm_app;
\c bottlecrm
GRANT USAGE ON SCHEMA public TO crm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO crm_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO crm_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO crm_app;
```

> Migrations may need elevated rights to create RLS policies. If `migrate` fails on permissions, run migrations as the owner, then have the **app** connect as `crm_app`.

### Step 2.2 — Create your `.env`

```bash
cd backend
cp .env.example .env
```

Edit it — the important lines:

```env
SECRET_KEY=<generate a real one>
ENV_TYPE=dev
DEBUG=True

DBNAME=bottlecrm
DBUSER=crm_app                 # ← NOT postgres
DBPASSWORD=choose_a_strong_password
DBHOST=localhost
DBPORT=5432

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DOMAIN_NAME=http://localhost:8000
SWAGGER_ROOT_URL=http://localhost:8000
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Step 2.3 — Install and migrate

```bash
cd backend
uv sync
uv run python manage.py check
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

### Step 2.4 — Verify RLS is actually active

```bash
uv run python manage.py manage_rls --verify-user   # must confirm non-superuser
uv run python manage.py manage_rls --status
uv run python manage.py manage_rls --test
```

If `--verify-user` warns you're a superuser, **stop and fix it** — every RLS guarantee is void otherwise.

### Step 2.5 — Run and record the baseline test result

```bash
uv run pytest -q 2>&1 | tail -30 > ../baseline_tests.txt
```

**This file matters.** Phase 4 will make some currently-passing tests fail *on purpose* (they pin bugs). You need the before-picture to tell intentional breakage from regressions.

### Step 2.6 — Smoke-test the server

```bash
uv run python manage.py runserver
```

Check `http://localhost:8000/swagger-ui/` and `http://localhost:8000/admin/`.

**Exit criteria:** `check` passes, migrations applied, RLS verified non-superuser, baseline test results saved, server serves Swagger.

---

## Phase 3 — Security hardening (BLOCKERS)

**Goal:** close the seven issues that make upstream unsafe to point at real data. **Do not skip. Do not defer.**

Work on a branch, one commit per fix, and add a regression test for each.

```bash
git checkout -b security-hardening
```

### 3.1 🔴 Close the privilege-escalation chain

*Any `role="USER"` member can read `api_key` and replay it to become org admin.*

**Fix A — stop serializing the key.** `common/serializer.py:96`:

```python
# BEFORE
class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Org
        fields = ("id", "name", "api_key")     # ← leaks the credential

# AFTER
class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Org
        fields = ("id", "name")

class OrganizationAdminSerializer(serializers.ModelSerializer):
    """Admin-only. Never use on a non-admin-gated endpoint."""
    class Meta:
        model = Org
        fields = ("id", "name", "api_key")
```

Then grep every use and confirm none of the non-admin paths switched to the admin serializer:
```bash
grep -rn "OrganizationSerializer" --include=*.py backend/
```

**Fix B — add the missing role check.** `common/views/organization_views.py:215`, `OrgUpdateView.get` — its own docstring says "Only organization admins", but only `put`/`patch` enforce it:

```python
def get(self, request, pk, format=None):
    if not request.profile:
        return Response({"error": True, "errors": "Organization context required"},
                        status=status.HTTP_400_BAD_REQUEST)
    if str(request.profile.org.id) != str(pk):
        return Response({"error": True, "errors": "Cannot access a different organization"},
                        status=status.HTTP_403_FORBIDDEN)
    # ADD THIS — mirror the check that put/patch already perform
    if not (request.profile.role == "ADMIN" or request.profile.is_admin):
        return Response({"error": True, "errors": "Admin access required"},
                        status=status.HTTP_403_FORBIDDEN)
    ...
```

**Regression test:** a `USER`-role member calling `GET /api/org/<their-org-id>/` must not receive `api_key` in the response body.

### 3.2 🔴 Retire the org API-key authentication path

The key authenticates as an *arbitrary admin*. PAT (`common/pat_auth.py`) already does this job correctly — hashed, shown once, scoped to the owning profile.

**Remove the authenticator** — `crm/settings.py:251`:
```python
"DEFAULT_AUTHENTICATION_CLASSES": (
    "common.pat_auth.PATAuthentication",
    "rest_framework_simplejwt.authentication.JWTAuthentication",
    # "common.external_auth.APIKeyAuthentication",   ← DELETE
),
```

**Remove the duplicate in middleware** — `common/middleware/get_company.py:161-166` repeats the same admin-impersonation logic; delete that branch too.

**Migrate the one legitimate consumer:** the public lead-capture webhook (`CreateLeadFromSite`) uses `APISettings.apikey`, which is a *different* key from `Org.api_key` — verify which your integrations use before removing anything. If something genuinely needs machine auth, issue it a PAT.

**Regression test:** a request carrying `Token: <org.api_key>` must be rejected, not authenticated as admin.

### 3.3 🔴 Confirm the database role is not a superuser

Already done in Phase 2, but make it enforced rather than remembered:

- Add `manage_rls --verify-user` to your deploy/CI pipeline as a gate.
- Never ship an `.env` with `DBUSER=postgres`.

### 3.4 🔴 Fix the six attachment-delete IDORs

Same bug in six files — an org-A admin passes their *own* role check and deletes an **org-B** attachment.

Sites: `accounts/views.py:874` · `contacts/views.py:888` · `leads/views/lead_interactions.py:204` · `opportunity/views/opportunity_interactions.py:158` · `cases/views.py:1105` · `tasks/views/task_views.py:955`

`invoices/api_views.py:1796` already does it right — copy that:

```python
# BEFORE
def delete(self, request, pk, format=None):
    self.object = self.model.objects.get(pk=pk)            # no org filter, 500s on miss
    if (request.profile.role == "ADMIN" or request.profile.is_admin
        or request.profile == self.object.created_by):      # also the C5 bug

# AFTER
def delete(self, request, pk, format=None):
    self.object = get_object_or_404(
        self.model, pk=pk, org=request.profile.org          # ← org scope + proper 404
    )
    if (request.profile.role == "ADMIN" or request.profile.is_admin
        or self.object.created_by_id == request.profile.user_id):   # ← C5 fix
```

**Regression test (write once, parametrise over all six):** a user in org A attempting to delete an attachment owned by org B gets 404, and the row still exists.

### 3.5 🔴 Add project-level default permissions

`crm/settings.py`, inside `REST_FRAMEWORK`:

```python
"DEFAULT_PERMISSION_CLASSES": (
    "rest_framework.permissions.IsAuthenticated",
    "common.permissions.HasOrgContext",
),
```

Then explicitly opt out the genuinely public endpoints with `permission_classes = []` / `AllowAny`:
- `invoices/public_views.py` (client portal)
- `cases/csat_views.py` (public CSAT)
- `cases/inbound_views.py` (SNS webhook)
- `leads` public capture endpoint
- health check / schema

Run the full suite after this — it will surface anything that was implicitly relying on `AllowAny`.

### 3.6 🔴 Remove wildcard CORS from production settings

`crm/server_settings.py:27` unconditionally sets `CORS_ORIGIN_ALLOW_ALL = True`, and `crm/settings.py:148` star-imports it when `ENV_TYPE == "prod"` — silently re-opening in production the exact setting the main file made env-driven.

```python
# crm/server_settings.py — DELETE
CORS_ORIGIN_ALLOW_ALL = True
```

Rely on env `CORS_ALLOWED_ORIGINS`, and fail startup in prod if it's empty:

```python
if ENV_TYPE == "prod" and not CORS_ALLOWED_ORIGINS:
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must be set in production")
```

While here, audit the rest of `server_settings.py` for other overrides that undo hardening.

### 3.7 🔴 Make JWT refresh rotation real (or stop claiming it)

`settings.py:333-334` sets `ROTATE_REFRESH_TOKENS: True` and `BLACKLIST_AFTER_ROTATION: True`, but `token_blacklist` isn't installed and nothing blacklists. A stolen refresh token stays valid its full 14 days.

**Option A (recommended):**
```python
INSTALLED_APPS = [..., "rest_framework_simplejwt.token_blacklist"]
```
```bash
uv run python manage.py migrate
```
Then update `OrgAwareTokenRefreshView` (`common/views/auth_views.py:320-379`) to blacklist the presented token before issuing the new pair.

**Option B (only if A is deferred):** remove the two settings and document that refresh tokens are valid until expiry — don't ship a setting implying protection it doesn't give.

**Exit criteria for Phase 3:** all seven fixed, each with a regression test, full suite run and diffs understood.

---

## Phase 4 — Correctness fixes

**Goal:** eliminate the inherited bugs both codebases share.

```bash
git checkout -b correctness-fixes
```

### 4.1 The ~34 `created_by` vs `Profile` comparisons

`created_by` is an FK to `common.User`; comparing it to `request.profile` (a `Profile`) is always False, so ownership checks silently fail — and some sites hard-crash on `created_by.user`.

**Don't do 34 inline edits.** Add one helper and use it everywhere:

```python
# common/permissions.py
def is_creator(profile, obj) -> bool:
    """created_by is a User FK; profile is a Profile. Compare correctly."""
    return bool(profile and getattr(obj, "created_by_id", None) == profile.user_id)


def can_modify(profile, obj) -> bool:
    """Standard object-level rule: org admin, or the creator."""
    return bool(profile) and (
        profile.role == "ADMIN" or profile.is_admin or is_creator(profile, obj)
    )
```

Find them all:
```bash
grep -rn "profile == .*created_by\|profile != .*created_by" --include=*.py backend/
```

Sites by app: `accounts/views.py:299,465,478,490,586,653,878` · `contacts/views.py:291,436,460,465,572,649,892` · `opportunity/views/opportunity_views.py:367,580,594,606,683,776` + `opportunity_interactions.py:162` + `kanban_views.py:162` · `tasks/views/task_views.py:283,315,405,482,634,797,959` · `invoices/api_views.py:255,551,605,832,1298,1804` · `cases/views.py:645,1109` · `common/views/document_views.py:227,281,326,420`

**Also fix the crash sites** — e.g. `tasks/views/task_views.py:315-316` does `self.task_obj.created_by.user.email`; `created_by` is already a `User`, so it becomes `created_by.email`.

`leads/views/` is already correct — use it as the reference.

### 4.2 Audit task/service code for the same type confusion

The view-layer grep above **misses these**. Two confirmed:

```python
# leads/tasks.py:159
lead.created_by = profile          # ✗ Profile into a User FK
lead.created_by = profile.user     # ✓

# common/tasks.py:204
if user.has_marketing_access:      # ✗ flag lives on Profile, not User
```

Sweep for the whole class:
```bash
grep -rn "created_by\s*=\s*profile\b\|updated_by\s*=\s*profile\b" --include=*.py backend/
grep -rn "user\.has_.*_access\|\.user\.role" --include=*.py backend/
```

### 4.3 Finish the generic-comment migration

`accounts/views.py:599` and `contacts/views.py:585` still pass phantom kwargs — the comment is **silently dropped with HTTP 200**. Upstream already fixed this in `opportunity/views/opportunity_views.py:703-709`; copy it:

```python
# BEFORE
comment_serializer.save(account_id=self.account.id, commented_by_id=...)

# AFTER
Comment.objects.create(
    comment=params.get("comment"),
    content_type=ContentType.objects.get_for_model(Account),
    object_id=self.account.id,
    commented_by=request.profile,
    org=request.profile.org,
)
```

**Test that the comment actually persists** — the existing test asserts HTTP 200 without checking persistence, which is how this survived.

### 4.4 Remove the phantom serializer fields

Six declared fields resolve to nothing and are silently omitted, making the documented API a lie: `accounts/serializer.py:30` (`account_attachment`), `contacts/serializer.py:22` (`contact_attachment`), `leads/serializer.py:21,23` (`lead_attachment`, `lead_comments`), `tasks/serializer.py:212,213` (`task_attachment`, `task_comments`).

Either delete them, **or** back them with real relations on the models:

```python
from django.contrib.contenttypes.fields import GenericRelation

class Account(...):
    attachments = GenericRelation("common.Attachments")
    comments = GenericRelation("common.Comment")
```

**Adding `GenericRelation` also fixes an orphaning bug**: without it, deleting a parent record leaves its comments/attachments behind forever. I'd recommend adding it.

### 4.5 Fix the `BaseModel.save()` audit bug

`common/base.py:71-77` — one line, byte-identical to your fork:

```python
if self._state.adding:
    self.created_by = user
    self.updated_by = None
else:                          # ← ADD
    self.updated_by = user     # ← INDENT under else
super().save(*args, **kwargs)
```

### 4.6 Remaining security items

- **Hash magic-link tokens** — `common/views/auth_views.py:537` stores `secrets.token_hex(32)` in plaintext while the sibling OTP is hashed. Store a hash, compare in constant time, keep expiry/single-use.
- **Fix `IsSuperAdmin`** — `common/permissions.py:77` trusts `email.endswith("@micropyramid.com")`. Replace with an explicit `User.is_superuser` / dedicated flag.
- **Exempt `/api/public/`** — `common/middleware/rls_context.py` `EXEMPT_PATHS` lists only `/api/public/csat/`, so the invoice/estimate client portal, `/healthz/` and `/schema/` are 403'd before reaching their `AllowAny` views. Add the whole namespace and test each unauthenticated.
- **Add throttling** — no `DEFAULT_THROTTLE_CLASSES` at all; Google OAuth, token refresh and org enumeration have no IP-level limit.
- **Fix `invoices/api_views.py:1775`** — `created_by=request.profile` into a `User` FK.

### 4.7 Explicit org permissions on the new apps

`business_hours` and `macros` views declare only `IsAuthenticated` and lean on `RequireOrgContext` middleware. Declare it directly so the guarantee doesn't depend on middleware ordering:

```python
permission_classes = (IsAuthenticated, HasOrgContext)
```

### 4.8 Cleanup

- Delete `common/status.py` (62 lines duplicating DRF's `status`, imported nowhere).
- Decide on `invoices/tests_legacy.py` (521 lines) — port or delete.
- Pin invoice rounding with a test — money is `Decimal` now, but `.quantize()` isn't universal.
- Fix the `business_hours` N+1 (`calendar.py:69` bypasses the prefetch) and the racy `_get_or_create_default`.

**Exit criteria:** all items fixed; test diff vs `baseline_tests.txt` fully explained.

---

## Phase 5 — Port back your unique work

### 5.1 `migrate_from_prisma.py`

```bash
cp _portback/migrate_from_prisma.py backend/common/management/commands/
```

⚠️ **It will not run as-is.** It was written against your fork's models, and upstream's schema has changed substantially (new apps, renamed/added fields, RLS). Before using it:

1. Update every model import and field mapping to upstream's models.
2. Replace raw-SQL table writes with ORM calls so validation and RLS apply.
3. Wrap each model's import in `transaction.atomic()`.
4. Call `set_rls_context(org_id)` at the start — it runs outside request middleware.
5. Add a `--dry-run` that reports row counts without writing.
6. Test against a scratch database and compare counts before touching anything real.

### 5.2 `common/templatetags/`

Only port this if something still needs it:

```bash
grep -rn "is_document_file_\|common_tags" --include=*.py backend/
```

If nothing references those helpers, upstream dropped them deliberately — leave them out.

### 5.3 Mine your annotations

Walk `fork_review_annotations.txt`. Many `[??]`/`[!!]` markers describe bugs that **still exist upstream** (same lineage). For each: if it's fixed upstream, discard; if it still applies, open an issue. Don't paste the markers back into upstream code.

---

## Phase 6 — Reconcile the test suite

**Goal:** the suite asserts *desired* behaviour, not current breakage.

### 6.1 Fix the tests that pin bugs

Your Phase 4 fixes will turn these **red — correctly**:

```python
# tasks/tests/test_tasks_api.py:1393
with pytest.raises(AttributeError, match="has no attribute 'user'"):
    user_client.get(f"/api/tasks/{task.id}/")

# contacts/tests/test_contacts_api.py:1066
with pytest.raises(TypeError, match="contact_id"):
```

Rewrite them to assert the correct outcome (200 and a persisted comment). Find others:
```bash
grep -rn "pytest.raises(AttributeError\|pytest.raises(TypeError" --include=*.py backend/
```

### 6.2 Add the missing tenant-isolation tests

The root `conftest.py` already provides `org_a` / `org_b` fixtures. For **every** app add: a user in org A cannot list, read, update, delete, comment on, or attach to org B's records — asserting 404/403 *and* that the row is unchanged.

### 6.3 Add a regression test per security fix

One test each for §3.1, §3.2, §3.4, §3.5, §3.6, §3.7 — so a future upstream merge can't silently reintroduce them.

### 6.4 Compare against baseline

```bash
uv run pytest -q 2>&1 | tail -30 > current_tests.txt
diff baseline_tests.txt current_tests.txt
```

Every difference must be explainable as an intentional fix.

---

## Phase 7 — Data migration (only if you have data to keep)

1. **Never** run against production first. Restore a copy to a scratch DB.
2. Run `migrate` on the scratch DB, confirm all migrations apply cleanly.
3. Run the reworked Prisma command with `--dry-run`; compare row counts per model.
4. Run for real on scratch; spot-check referential integrity and that every row has a correct `org_id`.
5. **Verify tenant isolation on migrated data** — log in as an org-A user and confirm you cannot see org-B rows.
6. Only then plan the real cutover, with a backup and a rollback path.

---

## Phase 8 — The frontend question

**Your existing frontend will almost certainly not work with this backend.** The API changed fundamentally: new auth flows (Google OAuth + magic link, no password login), org context in JWT claims rather than headers, and dozens of new endpoints.

Options, best first:

1. **Adopt upstream's frontend too** — it lives at `Django-CRM/frontend` (SvelteKit) and is built against exactly this API. Given you told me your frontend's maintenance state is unknown, this is the lowest-risk path.
2. **Regenerate a client** from the OpenAPI schema and adapt:
   ```bash
   uv run python manage.py spectacular --file openapi.yml
   ```
3. **Keep yours and port endpoint by endpoint** — most work, only worth it if it has significant custom UI.

Upstream also ships `mobile/` and an optional `mcp_server/` (AI-agent integration) if either is interesting.

---

## Phase 9 — Stay in sync with upstream

Upstream is **actively maintained** (last commit 2026-06-06). This is the difference between a one-time copy and a sustainable base.

### 9.1 Keep your changes identifiable

Keep security/correctness fixes in **small, well-labelled commits**, separate from any feature work. When you pull upstream changes, you'll replay these on top.

### 9.2 Periodic sync

```bash
git fetch upstream
git log --oneline HEAD..upstream/main -- backend/    # what changed
```

Review, then merge or cherry-pick, re-running your regression tests afterwards.

### 9.3 Upstream your fixes — strongly recommended

The security issues in Phase 3 are **upstream's bugs, affecting every user of this project**. Reporting/PR-ing them:
- gets them reviewed and maintained by others,
- **reduces your divergence permanently** (every fix you upstream is one you never re-apply),
- is the right thing to do for an open-source project you're benefiting from.

Report the privilege-escalation chain (§3.1) **privately first** via security contact or a private advisory — not a public issue.

---

## Phase 10 — Production readiness checklist

- [ ] `DEBUG=False`; real `SECRET_KEY` from env (prod guard active)
- [ ] `ALLOWED_HOSTS` explicit; `CORS_ALLOWED_ORIGINS` explicit; **no wildcard CORS anywhere** (incl. `server_settings.py`)
- [ ] `DBUSER` is a non-superuser; `manage_rls --verify-user` passes **in the deploy pipeline**
- [ ] `manage_rls --status` shows policies on all expected tables
- [ ] `DEFAULT_PERMISSION_CLASSES` set; public endpoints explicitly opted out
- [ ] Org API-key auth removed; PATs used for machine access
- [ ] `api_key` absent from all non-admin responses
- [ ] Refresh-token blacklisting working (or rotation settings removed + documented)
- [ ] Throttling configured on unauthenticated endpoints
- [ ] Celery worker **and beat** running (SLA scan, timers, reminders all depend on beat)
- [ ] Redis reachable (notifications SSE + Celery)
- [ ] Full test suite green, differences vs baseline all explained
- [ ] Tenant-isolation tests passing for every app
- [ ] Backups and a tested restore
- [ ] Sentry DSN configured
- [ ] WeasyPrint libs installed (or PDF degradation accepted)

---

## Rollback

At any point:

```bash
git checkout main                 # abandon the adoption branch
# or, to go all the way back:
git reset --hard pre-upstream-adoption
```

Your original fork remains fully recoverable at the `pre-upstream-adoption` tag and on `origin`.

---

## Quick reference — order of operations

```
Phase 0  Tag, extract annotations, copy port-backs, decide data, install uv/PG/Redis
Phase 1  Add upstream remote → branch → replace backend/ → strip .env/.venv/logs → commit
Phase 2  Non-superuser DB → .env → uv sync → migrate → verify RLS → BASELINE TESTS
Phase 3  🔴 SECURITY (7 blockers) ← do not skip
Phase 4  Correctness (~34 created_by, task-layer types, comments, GenericRelation,
         BaseModel.save, magic-link hash, IsSuperAdmin, /api/public/, throttling)
Phase 5  Port back migrate_from_prisma (rework it) + mine annotations
Phase 6  Fix bug-pinning tests, add tenant-isolation + regression tests
Phase 7  Data migration (scratch DB first)
Phase 8  Frontend decision
Phase 9  Upstream remote sync + report security findings upstream
Phase 10 Production checklist
```
