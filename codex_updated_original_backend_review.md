# Updated Original Backend Review

Source reviewed: `D:\02_Personal\01_OpenSource\03_Applications\DjangoCrm\Django-CRM\backend`

Date: 2026-07-23

Compared against: `codex_review_plan.md`

## Verdict

The updated original backend is a major improvement over the earlier snapshot, but it does not solve all problems listed in `codex_review_plan.md`.

The old boot/import blockers are mostly resolved. All main business apps are installed, `common.urls` and `common.views` are real, Celery is wired through the project app, migrations now exist, and `manage.py check --settings=crm.test_settings` passes.

The remaining problems are no longer mostly "project cannot start" problems. They are security-contract, tenant-isolation, audit, and old-refactor-cleanup problems. After reading `upstream_comparison_report.md`, I would classify several of them as production blockers, not just cleanup items:

- Org API keys are still plaintext, still stored on `Org`, still exposed through org serialization, and still authenticate as the first active admin profile in the org.
- Claude's report identifies a worse chain: an ordinary authenticated org user can appear to retrieve `api_key` from the org endpoint, then replay it as `Token <api_key>` and become the first active org admin.
- `REST_FRAMEWORK` still has no project-level `DEFAULT_PERMISSION_CLASSES`.
- `BaseModel.save()` still sets `updated_by` during creation.
- Many object-permission checks still compare `request.profile` to `created_by`, but `created_by` is a `User` FK.
- Generic comment/attachment migration is improved but still incomplete in accounts/contacts, serializer reverse-field naming, and several attachment-delete paths.
- Production settings regress through `crm/server_settings.py`, which sets `CORS_ORIGIN_ALLOW_ALL = True`.
- JWT refresh rotation settings are misleading unless `rest_framework_simplejwt.token_blacklist` is installed and old refresh tokens are actually blacklisted.
- Magic-link OTPs are hashed, but the magic-link token itself is still stored and looked up in plaintext.
- Public invoice/estimate routes under `/api/public/` may be blocked by `RequireOrgContext` because only `/api/public/csat/` is exempted.
- Some tasks/import paths still use old `User` or `Profile` assumptions incorrectly.
- Some upstream tests appear to assert current crashes or error behavior, so test count alone does not mean the behavior is correct.

## Update After Reading `upstream_comparison_report.md`

Claude's comparison agrees with the core Codex verdict: upstream is much healthier than the earlier broken snapshot, but it has not closed the review plan. The useful refinement is severity. The updated original repo fixes most infrastructure problems and adds a lot of product surface, while leaving a smaller set of sharper security and correctness defects.

My opinion after reading it:

- I agree with using upstream as the better base, because it has real migrations, installed apps, RLS plumbing, a much larger test suite, and active implementations for cases, invoices, PATs, custom fields, notifications, business hours, and macros.
- I would not deploy it as-is. The org API-key escalation path, missing DRF default permissions, attachment-delete IDORs, wildcard production CORS setting, and misleading JWT rotation settings are release blockers.
- Claude's report makes the RLS picture stronger than my first pass: RLS appears implemented in code with middleware, policies, context reset, and management verification tooling. The deployment caveat remains important: if the app connects as a PostgreSQL superuser such as `postgres`, RLS can be bypassed.
- The "new apps" are not all equally mature. `business_hours` and `macros` look useful and coherent; `orders` is currently more of a model/admin foundation than a usable API feature.

## Verification Performed

- Inspected project layout, app list, settings, URL wiring, Celery wiring, models, serializers, views, tasks, and new app modules.
- Ran:

```powershell
.\.venv\Scripts\python.exe -B manage.py check --settings=crm.test_settings
```

Result:

```text
System check identified no issues (0 silenced).
```

Notes:

- The first check attempt failed only because the sandbox could not write `server.log` in the external source checkout. After allowing the check command against that path, Django's system check passed.
- Read `upstream_comparison_report.md` and folded its upstream-vs-fork findings into this report.
- Cross-checked several high-impact Claude findings: `crm/server_settings.py` sets `CORS_ORIGIN_ALLOW_ALL = True`; SimpleJWT refresh rotation/blacklist settings are present while `rest_framework_simplejwt.token_blacklist` is not installed; magic-link OTPs are hashed but magic-link tokens are stored plaintext; `RequireOrgContext.EXEMPT_PATHS` does not exempt `/api/public/`, `/healthz/`, or `/schema/`.
- I did not run the full pytest suite. My filesystem count found 93 `test_*.py` files. Claude's app-focused count reports 73 test files and 2,024 test functions, which is still a major improvement over the earlier fork. This review is static plus Django system check.

## Snapshot Of The Updated Backend

- Python files reviewed, excluding `.venv`: 426.
- Installed Django apps with `apps.py`: `accounts`, `business_hours`, `cases`, `common`, `contacts`, `invoices`, `leads`, `macros`, `opportunity`, `orders`, `tasks`.
- Migrations now exist:

| App | Migration files |
|---|---:|
| `accounts` | 7 |
| `business_hours` | 1 |
| `cases` | 23 |
| `common` | 27 |
| `contacts` | 12 |
| `invoices` | 9 |
| `leads` | 13 |
| `macros` | 1 |
| `opportunity` | 11 |
| `orders` | 3 |
| `tasks` | 11 |

Claude's comparison adds useful scale context: excluding migrations, it counted the reviewed upstream at about 79,599 lines of app code versus about 17,743 lines in the local fork, with 297 Python files versus 128. That matches what I saw qualitatively: this is not a small patch over the old snapshot; upstream has become a substantially larger product.

## Comparison Against `codex_review_plan.md`

| Old issue | Updated status | Evidence / opinion |
|---|---|---|
| URLConf includes disabled apps | Resolved | `crm/settings.py` installs the business apps and `common/app_urls/__init__.py` includes them consistently. |
| `common.urls` and `common.views` missing | Resolved | `common/urls.py` now exposes auth, profile, org, users, teams, docs, tags, notifications, custom fields, PATs, and dashboard endpoints. `common/views/` now contains real view modules. |
| Project does not import | Mostly resolved | `manage.py check --settings=crm.test_settings` passes. |
| Migrations missing | Resolved | All installed apps now have migration history. |
| Celery disconnected | Resolved | `crm/__init__.py` exports `celery_app`; task modules use `@shared_task`; `crm/celery.py` autodiscovers `tasks` and `celery_tasks`. |
| Development-open settings | Partially resolved, with regression | Main settings are more env-driven, but `crm/server_settings.py` sets `CORS_ORIGIN_ALLOW_ALL = True`. JWT refresh rotation is configured, but blacklist support is not installed, so the security claim is incomplete. |
| No default DRF permissions | Not resolved | `REST_FRAMEWORK` defines authentication, pagination, and schema, but no `DEFAULT_PERMISSION_CLASSES`. Many views set permissions manually, and `RequireOrgContext` helps, but there is no fail-closed DRF default. |
| API key admin impersonation | Not resolved, critical | `common.external_auth.APIKeyAuthentication` and `GetProfileAndOrg._process_api_key_auth()` still resolve `Org.objects.get(api_key=...)`, then use the first active `role="ADMIN"` profile. Claude also found the org endpoint can expose this key to an ordinary org user. |
| API key exposed in serialization | Not resolved, critical | `OrganizationSerializer` still has `fields = ("id", "name", "api_key")`; org responses serialize it. In combination with API-key auth, this becomes privilege escalation. |
| API keys plaintext | Not resolved | `Org.api_key` is still a `TextField` with unique plaintext values. The new PAT model is hashed, but it does not replace org API keys. |
| JWT refresh rotation | Not resolved | `ROTATE_REFRESH_TOKENS` and `BLACKLIST_AFTER_ROTATION` are enabled, but the blacklist app is absent and the custom refresh flow does not blacklist the old token. |
| `BaseModel.save()` audit bug | Not resolved | `common/base.py` still sets `self.updated_by = user` immediately after the create branch, so new rows get `updated_by` too. |
| `User`/`Profile` drift | Partially resolved | Many list filters now use `created_by=request.profile.user`, but active code still has many comparisons like `request.profile == obj.created_by`. My broader scan found 34; Claude's curated count found 31. `created_by` is a `User` FK. |
| Phantom `User` fields | Mostly resolved, not fully | `User` now has `name`, but `common/tasks.py` still reads `user.has_marketing_access`, which lives on `Profile`. |
| Generic comments/attachments | Partially resolved | Most active flows now use `ContentType`/`object_id`; accounts and contacts still have old `comment_serializer.save(account_id=...)` and `comment_serializer.save(contact_id=...)` paths. Claude also found attachment-delete IDORs across several apps. |
| Cross-org filtering | Improved but incomplete | Most new code filters by `request.profile.org`; middleware and RLS context are enabled. Request-level IDORs still exist where objects are fetched or deleted by `pk` without org scoping. |
| Duplicated permission logic | Not resolved | Apps still hand-roll admin/creator/assignee checks. This is better than before in places, but not centralized. |
| Business logic in views | Not resolved | Some workflows moved to services, but view files are still large and process assignment, tags, comments, attachments, CSV imports, invoice actions, and workflow transitions directly. |
| Invoice duplicate serializers | Resolved | Updated invoice app uses `serializer.py`; the unused `serializers.py` module from the earlier snapshot is gone. |
| Invoice float money bug | Mostly resolved | I did not find the old `float(...)` calculations in `invoices/api_views.py`; invoice math now uses `Decimal` fields and line items. Some calculations still do not explicitly `quantize()`, so rounding policy should be tested. |
| Invoice malformed `Response()` calls | Appears resolved | Targeted search did not find the old `Response({"error": True}, data)` form. |
| Invoice Celery argument order | Resolved for the checked path | `send_email.delay(str(invoice.id), [profile_ids], org_id, ...)` now matches `send_email(invoice_id, recipients, org_id, ...)`. |
| RLS half-integrated | Fixed in code, deployment caveat | Claude verified middleware registration, `set_config`, migrations, fail-safe predicates, context reset, and management verification tooling. The caveat is deployment: using `DBUSER=postgres` or another bypassing role can defeat RLS. |
| Public invoice/estimate routes | New blocker | Public routes are mounted under `/api/public/`, but org-context middleware appears to exempt only `/api/public/csat/`. The client portal can be blocked unless `/api/public/` is explicitly exempted or handled separately. |
| Magic-link storage | New concern | OTP hashes are stored safely, but the URL token is stored and queried in plaintext. Treat it like a credential and store only a hash. |
| Test suite | Much improved, still not proof | Upstream has a large test suite; Claude counted 2,024 test functions. Some tests reportedly assert current crashes or error behavior, so test volume does not close the remaining review findings. |

## Highest Risk Findings In The Updated Code

### 1. Ordinary Users Can Escalate Through Org API Keys

The old API-key design is still present:

- `Org.api_key` is plaintext.
- `OrganizationSerializer` returns it.
- `APIKeyAuthentication` maps the key to the first active admin profile.
- `GetProfileAndOrg` repeats the same behavior for middleware org context.

Claude's report adds the critical exploit chain: `OrgUpdateView.get` is reachable by an authenticated org user, returns `OrganizationSerializer(org).data`, and that serializer includes `api_key`. The user can then send the key as `Token <api_key>`. The API-key authenticator does not authenticate the user who fetched the key; it authenticates as the first active admin in the org.

The new `PersonalAccessToken` model is a good direction: it hashes tokens, shows the raw token once, scopes to a profile/org, supports revocation/expiry, and has tests. But it coexists with the unsafe org API-key path instead of replacing it. Claude also notes that PAT scopes exist but are not yet consistently enforced.

Recommended fix:

- Stop using `Org.api_key` for general API auth.
- Remove `api_key` from normal org serializers immediately.
- Gate any key-management endpoint behind explicit org-admin permission.
- Migrate integrations to `PersonalAccessToken` or a separate hashed `IntegrationAPIKey` model with explicit scopes.
- Do not impersonate arbitrary admins.

### 2. No Project-Level Default Permissions

`REST_FRAMEWORK` still omits `DEFAULT_PERMISSION_CLASSES`. The code partially compensates with explicit `permission_classes` and `RequireOrgContext` middleware, but this is still not a strong default.

Recommended fix:

```python
"DEFAULT_PERMISSION_CLASSES": (
    "rest_framework.permissions.IsAuthenticated",
    "common.permissions.HasOrgContext",
)
```

Then explicitly opt out public endpoints with `AllowAny` or `permission_classes = []`.

### 3. `BaseModel.save()` Still Writes `updated_by` On Create

Current logic still does:

```python
if self._state.adding:
    self.created_by = user
    self.updated_by = None
self.updated_by = user
```

That defeats the intended create/update audit split.

Recommended fix:

```python
if self._state.adding:
    self.created_by = user
    self.updated_by = None
else:
    self.updated_by = user
```

### 4. Owner Checks Still Compare `Profile` To `User`

Static scans found many active-code owner checks like this. My broader regex found 34; Claude's curated active-code count found 31:

- `self.request.profile == self.account.created_by`
- `request.profile == invoice.created_by`
- `request.profile == self.object.created_by`

`created_by` comes from `UserAuditModel` and is a `common.User` FK. These checks should compare `request.profile.user` to `created_by`, or object permissions should be centralized.

Recommended fix:

- Replace direct comparisons with a shared helper:

```python
def is_creator(profile, obj):
    return bool(profile and obj.created_by_id == profile.user_id)
```

- Better: replace all inline checks with a single object permission class.

### 5. Generic Comment Creation Is Still Not Fully Migrated

The updated code is much closer to the intended `ContentType`/`object_id` design, but old save calls remain:

- `accounts/views.py`: `comment_serializer.save(account_id=...)`
- `contacts/views.py`: `comment_serializer.save(contact_id=...)`

Those do not match the generic `Comment` model. Several app serializers also still expose historical names such as `account_attachment`, `contact_attachment`, `lead_comments`, and `task_attachment`. If no `GenericRelation` fields exist on target models, these serializer fields are still fragile.

Recommended fix:

- Add one shared interaction service for comments/attachments.
- Use it from every app.
- Either add explicit `GenericRelation` fields with those related query names or stop exposing old reverse names in serializers.

### 6. Residual Task And Import Bugs

Examples:

- `common/tasks.py` still checks `user.has_marketing_access`, but that flag is on `Profile`.
- `leads/tasks.py` sets `lead.created_by = profile`, but `created_by` expects `User`.

Recommended fix:

- Run a targeted audit for `created_by=profile`, `updated_by=profile`, and `user.has_*_access`.
- Add Celery eager tests for these paths.

### 7. Attachment Delete IDORs Still Exist

Claude's report identifies attachment-delete IDORs in multiple apps: `accounts`, `contacts`, `leads/lead_interactions`, `opportunity/opportunity_interactions`, `cases`, and `tasks`. The pattern is the same old risk: delete by attachment id without scoping the lookup through the parent object and current org.

Recommended fix:

- For every attachment/comment mutation, resolve the parent object through `org=request.profile.org` first.
- Resolve the attachment through both `content_type/object_id` and org-scoped parent ownership.
- Add negative tests where a user from org A tries to delete an attachment belonging to org B.

### 8. JWT Refresh Rotation Settings Are Misleading

Settings enable refresh-token rotation and blacklist-after-rotation, but `rest_framework_simplejwt.token_blacklist` is not installed. The custom refresh view issues a new token without blacklisting the old refresh token.

Recommended fix:

- Install and migrate SimpleJWT's blacklist app, then blacklist the old refresh token during refresh; or
- Disable the rotation/blacklist settings and document that refresh tokens remain valid until expiry.

The first option is the right production direction.

### 9. Magic-Link Tokens Are Stored Plaintext

The OTP/code path uses `make_password`, which is good. The magic-link token itself is still generated with `secrets.token_hex(32)`, stored in the database, and queried by plaintext value.

Recommended fix:

- Store a hash of the magic-link token.
- Compare candidate tokens with a constant-time hash check.
- Keep expiry and one-time-use behavior.

### 10. Public Client Portal May Be Blocked By Org Middleware

Public invoice/estimate URLs are mounted under `/api/public/`, but `RequireOrgContext.EXEMPT_PATHS` appears to exempt `/api/public/csat/` only. That means public invoice or estimate links can be rejected before they reach their intended `AllowAny` views.

Recommended fix:

- Exempt the full intended public namespace, or split public routes into a middleware-safe path.
- Add integration tests for public invoice, public estimate, CSAT, `/healthz/`, and `/schema/` without auth headers.

### 11. Production CORS Reopens In `server_settings.py`

Main settings are more environment-driven, but `crm/server_settings.py` sets `CORS_ORIGIN_ALLOW_ALL = True` while `DEBUG = False`. That reintroduces a production wildcard CORS posture.

Recommended fix:

- Remove `CORS_ORIGIN_ALLOW_ALL = True` from production settings.
- Use explicit `CORS_ALLOWED_ORIGINS` from environment.
- Fail startup if production origins are missing.

### 12. Secondary Security Concerns From Claude's Report

These are not all as severe as the org API-key escalation, but they should be fixed before calling the backend production-ready:

- `IsSuperAdmin` trusts a hardcoded `@micropyramid.com` email suffix.
- Bad API keys raised from middleware may bypass DRF's normal exception handling and become 500s.
- No project-level throttling defaults are configured.
- Some tests appear to pin crashes or current broken behavior instead of documenting the desired behavior.

## What The New Apps Do

### `business_hours`

Purpose: per-org working calendar support, mainly for SLA and due-time calculations.

Main models:

- `BusinessCalendar`: org-owned calendar with IANA timezone and open/close times for each weekday.
- `BusinessHoliday`: full-day holidays tied to a calendar.

Main endpoints under `/api/business-hours/`:

- `GET /calendar/`: return or create the org default calendar.
- `PUT /calendar/<pk>/`: admin update calendar hours/timezone.
- `POST /calendar/<pk>/holidays/`: admin add holiday.
- `DELETE /calendar/<pk>/holidays/<hid>/`: admin delete holiday.

Important helper:

- `business_hours.calendar.add_business_hours(start_dt, hours, calendar)` walks forward through working windows and skips holidays.

Review note: useful and coherent. It uses `IsAuthenticated` only, but global `RequireOrgContext` currently protects the route for normal requests. I would still add `HasOrgContext` directly. Claude also notes two implementation concerns worth fixing: the calendar helper can create N+1 holiday queries if prefetching is bypassed, and default-calendar creation may race on first use unless protected by a transaction or retry around the unique constraint.

### `macros`

Purpose: canned response templates for support cases.

Main model:

- `Macro`: org or personal scope, title/body, owner, active flag, usage count, and database constraints around scope ownership.

Main endpoints under `/api/macros/`:

- `GET /`: list visible org macros and the user's own personal macros.
- `POST /`: create macro; non-admins are forced to personal scope.
- `GET/PUT/PATCH/DELETE /<id>/`: manage visible/writable macro.
- `POST /<id>/render/`: render placeholders against a case and increment usage.

Supported placeholders include:

- `%customer_name%`
- `%customer_email%`
- `%case_id%`
- `%case_subject%`
- `%agent_name%`
- `%agent_email%`
- `%org_name%`

Review note: well scoped and practical. Like `business_hours`, it should declare `HasOrgContext` directly instead of relying only on middleware. Claude's main concerns are smaller: `GET` on another user's personal macro returns 404 while `PATCH`/`DELETE` can reveal existence through 403, and rendering is currently hard-coupled to cases rather than a generic templating target.

### `orders`

Purpose: sales order data model linked to CRM records.

Main models:

- `Order`: org-scoped sales order linked to `Account`, optional `Contact`, and optional `Opportunity`; includes status, order number, billing/shipping addresses, and financial summary fields.
- `OrderLineItem`: org-scoped order line item linked to `Order` and optional `invoices.Product`; computes line total from quantity, unit price, and discount.

Review note: this is currently model/admin/test-only. It is installed and migrated, but I did not find `orders.urls`, serializers, or API views. Claude's report reaches the same conclusion and adds that important domain behavior is not finished yet: order header totals are not recomputed from line items, order number generation/uniqueness is incomplete, status transitions are not validated, and there is no order-to-invoice workflow. Treat `orders` as a foundation, not a completed module.

## Updated Existing App Inventory

### `common`

Now owns the real platform surface: auth, Google OAuth, magic links, org switching, profiles, users, teams, tags, documents, API settings, org settings, dashboard, activity feed, notifications, custom fields, PATs, audit log, and RLS context.

Strong improvements:

- `common.views` is restored.
- `PersonalAccessToken` is hashed and one-time-display.
- Notifications and custom fields are now real features.
- Middleware for org context and RLS is enabled, and Claude's report verifies the RLS code path more deeply than my first pass did.

Remaining concern:

- Unsafe org API-key path still exists beside the better PAT implementation and can become an ordinary-user-to-admin escalation.
- PAT scopes exist, but should be audited for consistent enforcement.
- Magic-link tokens are plaintext even though OTPs are hashed.
- `IsSuperAdmin` trusts a hardcoded email suffix.
- Public-route exemptions in `RequireOrgContext` are incomplete.

### `accounts`

Account CRUD, assignment/team/tag handling, account emails, comments, attachments, custom fields, and tests.

Improved:

- App is installed and migrated.
- List filtering mostly uses `request.profile.org`.
- Tests cover core API paths.

Remaining concern:

- Some owner checks still compare `Profile` to `User.created_by`.
- Account comment creation still has an old `account_id=` save path.
- Attachment delete should be reworked to scope through the account and org.

### `contacts`

Contact CRUD, assignment/team/tag handling, optional account relation, CSV import preview/commit, comments, attachments, custom fields, and tests.

Improved:

- Contact/account relation is explicit.
- CSV import is two-phase and org-scoped.
- Tests cover many API paths.

Remaining concern:

- Some detail/comment paths still fetch before org filtering or compare `Profile` to `created_by`.
- Contact comment creation still has an old `contact_id=` save path.
- Claude also flags a detail `POST` path and attachment delete as request-level IDOR risks.

### `leads`

Lead CRUD, lead conversion, lead pipelines/stages, kanban movement, CSV upload/import, comments, attachments, assignment notifications, custom fields, and tests.

Improved:

- The old `leads.Company` model appears removed; lead/account conversion moved partly into services.
- Lead kanban is now a real feature.

Remaining concern:

- `leads/tasks.py` still has a `created_by = profile` assignment into a `User` FK.
- Some conversion/workflow logic remains split across views and services.
- Attachment delete should be checked against the generic parent object and org before deletion.

### `opportunity`

Opportunity CRUD, line items, kanban, stage aging/rotten deal tracking, sales goals, leaderboard, comments, attachments, custom fields, and scheduled tasks.

Improved:

- Opportunity line items and sales goals are real features.
- Celery tasks use `@shared_task`.

Remaining concern:

- Multiple owner checks still compare `Profile` to `created_by`.
- Attachment delete should be scoped by org and parent object.

### `tasks`

CRM task CRUD plus task pipelines/stages, task kanban, board/column/card functionality, related links to account/contact/opportunity/case/lead, comments, attachments, custom fields, and tests.

Improved:

- The old board app seems merged into `tasks`.
- `crm/celery.py` explicitly autodiscovers `celery_tasks`.
- The previous `BoardMember` constraint issue appears addressed in migrations/models.

Remaining concern:

- Several owner checks still compare `Profile` to `created_by`.
- Task serializers still expose `task_attachment` and `task_comments`, so the generic relation contract should be verified.
- Attachment delete should be scoped by org and parent object.

### `cases`

Large support/service app. It now looks closer to a helpdesk/ITSM module than a simple CRM case tracker. It includes cases, pipelines/stages, kanban, solutions/knowledge base, watchers, mentions, internal notes, bulk update/delete, SLA timing and pause/escalation, CSAT surveys, inbound email, routing rules, approvals, parent-child cases, merge/unmerge, time tracking, analytics, imports, notifications, and tests.

Improved:

- This app has grown substantially and has strong feature coverage.
- Business-hours integration supports SLA-style timing.
- Inbound email and webhook-like paths appear to set and clear tenant/RLS context deliberately.
- Support workflows now include routing, approvals, time tracking, knowledge base, and customer satisfaction.
- Time entries can feed invoice creation.

Remaining concern:

- Some old-style permission checks remain.
- The module is large and still mixes many workflows in views.
- Attachment delete is included in Claude's IDOR list and should be scoped through org and parent case.

### `invoices`

Full billing app. It now includes invoices, invoice line items, products, payments, estimates, recurring invoices, recurring/estimate line items, invoice templates, history, PDFs, public invoice/estimate views, dashboards, revenue/aging reports, invoice-from-opportunity and invoice-from-time-entry workflows, custom fields, Celery schedules, and tests.

Improved:

- Old duplicate serializer module is gone.
- Send-email argument order is fixed.
- Old `request.company` usage is gone from active invoice APIs.
- Money is now stored and mostly calculated through `Decimal` fields.
- Public portal/PDF endpoints are explicit.

Remaining concern:

- Some owner checks still compare `Profile` to `created_by`.
- `created_by=request.profile` appears in at least one attachment path and should be audited.
- Rounding policy should be explicit for all money totals.
- Public invoice/estimate routes may be blocked by org-context middleware because `/api/public/` is not generally exempted.

## Answer To The Main Question

Does the updated original backend solve all problems in `codex_review_plan.md`?

No.

It solves the most severe bootability and project-structure problems, and it adds a lot of real product functionality. It is much closer to a functioning CRM backend than the snapshot previously reviewed.

But it still does not close the security and correctness bar from the review plan. Claude's report makes me more confident that upstream is the right base to study or adopt, but less comfortable with treating it as production-ready. Before treating this as a safe upstream base, I would fix these in order:

1. Remove or replace org API-key admin impersonation, and immediately stop serializing `Org.api_key`.
2. Gate org key management behind admin-only permissions or remove the old org key path entirely in favor of hashed PAT/integration tokens.
3. Add project-level DRF default permissions and explicit public-route exemptions.
4. Fix the six attachment-delete IDOR patterns and any detail routes that fetch by `pk` before org scoping.
5. Fix production settings: remove wildcard CORS from `server_settings.py`, configure explicit origins, and add default throttling.
6. Make JWT refresh rotation real by installing/configuring token blacklisting, or remove the misleading rotation/blacklist settings.
7. Verify RLS under a non-superuser database role; do not deploy with `DBUSER=postgres`.
8. Fix `BaseModel.save()` audit behavior and replace all `Profile` versus `User.created_by` comparisons.
9. Finish generic comment/attachment creation in accounts and contacts.
10. Hash magic-link tokens and remove hardcoded email-domain superadmin trust.
11. Audit task/import paths for `User` versus `Profile` assignments, including the confirmed `leads/tasks.py` assignment.
12. Update tests so they assert desired behavior, not current crashes or accidental exceptions.

## Recommended Next Step

If we want to pull ideas from the updated original repo into this local CRM codebase, use upstream as the base/reference rather than trying to repair the older fork feature by feature. The updated repo gives us working implementations for common auth views, migrations, invoices, cases, kanban, PATs, custom fields, notifications, macros, and business hours.

The first adoption branch should be security-first: remove the org API-key escalation path, add default DRF permissions, lock production CORS, verify RLS with a non-superuser DB role, fix attachment-delete IDORs, repair audit/owner checks, and then run the full test suite.
