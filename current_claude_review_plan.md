# Backend Code Review & Solution Plan

> **Scope:** Full review of `backend/` (Django 5.2 + DRF, multi-tenant CRM, PostgreSQL).
> **Original ask:** *"I cloned django-crm and tried to recreate it fully… the original repo was unmaintained, buggy, not DRY, and looks like they stopped mid-refactor. Generic models look wrong in models.py and views.py; the same code is duplicated across modules; some modules contain both old and new models/serializers. Give an honest review and a solution plan for each app and its modules."*

This document is organized as:
1. **Honest verdict** (the blunt summary)
2. **Cross-cutting issues** — the systemic problems that repeat in *every* app (fix these first; they eliminate most of the per-app bugs at once)
3. **Per-app review** — module-by-module, with `file:line` refs and ranked bugs
4. **Solution plan** — a phased roadmap
5. **Bug quick-reference table**

---

## 1. Honest verdict

You are right on all counts, and the situation is a bit worse than "buggy": **the project does not currently boot or run end-to-end.** Three independent problems each block startup or every request:

- **The URLConf crashes on load.** `common/app_urls/__init__.py` includes the URL modules of `leads`, `opportunity`, `tasks`, `cases`, `invoices`, but those apps are commented out of `INSTALLED_APPS` (`crm/settings.py:55-60`). Importing their `urls.py` imports their models → `AppRegistryNotReady`/`RuntimeError`. It also `include(("common.urls"))`, but `common/urls.py` is 100% commented out and defines no `urlpatterns` → `ImproperlyConfigured`.
- **The whole HTTP surface of `common` is missing.** `common/views.py` is empty (`from django.shortcuts import render` + a comment). Login, register, org creation, dashboard, users, documents, teams, activities — all have finished *serializers* but **no views** and no URLs. There is no way to authenticate or create an org.
- **The request context every view depends on is never reliably set.** `request.profile` / `request.org` are meant to come from `common.middleware.get_company.GetProfileAndOrg`, which is commented out (`crm/settings.py:76`). The only thing that sets them is the DRF authenticator `CustomDualAuthentication`, and only on specific header combinations. Meanwhile `REST_FRAMEWORK` has **no `DEFAULT_PERMISSION_CLASSES`**, so DRF falls back to `AllowAny`.

Underneath that, the code quality issues you sensed are real and *systemic* — they are the same 6-7 mistakes copy-pasted across all eight business apps. The good news: because the mistakes are uniform, a relatively small set of shared fixes (a proper base model, a view mixin, one permission class, one generic-relation helper, one Celery app) removes the majority of the ~80 findings below.

**Overall grade:** the *architecture intent* in `common/` (a `BaseOrgModel`, org-scoped managers, view mixins, permission classes, RLS) is genuinely good and is the right target. The *apps* almost entirely ignore that intent and hand-roll broken versions of it. The refactor was started in `common/` and never propagated outward — that is exactly the "stopped in the middle" feeling you had.

### Cross-check against Codex's independent review

Codex reviewed the same backend (and read this plan). The two reviews are ~90% overlapping and fully compatible — independent corroboration of the same ~12 systemic issues raises confidence that these are the right priorities. Codex added real value by **actually running `python manage.py check` and AST-parsing all 136 files**, which upgrades several of my "will crash / un-importable" *inferences* into *confirmed facts*. I have verified each of the following firsthand and folded them into the plan below:

- **Even the *installed* apps fail `manage.py check`.** `accounts/views.py:48-53` (an installed app, reached via its URLs) imports `invoices.serializer`, `leads.models`, `opportunity.models`, `tasks.serializer` — all apps that are **not** in `INSTALLED_APPS`. So the failure is not just "disabled apps' URLs are included" (C1); the enabled set is itself broken. This is the sharper framing.
- **Confirmed hard `SyntaxError`s** (module won't even parse): `tasks/swagger_params.py:25` (missing comma — `organization_params` then `OpenApiParameter(...)` with only comments between), plus `common/tasks.py:5,12` and `common/token_generator.py:6` (previously listed as "un-importable" — now confirmed).
- **`Comment.get_files()` bug** — `common/models.py:320` filters `comment_id=self` (a `Comment` instance) instead of `comment=self`.
- **`Address.org` is required, but invoice serializers/forms create `Address` rows without `org`** → `IntegrityError`.
- **`InvoiceHistory` overrides `updated_by` with a `Profile` FK** while `created_by` stays a `User` FK — a confusing mixed audit contract.
- **`common/mixins.py:5`** does `from common.models import models` (re-imports Django's `models` through `common.models`) — a circular-import smell; should be `from django.db import models`.
- **`manage_rls.py --test`** queries `company` while the org table is `organization`; contacts `get_country()` calls `get_country_display()` on blank country; **URL route-ordering shadows** `leads/upload/` and `cases/solutions/` behind `<str:pk>/`.
- **Framing to adopt:** Codex's "freeze the contracts *before* coding" step (Org is the only tenant; Profile is the only membership/role actor; explicitly decide whether `Account.contacts` and `AccountEmail.recipients` survive; decide whether `leads.Company` merges into `Account`). These unmade product decisions are the *root cause* of the field-drift bugs — see Phase 0 below.

**One point of difference (invoices serializer):** I originally said keep the wired `serializer.py` and delete the dead `serializers.py`; Codex prefers keeping `serializers.py` (the better-designed module) and rewiring imports. Reconciled position: **pick one module, port the `*_ids` write-field design from `serializers.py` into the survivor, and do not delete either until the port is done** — don't run both in parallel. (Details in §3.4.)

---

## 2. Cross-cutting issues (the systemic ones)

These recur in nearly every app. Each per-app section references back to these by number (C1…C12).

### C1 — The app doesn't boot: `manage.py check` fails today
Three independent import-time failures (Codex confirmed with a real `manage.py check` run):
1. **Installed apps import non-installed apps.** `accounts/views.py:48-53` imports `invoices.serializer`, `leads.models`, `opportunity.models`, `tasks.serializer` — none are in `INSTALLED_APPS`. Since `accounts` *is* installed and its URLs load `accounts.views`, `check` fails immediately with a model-registry error.
2. **URLConf includes disabled apps.** `common/app_urls/__init__.py:10-15` includes `leads/opportunity/tasks/cases/invoices` URLs; those apps are commented out of `INSTALLED_APPS` (`crm/settings.py:55-60`). And `common/app_urls:7` `include(("common.urls"))` targets an empty module.
3. **Modules that won't parse.** Confirmed `SyntaxError`s: `tasks/swagger_params.py:25` (missing comma), `common/tasks.py:5,12`, `common/token_generator.py:6`.
**Fix:** make `INSTALLED_APPS` and every `include()`/cross-app import agree (either install the apps or gate the imports/includes behind them); fix the three parse errors; implement `common/urls.py` (see C2). Add a URL-import/`check` smoke test so this class of failure is caught automatically.

### C2 — `common` has serializers but no views/urls
`common/views.py` is empty; `common/urls.py` is fully commented. The auth/org/user/document/team/activity endpoints don't exist.
**Fix:** implement the views the commented URLConf references, then re-enable `common/urls.py`. This is the single biggest missing piece — nothing works without login/org creation.

### C3 — Tenant context + permissions are effectively off
- `GetProfileAndOrg` and `RequireOrgContext` middleware are commented out (`crm/settings.py:76-77`), so `request.profile`/`request.org` are not reliably populated.
- No `DEFAULT_PERMISSION_CLASSES` in `REST_FRAMEWORK` (`crm/settings.py:277-288`) ⇒ implicit `AllowAny`.
- Result: every view that reads `request.profile.org` will `AttributeError`, and any view that *doesn't* is wide open.
**Fix:** re-enable the (fixed) middleware; add `"DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated", "common.permissions.HasOrgContext"]`.

### C4 — Generic relations used wrong at the view/serializer layer (your concern #1)
`Comment` and `Attachments` (`common/models.py:278-345, 372-457`) are correctly modeled with `GenericForeignKey` (`content_type` + `object_id`). But **every app writes to a plain FK that doesn't exist**:
- `attachment.account = …` (accounts), `.contact =` (contacts), `.lead =` (leads), `.case`/`.cases =` (cases), `.task =` (tasks), `.invoice =` (invoices), `.opportunity =` (opportunity).
- `comment_serializer.save(account_id=…/lead_id=…/case_id=…/task_id=…/opportunity_id=…)` — none of those columns exist.
- Serializers declare non-existent reverse accessors: `contact_attachment`, `lead_attachment`/`lead_comments`, `task_comments`/`task_attachment`, `opportunity_attachment`, `AccountSerializer.contacts`.
Because `Comment.org`/`Attachments.org` are **required** and `full_clean()` runs in `save()` (`common/models.py:343-345, 455-457`), these writes raise every time. And even the correct read path (`filter(content_type=…, object_id=…)`) then finds nothing.
Separately, the modeling is *inconsistent*: `Comment`/`Attachments` use `GenericForeignKey`, but `Activity` (`common/models.py:631-687`) uses a **string** `entity_type` + `entity_id` for the same "attach to any model" job. Pick one pattern.
**Fix:** one shared helper/serializer that sets `content_type=ContentType.objects.get_for_model(obj)`, `object_id=obj.id`, `org=obj.org`, and the creator. Add `GenericRelation` accessors on the parent models so serializers can nest them. Standardize `Activity` on the same generic pattern (or leave it string-based but stop calling it "generic").

### C5 — `created_by`/`updated_by` are `User`, but code compares them to `Profile`
`AuditModel.created_by`/`updated_by` are FKs to `common.User` (`common/mixins.py:24-38`). Almost every view does `if request.profile == obj.created_by` or `request.profile != obj.created_by`. A `Profile` never equals a `User`, so **ownership checks silently always fail** → non-admin creators are locked out of their own records (and the "owner can edit" path is dead).
**Fix:** compare `obj.created_by == request.profile.user` (or `obj.created_by_id == request.profile.user_id`). Better: centralize in `CanAccessObject` (`common/permissions.py:130`) which already does it correctly, and delete the inline checks.

### C6 — Cross-org IDOR on detail-POST / attachment-delete
Repeated pattern: `Model.objects.get(pk=pk)` **with no `org=` filter** on the comment/attachment POST path and on `*AttachmentView.delete`. Any authenticated user can act on another org's row by guessing a UUID. Confirmed in accounts (`views.py:609`), contacts (`views.py:362`), leads (`views.py:431, 912, 1055`), cases (`views.py:384, 514`), opportunity (`views.py:448, 580`), tasks (`views.py:271, 471`), invoices (`api_views.py:517, 645`).
**Fix:** always `get_object_or_404(Model, pk=pk, org=request.profile.org)` — exactly what `OrgFilterMixin.get_org_object` (`common/mixins.py:89`) already provides. Also fixes the `.get()`-throws-500-instead-of-404 problem.

### C7 — Every app reinvents `BaseOrgModel`, the view mixins, and permissions (your concern #2)
`common/` ships `BaseOrgModel` (required `org` + `OrgScopedManager` + org index + RLS, `common/base.py:113`), `OrgViewMixin`/`OrgFilterMixin` (`common/mixins.py`), `AssignableMixin` (`common/base.py:13`), and `common/permissions.py`. **No business app uses them.** Instead each app:
- inherits `BaseModel` and hand-declares `org = ForeignKey(Org…)` + a duplicate `["org","-created_at"]` index;
- copies the `get_team_users`/`get_team_and_assigned_users`/`get_assigned_users_not_in_teams` trio verbatim (also duplicated *again* inside `common/models.py` `Document`/`Teams` even though `AssignableMixin` exists);
- hand-rolls org filtering, `filter_by_role`, and the 4-6 line "not ADMIN → 403" block, pasted ~4× per view file;
- hand-rolls pagination offset math instead of DRF's `get_paginated_response`.
**Fix:** rebase all tenant models on `BaseOrgModel`; rebase all views on `OrgViewMixin` + the permission classes; delete the duplicated model helpers in favor of `AssignableMixin`.

### C8 — Celery is mis-wired everywhere
Every app's task module does `app = Celery("redis://")` and decorates with `@app.task` (accounts, contacts, cases, leads, opportunity, invoices `tasks.py`; tasks `celery_tasks.py`). That creates a throwaway app named literally `"redis://"`, disconnected from the real `Celery("crm")` in `crm/celery.py`. Compounded by `crm/__init__.py` being **empty** (missing `from .celery import app as celery_app`), so the project app isn't loaded at Django startup and `autodiscover_tasks()` never runs. Net: `.delay()` calls don't reach the configured broker/worker.
Additional recurring task bugs: **argument order swapped** between caller and signature (accounts, invoices — a list lands in `invoice_id`, a UUID in `recipients`); **User-id vs Profile-id confusion** in recipient lookups.
**Fix:** delete the per-app `Celery("redis://")`; use `from celery import shared_task` / `@shared_task`; add `from .celery import app as celery_app` to `crm/__init__.py`; fix the call sites to match signatures.

### C9 — Half-finished refactor: old + new modules coexist (your concern #3)
Concrete dead/duplicate pairs to resolve:
- **invoices:** `serializer.py` (used, misspelled `InvoiceSerailizer`) vs `serializers.py` (cleaner, imported by *nothing* — dead); `views.py` (3-line stub) vs `api_views.py` (real); `urls.py` (absent) vs `api_urls.py`; plus `forms.py` (server-rendered `ModelForm`s, imported nowhere). The counter-intuitive part: the *newer-named* files are the dead ones.
- **cases:** `serializer.py`/`views.py` (Cases) vs `solution_serializers.py`/`solution_views.py` (Solutions) — **not** old-vs-new; they're two different features both wired. But the Case side is old-style and the Solution side is the cleaner target style. Standardize the Case side on the Solution side.
- **common:** empty `views.py` + commented `urls.py` (new, unfinished) coexist with `access_decorators_mixins.py` (old role-on-`User` model) and full serializers. `status.py` re-implements `rest_framework.status`. `common/tasks.py` and `common/token_generator.py` are **un-importable** (syntax errors, see per-app section).
- **contacts/leads:** `swagger_params.py` has a whole legacy block commented out above the active one; address handling exists as both an old FK approach (delete view still references `self.object.address_id`) and the new flat-fields approach.
**Fix:** delete the dead file of each pair; keep exactly one. Listed per-app below with explicit keep/delete verdicts.

### C10 — API-key auth = silent full-admin impersonation (critical security)
`common/external_auth.py:56-64`: a request with a `Token` header does `Org.objects.get(api_key=api_key)`, then grabs **any** `role="ADMIN"` profile in that org and authenticates the request as that admin. Possession of the org's API key = full admin. Worse, the key is **stored in plaintext** and **serialized back to clients** by `OrganizationSerializer` (`common/serializer.py:58`). Also `.split(" ")[1]` (`:37`) throws `IndexError` (500) on a malformed `Authorization` header, and `User/Profile.objects.get()` (`:44,47`) are unguarded (500 on unknown id). Two parallel JWT stacks exist (raw `pyjwt` here vs SimpleJWT `AccessToken` in the middleware).
**Fix:** never impersonate an arbitrary admin; bind API keys to a dedicated scoped service principal; hash keys at rest and make `api_key` write-only; guard header parsing and `.get()`; consolidate on SimpleJWT.

### C11 — `BaseModel.save()` audit bug + `jwt_payload_handler` references phantom fields
- `common/base.py:65-80`: after the `if self._state.adding:` branch sets `updated_by = None` for new rows, the code unconditionally runs `self.updated_by = user` again — so on *create*, `updated_by` is wrongly set to the creator instead of `None` (defeating its own stated intent).
- `common/utils.py:5-26` `jwt_payload_handler` reads `user.file_prepend`, `user.first_name`, `user.last_name`, (`role` commented) — the `User` model (`common/models.py:38-61`) has **none** of these fields. Any call raises `AttributeError`. The same phantom-field problem hits `access_decorators_mixins.py` and `common_tags.py` (`user.role`, `.has_sales_access`) and `common/tasks.py` (`User.objects.filter(username=…)`).
**Fix:** put the `self.updated_by = user` in an `else`; drop phantom fields from the payload handler; route role/access reads through `Profile`.

### C12 — Settings & production-safety
`crm/settings.py`: `DEBUG = True` hardcoded (`:32`); `ALLOWED_HOSTS = ["*"]` (`:34`); `CORS_ORIGIN_ALLOW_ALL = True` + `CSRF_TRUSTED_ORIGINS = ["https://*","http://*"]` (`:313-314`); `DEFAULT_AUTO_FIELD` set **twice** and contradictorily (`BigAutoField` `:167`, then `AutoField` `:321`); `REFRESH_TOKEN_LIFETIME = 365 days` (`:331`); a stray `print(">>> ENV_TYPE", …)` (`:183`); `MEDIA_ROOT`/`MEDIA_URL` only defined for `ENV_TYPE=="dev"` (undefined in prod unless `server_settings` supplies them). No `DEFAULT_PERMISSION_CLASSES` (see C3).
**Fix:** drive `DEBUG`, `ALLOWED_HOSTS`, CORS/CSRF allowlists from env; remove the duplicate `DEFAULT_AUTO_FIELD`; shorten refresh-token lifetime; remove the print.

---

## 3. Per-app review

### 3.0 `common` (foundation)
**Purpose:** shared user/org/profile/comment/attachment/document/team/activity models, base classes, mixins, permissions, auth, middleware, RLS, signals, management commands.

**Models (`common/models.py`) — the good and the inconsistent**
- `BaseModel`/`BaseOrgModel`/`AssignableMixin`/`OrgScopedManager` are well-designed (`base.py`) — this is the target architecture. The problem is nobody inherits `BaseOrgModel` or `AssignableMixin`.
- `Document` (`models.py:465-535`) and `Teams` (`models.py:695-719`) **duplicate the `AssignableMixin` methods verbatim** instead of mixing it in (C7).
- `Activity` (`models.py:631-687`) uses string `entity_type`+`entity_id` while `Comment`/`Attachments` use `GenericForeignKey` — inconsistent generic strategy (C4). The author's own `# [??] try genericforeign key` at `:664` is the right instinct.
- `Comment.save()`/`Attachments.save()` call `full_clean()` on every save (`:343-345, 455-457`) — the cross-org `clean()` check is good, but running full validation on every write is costly and will reject the app's own broken `.save(account_id=…)` calls.
- `Comment.get_files()` (`:320`) filters `comment_id=self` — passing a `Comment` instance to a `_id` field; should be `comment=self` (or `comment_id=self.id`).
- `common/mixins.py:5` does `from common.models import models` (re-imports Django's `models` through `common.models`) — circular-import smell; should be `from django.db import models`.
- `User` (`:38-61`) has no `first_name`/`last_name`/`username`/`role`/`file_prepend` — but utils/decorators/templatetags/tasks all reference those (C11). Either add them or purge the references.
- Dead code: a second commented-out `User` class (`:188-231`), `img_url` defined but unused (`:33`), trailing `from common.audit_log import SecurityAuditLog` at module end (`:800`) with a `# [??] why this here`.

**Routing** — see C1/C2. `common/app_urls/__init__.py:7` also has a no-op double-paren `include(("common.urls"))` (it's not a tuple; just `include("common.urls")`).

**Auth & middleware** — see C3/C10. `GetProfileAndOrg` (`middleware/get_company.py`) reads the `org` header + JWT to set `request.profile`/`request.org` — this is the intended mechanism and it's disabled. `CustomDualAuthentication` is active but buggy/insecure.

**Serializers (`common/serializer.py`)** — mostly valid and reasonably clean (this is where the finished refactor lives). Bugs:
- `CommentCreateSerializer.create` (`:98`) sets `content_type` from a bare model name via `ContentType.objects.get(model=…)` (no `app_label` → ambiguous/`MultipleObjectsReturned`) and **never sets `org`/`commented_by`** → `IntegrityError` (`Comment.org` is non-null). Same for `AttachmentsCreateSerializer` (`:302`). No `object_id`-belongs-to-my-org check → cross-org injection once wired.
- `OrganizationSerializer` exposes `api_key` (`:58`) — see C10.
- N+1s: `UserDetailSerializer.get_organizations` (`:540`), `DocumentSerializer.get_teams` (`:324`) query per row.

**RLS (`common/rls/__init__.py`, `management/commands/manage_rls.py`)** — the SQL is well-formed and fail-safe (`NULLIF(current_setting('app.current_org', true),'')`). But it's **not enforced**: the middleware that sets `app.current_org` is disabled (C3), several table names in `ORG_SCOPED_TABLES` are guesses, `manage_rls.py --test` queries `company` while the org table is `organization`, and a superuser `DBUSER` bypasses RLS entirely. Today there is **no DB-level isolation**.

**Signals / audit / tasks / commands**
- `signals.py` is wired via `apps.ready()`, but `create_activity` reads `request.profile` (`:42`) — always `None` with middleware off, so Activity is never recorded; several senders are non-installed apps; `get_entity_name` probes `first_name`/`last_name` (phantom, C11).
- `audit_log.py` defines `SecurityAuditLog` but it is **never written** anywhere — the security audit trail is aspirational.
- `common/tasks.py` **does not import**: `from celery ipmort Celery` (`:5` typo), `from django.utils import encoding import force_bytes` (`:12`), `urlsafe_based64_encode` (`:13` typo), plus runtime `NameError`s (`html_context` `:212`, `removed_users_list` `:316`).
- `common/token_generator.py` **does not import**: `IndentationError` (`:6-9`) and the instance is misspelled `account_acitvation_token` while callers import `account_activation_token`.
- `migrate_from_prisma.py` imports non-installed apps and writes via raw SQL to guessed table names (fragile, no per-model transaction).
- `status.py` duplicates `rest_framework.status`; `access_decorators_mixins.py` is old role-on-`User` dead code.

**Ranked bugs (common):** C10 (api-key impersonation) → C1/C2 (won't boot) → C3 (no isolation) → common/tasks.py & token_generator.py un-importable → CommentCreate/AttachmentsCreate missing `org` → `BaseModel.save()` audit bug.

---

### 3.1 `accounts`
**Purpose:** Account (company) CRUD + comments/attachments + outbound account emails (with Celery scheduling). *In `INSTALLED_APPS`.*

**Models (`models.py`)** — half-reverted "Contact" removal left dangling references:
- `Account` reinvents `BaseOrgModel` (manual `org` + index; also `AccountEmail`/`AccountEmailLog`) (C7).
- `Account.contact_values` (`:97-100`) reads `self.contacts…` but the `contacts` M2M is commented out (`:49-51`) → `AttributeError`.
- `AccountEmail.save` (`:146`) reads `self.recipients` (field commented, `:107`); `AccountEmailLog.save`/`__str__` (`:180,190`) read `self.contact`/`self.email.message_subject` with `email` nullable → `AttributeError`.

**Serializers (`serializer.py`)**
- `AccountSerializer.contacts` (`:63`), `EmailLogSerializer.contact` (`:124`), `AccountWriteSerializer.contacts` (`:152`), `EmailWriteSerializer.recipients` (`:222`) all reference **non-existent model fields** → serialization/validation errors.
- Typo class `TagsSerailizer` (`:15`) propagated into imports.
- `AssignableMixin` properties declared as nested serializer fields (`:32-34`) → unbounded N+1; no `select_related`/`prefetch_related` anywhere.
- `EmailSerializer.__init__` (`:84-85`) is a no-op but the view passes `request_obj=` → `TypeError`. Two parallel serializer sets (old `AccountSerializer/...` used by views vs newer thin `AccountReadSerializer/AccountWriteSerializer` set as `serializer_class` but never used) — dead scaffolding (C9).

**Views (`views.py`)** — none use `common` mixins (C7); role/permission block copy-pasted 4× (`:257-271, 347-355, 375-386, 486-497`); redundant post-`get_object` org checks; `filter(tags__in=params.get("tags"))` (`:82`) iterates a raw string char-by-char; contacts logic all broken (field gone). Massive cross-app imports (`:46-53`) aggregate every other app inline. `AccountAttachmentView.delete` (`:609`) has no org filter (C6).

**URLs & tasks** — `<str:pk>` instead of `<uuid:pk>`. `tasks.py` is **dead on arrival**: references undefined `Email`/`EmailLog` (models are `AccountEmail`/`AccountEmailLog`) → `NameError`; `Celery("redis://")` (C8); bare `print(e)` error handling. `tests_celery_tasks.py` imports non-existent `Email` and a base class from an empty `tests.py` → suite won't collect.

**Ranked bugs:** (1) all `created_by==profile` checks always False (C5) at `:262,348,377,402,488,556,585,613`; (2) cross-org attachment delete (C6, `:609`); (3) `tasks.py` `NameError` (`:19,24,56,93`); (4) comment create/update always 500 (C4, `:501-503, 558`); (5) `attachment.account=` phantom field (C4, `:209,317,510`); (6) serializing any Account raises (`serializer.py:63`); (7) `AccountCreateMailView.post` sets `data = {}` mid-handler then reads from it (`:650,660,674`).

---

### 3.2 `contacts`
**Purpose:** Contact CRUD + comments/attachments + assignment-notification task. *In `INSTALLED_APPS`.*

**Models (`models.py`)** — reinvents `BaseOrgModel` (`:11,55,69`) (C7); uses `AssignableMixin` correctly; **no** comment/attachment relation declared (the `GenericRelation` is commented out `:56-60`) yet serializer/views assume one (C4); address is flat fields duplicating `common.Address`; `__str__` returns only `first_name`; a `(email, org)` unique constraint is TODO-noted but enforced only in Python (race-prone).

**Serializers (`serializer.py`)** — `contact_attachment` (`:20`) references a non-existent relation → read fails (C4); the three `get_*_users` properties nested as serializers → N+1; `org` writable (no `read_only`); `get_country()` calls `get_country_display()` even when `country` is blank/null → return `None` instead.

**Views (`views.py`)** — `address__city__icontains` (`:48`) but there's no `address` relation → 500 on `?city=`; `self.object.address_id`/`self.object.address.delete()` in delete (`:345-346`) → `AttributeError`; `contact_obj.account_contacts` (`:253`) reverse relation is commented out in accounts → `AttributeError`; comment/attachment blocks duplicated and write to phantom `.contact`/`contact_id` (C4, `:135,227,380`); detail-POST `Contact.objects.get(pk=pk)` no org filter (C6, `:362`); previous-assignee diff computed *after* `clear()` so notifications never fire (`:214-222`); `assigned_to__id__in=params.get(...)` passes a scalar (`:55`).

**URLs & tasks** — `<str:pk>`; `Celery("redis://")` throwaway (C8); `tests_celery_tasks.py` references undefined `ContactObjectsCreation` → won't import.

**Ranked bugs:** (1) `account_contacts` AttributeError on every detail GET (`:253`); (2) attachment save to phantom `.contact` (`:135`); (3) comment save to phantom `contact_id` (`:380`); (4) `contact_attachment` serializer field (`serializer.py:20`); (5) delete references non-existent `address` (`:345`); (6) `?city=` 500 (`:48`); (7) IDOR detail-POST (`:362`).

---

### 3.3 `cases`  *(commented out of `INSTALLED_APPS`; URLs not reachable)*
**Purpose:** support **Cases** CRUD (`views.py`/`serializer.py`) **and** a **Solution** knowledge base (`solution_views.py`/`solution_serializers.py`). The two file-sets are *different features*, both wired in `urls.py` — **not** an old/new duplicate. The Solution side is the cleaner, newer style; the Case side is old-style. (C9 note: here the fix is "level up the Case side," not "delete a file.")

**Models (`models.py`)** — `Case` and `Solution` both reinvent `BaseOrgModel` (`:37,44-48,78`) (C7); `created_by` commented out (`:32-34`) but relied on everywhere (it's still inherited from `AuditModel`); dead `closed_on` DateTimeField comment; `case_type` mixes `null=True` + `default=""`. **No migrations exist** (`migrations/` has only `__init__.py`).

**Serializers** — `CaseSerializer` nests 6 serializers, no prefetch → N+1; `CaseCreateSerializer.closed_on = serializers.DateField` (`:46`) assigned the **class, not an instance** → field ignored; create serializer lists read-only audit fields as writable. `solution_serializers.py` is the good pattern (uses `read_only_fields`, field validators) but has `get_case_count`/`get_linked_cases` N+1.

**Views** — neither uses `common` mixins; Case role block pasted 4× (`:48,194-198,279-287,311-315`); Solution views have **no object-level permission at all** (any org member can edit/delete/publish any solution). `created_by` compared to `Profile` (C5, `:280,490,518`) while `:196` correctly uses `.user`. `CaseDetailView.post` `.get()` → 500 (`:384`); `CaseAttachmentView.delete` no org filter (C6, `:514`).

**URLs & tasks** — Case routes have no `name=`; `<str:pk>`; **`<str:pk>/` precedes `solutions/`, so the Solution routes are shadowed by the detail route** (move `solutions/` first); not included in `crm/urls.py`. `tasks.py:9` `Celery("redis://")` (C8) and `from accounts.models import Profile` (`:6`) wrong path (it's `common.models`). `tests_celery_tasks.py` imports from a non-existent `cases/tests.py`.

**Ranked bugs:** (1) comment save to phantom `case_id` (C4, `:407-410`); (2) attachment save to phantom `.cases` (create, `:147`); (3) attachment save to phantom `.case` (update, `:249,416`) — note the two spellings are inconsistent; (4) wrong Celery app + wrong `Profile` import (`tasks.py:6,9`); (5) `created_by` vs `Profile` (C5); (6) IDOR (`:514`); (7) `DateField` class-not-instance (`serializer.py:46`).

---

### 3.4 `invoices`  *(commented out of `INSTALLED_APPS`; the worst refactor mess)*
**Purpose:** Invoice + InvoiceHistory (+ Product/InvoiceLineItem). Two parallel stacks; **nothing is wired** (`api_urls.py` never `include()`d, `urls.py` absent).

**Old vs new (C9) — explicit verdicts:**
- KEEP (after fixing): `api_views.py` (real, but old-style), `api_urls.py`, `models.py`, `tasks.py`, `admin.py`, `swagger_params.py`.
- DELETE now: `views.py` (3-line stub), `forms.py` (server-rendered `ModelForm`s, imported nowhere), broken `tests_celery_tasks.py` (imports `InvoiceCreateTest` from empty `tests.py`).
- **One serializer module — reconciled with Codex:** there are two (`serializer.py`, wired but misspelled `InvoiceSerailizer`, `created_by = ProfileSerializer` bug; and `serializers.py`, cleaner `*_ids` write fields + `InvoiceListSerializer` + correct `created_by = UserSerializer`, but imported by nothing). Pick **one** survivor (Codex recommends keeping `serializers.py` for its better design and rewiring `api_views.py`'s import to it; either filename is fine). **Port the good write-field design into the survivor first, then delete the other — do not leave both running in parallel.** My earlier "delete `serializers.py`" is superseded by this: it's the better *source material*, not dead weight to drop.

**Models (`models.py`)** — money fields are correctly `DecimalField` (good). But: reinvents `BaseOrgModel` on all 4 models (C7); copies `AssignableMixin` verbatim (`:131-148`); `invoice_id_generator` (`:87-92`) returns an `int` for a `CharField` and its uniqueness loop compares CharField to int; `INVOICE_STATUS` defined twice (`:17-23, 156-162`); `InvoiceHistory` omits the `tax` field that `Invoice` has; `InvoiceHistory` overrides `updated_by` to a **`Profile`** FK while `created_by` stays a **`User`** FK — a confusing mixed audit contract (rename to `changed_by_profile` or keep the inherited `User` `updated_by`); the invoice views create `Address` rows without setting the **required** `Address.org` → `IntegrityError`.

**Views (`api_views.py`)** — uses a **third tenancy notion** `request.company`/`self.request.company` (`:60,61,119,191,…`) that doesn't exist on these models, mixed with `request.profile.org` — every endpoint 500s. Hand-rolls pagination via `APIView, LimitOffsetPagination` (`:52`); attachment save to phantom `.invoice` (C4, `:544-549`); IDOR on detail-POST/attachment-delete (C6, `:517,645`); non-atomic multi-step create that `delete()`s the invoice mid-request on a bad id.

**Tasks** — `Celery("redis://")` (C8); `reverse("invoices:invoice_details")` → `NoReverseMatch` (namespace/route don't exist); `send_invoice_email`/`_cancel` duplicated bodies; `create_invoice_history` omits `tax`.

**Ranked bugs:** (1) **money computed in float** (`api_views.py:166-169,336-339`) on `Decimal` fields → rounding errors (C4-adjacent); (2) `send_email.delay(recipients, invoice_obj.id)` **argument order swapped** vs `send_email(invoice_id, recipients)` (C8, `api_views.py:242,384`); (3) malformed `Response({"error":True}, data)` — dict passed as HTTP status (`:162,210,310,353`); (4) `NoReverseMatch` on every email (`tasks.py:35`); (5) `created_by = ProfileSerializer()` on a User FK (`serializer.py:16`); (6) IDOR (`:517,645`); (7) `assigned_to.add(user_id)` adds User to a Profile M2M (`:229-231`).

---

### 3.5 `leads`  *(commented out of `INSTALLED_APPS`; URLs unwired)*
**Purpose:** Lead capture/list/edit, convert→Account/Contact, bulk CSV import, public site-capture via API key, plus a `Company` model. ~1100-line `views.py`.

**Models (`models.py`)** — `Lead`/`Company` reinvent `BaseOrgModel` (`:33,103,120,19`) (C7); use `AssignableMixin`; comments/attachments not related by FK yet serializer declares `lead_attachment`/`lead_comments` (C4, `serializer.py:41,43`); flat address duplicating `common.Address`; convert logic lives entirely in views in **three divergent copies**; `phone_raw_input` compares `str(self.phone)=="+NoneNone"` (brittle). **No migrations.**

**Views (`views.py`)** — the three convert implementations (`:221-281`, `:571-633`, `:677-769`) reference **non-existent Account fields** (`billing_street/billing_city`) and `Lead.street`, use an unset `self.lead_obj`, pass `lead=lead_obj` to `Account.objects.create()` (no such field), and skip `account_object.save()`. Tag-upsert duplicated and omits `slug`/`org` on create (`:184,528`); attachment/comment blocks duplicated 3× and write to phantom `.lead`/`lead_id` (C4); name search uses `Q(...) & Q(...)` (`:75-76`) so both names must match; IDOR on `:431,912,1055` (C6); `filter(**request.data)` (`:1029`) → `FieldError`; `print("test")`/`print(request.data)` debug lines. `created_by` mixed types in permission list (`:309-313`, C5).

**URLs, forms & tasks** — unwired; **route ordering: `<str:pk>/` is declared before `upload/`, so `/api/leads/upload/` is shadowed by the detail route** (put fixed routes before the dynamic `<pk>` route); `companies`/`company/<pk>` omit trailing slashes; `forms.py` server-rendered widget code (dead in API context); public `CreateLeadFromSite` (`:932`) authenticates by API key with the website-origin check commented out (any org's key works), reads `params.get("message")` while the site sends `description`, `add(user)` a User to a Profile M2M, and `except Exception: pass` swallows failures. `Celery("redis://")` (C8); `send_email_to_assigned_user` recipient User-id vs Profile-id mismatch; CSV import sets `created_by = profile` (should be `.user`) and dedupes globally not per-org.

**Ranked bugs:** (1) IDOR (`:431,912,1055`); (2) convert references phantom fields (`:237-240,583`); (3) `self.lead_obj` never set (`:247,257`); (4) comment/attachment phantom FK (C4); (5) tag create omits `slug`/`org` → cross-org leakage (`:184`); (6) CSV `created_by=profile` integrity error (`tasks.py:138`); (7) name filter `&` should be `|` (`:75-76`).

---

### 3.6 `opportunity`  *(commented out of `INSTALLED_APPS`; a copy-paste clone of `cases`)*
**Purpose:** sales-pipeline Opportunity CRUD + comments/attachments + email task.

**Models (`models.py`)** — reinvents `BaseOrgModel` (`:13,76-80,89`) (C7); `AssignableMixin` reused; `amount` correctly `DecimalField` (no float bug here); `probability` is nullable + defaulted with no 0-100 validators; **field is `closed_on` but views save from `params.get("due_date")`** (`:148,265`) so close-date never populates; `stage` compared to string literals `"CLOSED WON"/"CLOSED LOST"` (`:171,290`) instead of `STAGES` constants.

**Serializers (`serializer.py`)** — deep nesting, no prefetch → N+1; `opportunity_attachment` (`:33`) references non-existent reverse relation (C4); `request_obj` anti-pattern; duplicate local `TagsSerializer` while views import the typo'd `TagsSerailizer` from accounts.

**Views (`views.py`)** — no `common` mixins; tags/attachment/permission blocks pasted across `post`/`put`/`get`; UUID `id__gte` pagination offset is meaningless (`:102`); `closed_by` set but never `.save()`d (`:172,291`); `created_by == profile` always False (C5, `:240,345,373,457`); IDOR on `:448,580` (C6); no `@transaction.atomic`.

**Tasks** — `Celery("redis://")` (C8, `:11`), the correct `@shared_task` version sits commented out right below; per-recipient query loop; `tests.py:5` imports `OpportunityModel` from itself → `ImportError`.

**Ranked bugs:** (1) attachment save to phantom `.opportunity` (C4, `:195,313,480`); (2) comment save to phantom `opportunity_id` (C4, `:470`); (3) IDOR attachment delete (`:580`); (4) ownership checks always False (C5); (5) `closed_by` never persisted (`:172,291`); (6) wrong Celery app; (7) broken test import.

---

### 3.7 `tasks`  *(commented out of `INSTALLED_APPS`; two apps in one)*
**Purpose:** CRM to-do **Task** entity **plus** an entire **Kanban Board** feature (`Board`/`BoardMember`/`BoardColumn`/`BoardTask`, "merged from boards app"). `celery_tasks.py` = the email task; `utils.py` = just duplicated `STATUS_CHOICES`/`PRIORITY_CHOICES` (not Celery).

**Models (`models.py`)** — `Task` reinvents `BaseOrgModel` (`:222,257`) (C7); status/priority choices duplicated three ways (model, `utils.py`, `common/utils.py`); no reminder field despite the notion; commented-out `created_by = ForeignKey(Profile)` (`:249-255`) is the root of the C5 confusion; **`BoardMember` `UniqueConstraint` references a non-existent field `user`** (`:72-73`; the field is `profile`) → `makemigrations` fails.

**Serializers (`serializer.py`)** — `task_attachment`/`task_comments` nested fields with no matching relation (C4, `:146-147,163-164`); `request_obj` anti-pattern; Board serializers use `fields="__all__"` (leaks `org`/audit fields); count methods → N+1.

**Views (`views.py`)** — no `common` mixins; N+1 (correct prefetch is written as a comment but unused, `:55-67`); IDOR on detail-POST (`:271`) and attachment delete (`:471`) (C6); `.get(pk=…)` → 500; `created_by == profile` (C5) at `:178,211,274,384,417,447,475`; `Teams.objects.all()` not org-scoped (`:254`); a `Response(...403...)` built inside `get_context_data` is stuffed into context and never returned (permission silently bypassed).

**URLs, celery_tasks & utils** — `board_urlpatterns` defined but never included; `<str:pk>`; `celery_tasks.py:12` `Celery("redis://")` (C8) with unused imports; **`swagger_params.py:25` is a hard `SyntaxError`** (missing comma after `organization_params`, then `OpenApiParameter(...)` with only comments between) → the module won't import (confirmed via AST parse), taking `tasks.views` down with it.

**Ranked bugs:** (1) comment save to phantom `task_id` → 500 (C4, `:287-290`); (2) attachment save to phantom `.task` (C4, `:302`); (3) IDOR (`:271,471`); (4) `created_by == profile` always False (C5); (5) `BoardMember` constraint `FieldError` (`:72-73`); (6) wrong Celery app; (7) `swagger_params.py:25` `SyntaxError` → `tasks.views` won't import.

**Recommendation:** split Kanban into its own app; it's cleaner than the Task side and doesn't belong here.

---

## 4. Solution plan (phased)

The ordering matters: the shared foundation fixes (Phase 1-2) delete most per-app bugs for free. Don't fix apps one-by-one first.

### Phase 0a — Freeze the contracts (decisions first, no code) — *adopted from Codex*
The field-drift bugs (phantom `.account`/`.lead`/`.company`/`company=`, `User`-vs-`Profile`, `contacts`/`recipients` references) all stem from unmade product decisions. Lock these *before* touching code, so the cleanup has a single target:
- **`Org` is the only tenant.** Delete `company`/`request.company` everywhere; there is no company-as-tenant.
- **`Profile` is the only membership/role/access actor; `User` only authenticates.** All `role`/`has_*_access` reads go through `Profile`; `created_by`/`updated_by` stay `User`.
- **Keep generic `Comment`/`Attachments`** (ContentType) — but commit to finishing the migration in every app.
- **Decide `Account.contacts` and `AccountEmail.recipients`:** restore the relations (with correct `Contact`/`Profile`/`Org` constraints) *or* delete the account-email feature (endpoints, serializers, tasks, tests, properties). Right now they're half-removed.
- **Decide `leads.Company`:** rename to `LeadCompany` or merge into `Account` if it's the same concept — the current `company` table name collides semantically with the tenant story.

### Phase 0b — Make it boot & make `manage.py check` pass (½ day)
1. Fix the three parse errors: `tasks/swagger_params.py:25` (missing comma), `common/tasks.py:5,12`, `common/token_generator.py:6` (+ the `account_acitvation_token` name).
2. Break the installed→non-installed import chain: `accounts/views.py:48-53` imports `invoices/leads/opportunity/tasks` — gate or remove those imports so `check` passes with the current `INSTALLED_APPS` (C1).
3. Reconcile `INSTALLED_APPS` with `common/app_urls` includes; enable only apps you'll run, gate the rest in *both* places.
4. Fix the `tests_celery_tasks.py`/`tests.py` import mismatches (accounts, contacts, cases, leads, opportunity, invoices) so the suite collects.
5. Add `from .celery import app as celery_app` to `crm/__init__.py` (C8).
6. Remove the duplicate `DEFAULT_AUTO_FIELD`, the `print` statements, and drive `DEBUG`/`ALLOWED_HOSTS`/CORS from env (C12).
7. **Exit criteria:** `python manage.py check` passes; every installed URL module imports; OpenAPI schema generates. Add a smoke test that asserts this.

### Phase 1 — Restore auth, org context, and isolation (2-3 days) — *highest security value*
1. Implement `common/views.py` (login/register/activate/org-create/me/users/documents/teams/activities) and re-enable `common/urls.py` (C2).
2. Fix and re-enable `GetProfileAndOrg` + `RequireOrgContext` middleware; add `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated, HasOrgContext]` (C3).
3. Rewrite `CustomDualAuthentication` (C10): guard header parsing and `.get()`; remove admin-impersonation; hash API keys and make `api_key` write-only in `OrganizationSerializer`; consolidate on SimpleJWT; delete `verify_jwt_token`'s parallel path. Fix `jwt_payload_handler` phantom fields (C11).
4. Fix `BaseModel.save()` audit bug (C11).
5. Decide RLS: either finish it (non-superuser `DBUSER`, verified table names, middleware on) or explicitly defer it and rely on `OrgScopedManager` — but don't leave it half-on.

### Phase 2 — Consolidate the shared layer, then delete duplication (3-5 days)
1. **One generic-relation helper** (C4): a `GenericRelatedCreateSerializer`/mixin that sets `content_type`/`object_id`/`org`/creator and validates the target's org. Add `GenericRelation("common.Comment")`/`("common.Attachments")` to every parent model so serializers can nest them. Standardize `Activity` on the same pattern (or rename it — stop calling string fields "generic").
2. **One object-permission path** (C5/C6): use `CanAccessObject` + `OrgFilterMixin.get_org_object` everywhere; delete the ~30 inline `created_by==profile` / `.get(pk=pk)` blocks.
3. **Rebase models on `BaseOrgModel`** and **views on `OrgViewMixin`** (C7); delete duplicated `org` FKs, indexes, `AssignableMixin` copies (including in `common.Document`/`Teams`), and pagination math.
4. **One Celery app** (C8): delete every `Celery("redis://")`; use `@shared_task`; fix argument-order/User-vs-Profile call sites.

### Phase 3 — Resolve old-vs-new files (1-2 days) (C9)
- invoices: delete `views.py`, `forms.py`, `serializers.py`; port its good ideas into `serializer.py`; wire `api_urls.py`.
- cases: standardize the Case side on the Solution side's style.
- common: delete `access_decorators_mixins.py`, `status.py`; finish or delete `migrate_from_prisma.py`.
- everywhere: delete commented-out legacy blocks in `swagger_params.py`, dead `save()` overrides, second `User` class, etc.
- Generate the **missing migrations** (cases, leads have none).

### Phase 4 — Correctness & polish (ongoing)
- invoices: move money math to `Decimal.quantize`; wrap multi-step create in `transaction.atomic`; fix `invoice_id_generator`; add `tax` to history.
- Fix filter bugs (`tags__in` on strings, `&`-vs-`|` name search, `getlist`), `<uuid:pk>` converters, N+1 via `select_related`/`prefetch_related`.
- Split Kanban Board out of `tasks`.
- Add real tests (the current `tests.py` files are empty stubs; the only task tests don't import).
- Register models in `admin.py` with proper `list_display`/org scoping, or remove.

---

## 5. Bug quick-reference table

| # | Severity | Issue | Where (representative) | Fix |
|---|---|---|---|---|
| C1 | Blocker | `manage.py check` fails: installed apps import non-installed apps, 3 parse errors, empty `common.urls` | `accounts/views.py:48-53`; `tasks/swagger_params.py:25`; `common/tasks.py:5` | Gate cross-app imports; fix parse errors; sync includes |
| C2 | Blocker | `common` has no views/urls | `common/views.py`, `common/urls.py` | Implement auth/org endpoints |
| C10 | Critical | API-key = admin impersonation; key in plaintext & serialized | `external_auth.py:56-64`; `serializer.py:58` | Scoped principal; hash; write-only |
| C3 | Critical | No tenant context / no default permissions | `settings.py:76-77,277-288` | Enable middleware; add perms |
| C6 | Critical | Cross-org IDOR on POST/attachment-delete | all apps, `.get(pk=pk)` | `get_org_object(pk)` |
| C4 | High | Generic comments/attachments write to phantom FKs; serializers declare phantom reverse relations | all apps | Shared generic helper + `GenericRelation` |
| C5 | High | `created_by`(User) compared to `Profile` → ownership always fails | all apps | Compare `.user`; use `CanAccessObject` |
| C8 | High | Throwaway `Celery("redis://")`; empty `crm/__init__.py`; swapped task args | all apps | `@shared_task`; fix `__init__`; fix calls |
| C11 | High | `BaseModel.save()` sets `updated_by` on create; `jwt_payload_handler` phantom fields | `base.py:65-80`; `utils.py:5-26` | `else` branch; drop phantom fields |
| — | High | Money in float | `invoices/api_views.py:166-169` | `Decimal.quantize` |
| — | High | Un-importable modules | `common/tasks.py`, `common/token_generator.py` | Fix typos/indentation |
| C7 | Medium | Every app reinvents `BaseOrgModel`/mixins/permissions | all apps | Rebase on `common/` |
| C9 | Medium | Old+new files coexist (invoices, cases, common, swagger) | see §3 | Delete dead file of each pair |
| C12 | Medium | `DEBUG=True`, `ALLOWED_HOSTS=*`, CORS all, dup `DEFAULT_AUTO_FIELD`, 365-day refresh | `settings.py` | Env-drive; dedupe |
| — | Medium | No migrations for `cases`, `leads` | `*/migrations/` | `makemigrations` |
| — | Low | `<str:pk>` for UUIDs; N+1; wildcard imports; empty tests; debug `print`s | all apps | `<uuid:pk>`; prefetch; real tests |

---

*Reviewed: models, serializers, views, urls, tasks, middleware, auth, permissions, RLS, and settings across `common`, `accounts`, `contacts`, `cases`, `invoices`, `leads`, `opportunity`, `tasks`, and the `crm` project config. Findings are grounded in specific `file:line` references; the systemic items (C1-C12) are the highest-leverage fixes.*
