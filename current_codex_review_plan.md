# Codex Backend Review And Solution Plan

Original request: review the whole Django CRM backend under `backend/`, especially the incomplete refactor, the generic comment/attachment models, duplicated code, old/new model drift, serializers, and views.

## Executive Verdict

The backend is not ready for feature work yet. It is currently in a broken intermediate refactor state: several files do not parse, Django cannot complete `manage.py check` with the current settings, multiple URL modules import apps that are not installed, and many views/serializers still reference fields that were removed from the models.

The generic `Comment` and `Attachments` approach in `common.models` is not inherently wrong. A `ContentType` + `object_id` design is a valid Django pattern for CRM-wide comments and files. The problem is that the rest of the codebase was not migrated to that pattern. Most app views still save `account_id`, `lead_id`, `attachment.account`, `attachment.lead`, etc., which do not exist on the generic models. Serializers expose reverse names such as `account_attachment`, `lead_comments`, `contact_attachment`, and `task_attachment` without adding `GenericRelation` fields on the target models.

The highest-value path is not a broad rewrite. First make the project importable, choose one tenant model (`Org`) and one membership actor (`Profile`), finish the generic comment/attachment refactor, and only then clean up app-by-app duplication.

## Opinion After Reading `claude_review_plan.md`

Claude's review is directionally correct and more aggressive on security prioritization than my first pass. I agree with the core conclusion: the project is not merely messy; it currently does not boot cleanly and the refactor stopped between the shared `common` architecture and the business apps.

The most important Claude findings I am folding into this plan are:

- `REST_FRAMEWORK` has no `DEFAULT_PERMISSION_CLASSES`, so endpoints default to DRF's permissive behavior unless each view sets permissions correctly.
- API-key auth is a critical risk: the current design effectively turns possession of an org API key into impersonation of the first admin profile in that org, and `OrganizationSerializer` exposes the key.
- Celery is not only duplicated; it is disconnected from the project Celery app because modules create `Celery("redis://")` locally and `crm/__init__.py` does not expose the project app.
- `BaseModel.save()` defeats its own audit intent by setting `updated_by` during creation.
- `jwt_payload_handler`, old decorators, template tags, and tasks still reference phantom `User` fields such as `username`, `role`, `file_prepend`, and access flags.
- Invoices have additional correctness bugs worth calling out explicitly: float math for money, malformed `Response()` calls, and swapped Celery task arguments.

My only meaningful nuance is on cleanup sequencing. Claude recommends deleting some dead files, especially in `invoices`. I agree with consolidation, but I would not delete `invoices/serializers.py` until its better API ideas are ported into the active serializer module or imports are switched. Treat it as source material for the final serializer contract, not as code to keep running in parallel.

## Verification Performed

- Static AST parse over 136 project Python files, excluding `.venv`.
- `manage.py check` using `backend/.venv/Scripts/python.exe` with development environment variables.
- Django setup probe with the disabled business apps temporarily added to `INSTALLED_APPS`.
- Manual review of models, serializers, views, URLs, Celery tasks, forms, admin, middleware, RLS utilities, management commands, and tests.

Confirmed hard failures:

- `backend/common/tasks.py` has syntax errors at lines 5 and 12.
- `backend/common/token_generator.py` has an indentation error at line 6 and exports `account_acitvation_token`, while callers import `account_activation_token`.
- `backend/tasks/swagger_params.py` has a syntax error at line 25 due to a missing comma.
- `python backend/manage.py check` fails because `accounts.views` imports `invoices.models`, but `invoices` is not in `INSTALLED_APPS`.
- All app `migrations/` directories contain only `__init__.py`; there are no initial migrations for the current models.

## Cross-Cutting Problems

### 1. App Loading And URL Wiring Are Broken

`backend/crm/settings.py` installs only `common`, `accounts`, and `contacts`; `cases`, `leads`, `opportunity`, `tasks`, and `invoices` are commented out. But `backend/common/app_urls/__init__.py` includes URLs for all of those apps. That creates import-time failures as soon as URL checks run.

`backend/common/urls.py` is fully commented out, so the auth, org, profile, document, team, API settings, and activity endpoints referenced in comments are not actually exposed. `backend/common/views.py` is still the default stub.

Solution:

- Decide the active backend surface. Either install all apps and make them valid, or remove their URL includes until each app is fixed.
- Restore real common auth/org/user/team/document/activity views or delete the commented URL contract.
- Add URL import tests so `reverse()`/schema generation catches this class of failure.

### 2. The Tenant Model Is Inconsistent

The newer models use `Org` and `Profile`. Older view/form/task code still uses `company`, `request.company`, `request.user.role`, `request.user.has_sales_access`, and `request.user.has_marketing_access`.

Examples:

- `invoices/api_views.py` filters `Invoice` and `Account` by `company=...`, but those models now use `org`.
- `common/external_auth.py` still trusts the `org` header for JWT requests, despite the safer JWT `org_id` claim design in `OrgAwareRefreshToken`.
- `common/middleware/get_company.py` sets `request.org` and `request.profile`, but that middleware is commented out in `settings.py`.
- `common/access_decorators_mixins.py` and `common/templatetags/common_tags.py` check `request.user.role`, but role/access flags live on `Profile`.
- `REST_FRAMEWORK` does not define `DEFAULT_PERMISSION_CLASSES`, so routes without explicit permission classes fall back to DRF defaults.

Solution:

- Make `Org` the only tenant model.
- Make `Profile` the only org membership/role object.
- Remove `request.company` and `company=` filters from all active code.
- Stop trusting an `org` header for JWT-authenticated requests. Use signed JWT `org_id`, then validate `Profile(user, org, is_active=True)`.
- Enable org middleware after authentication is settled.
- Set project-level default permissions for authenticated, org-scoped APIs, then explicitly opt out only for public endpoints such as login/register/public lead capture.

### 3. Generic Comments And Attachments Are Half-Migrated

`common.models.Comment` and `common.models.Attachments` correctly use `content_type`, `object_id`, and `content_object`. They also include `org` and `clean()` checks to prevent cross-org references. That is good design direction.

The rest of the code does not use it consistently:

- Account views save `account_id=...` or `attachment.account = ...`.
- Contact views save `contact_id=...` or `attachment.contact = ...`.
- Lead views save `lead_id=...` or `attachment.lead = ...`.
- Opportunity views save `opportunity_id=...` or `attachment.opportunity = ...`.
- Case views save `case_id=...` or `attachment.case = ...`.
- Task views save `task_id=...` or `attachment.task = ...`.
- Invoice views save `invoice_id=...` or `attachment.invoice = ...`.

Those fields do not exist on the generic models.

Solution:

- Add a shared service, for example `common/services/interactions.py`, with:
  - `create_comment(target, profile, text)`
  - `create_attachment(target, profile, uploaded_file, file_name=None)`
  - `comments_for(target, org)`
  - `attachments_for(target, org)`
- Optionally add `GenericRelation` fields on target models if serializers should use reverse relation names.
- Replace every app-specific comment/attachment branch with the shared service.
- Use `CommentCreateSerializer` and `AttachmentsCreateSerializer` for generic creation, or remove them if the service owns creation.

### 4. Permissions Are Duplicated And Sometimes Wrong

Every app repeats admin/creator/assignee checks manually. Some checks compare `Profile` to `User`, so they can never pass correctly.

Examples:

- `request.profile == obj.created_by` is wrong when `created_by` is a `User`.
- Some delete/update endpoints fetch attachments by `pk` only and do not filter `org`.
- Company detail endpoints in `leads.views` fetch by `pk` only and do not verify org ownership.
- `common.permissions` has useful classes, but the views mostly do not use them.

Solution:

- Standardize permissions with `IsAuthenticated`, `HasOrgContext`, `IsOrgMember`, and an object permission class.
- Move access filtering into `get_queryset()` or a shared `OrgViewMixin`.
- Use `get_object_or_404(Model, pk=pk, org=request.profile.org)` or equivalent in every org-scoped endpoint.
- Add tenant-isolation tests for every app: org A user cannot list, read, mutate, comment, attach, or delete org B data.

### 5. Serializers And Views Carry Too Much Business Logic

The views manually parse M2M lists, create tags, assign teams/users, create converted records, move comments/attachments, create invoice history, and schedule emails. Most of that belongs in serializers/services and should run inside `transaction.atomic()`.

Solution:

- Use DRF serializers with `context={"request": request}` instead of custom `request_obj` kwargs.
- Use `PrimaryKeyRelatedField(queryset=...)` scoped by org for `assigned_to`, `teams`, `contacts`, `tags`, and `accounts`.
- Use service functions for complex workflows:
  - lead conversion
  - invoice total calculation/history
  - assignment notification
  - tag get-or-create
  - generic comment/attachment creation
- Wrap multi-model writes in `transaction.atomic()` and schedule Celery notifications with `transaction.on_commit()`.

### 6. Celery Is Not Integrated Correctly

Each app creates `app = Celery("redis://")` instead of using `crm.celery.app` or `@shared_task`. Several tasks import missing models or use wrong types. `backend/crm/__init__.py` is empty, so the project Celery app is also not exposed through the standard Django/Celery discovery pattern.

Solution:

- Replace per-module `Celery("redis://")` with `@shared_task`.
- Keep Celery configuration only in `crm/celery.py`.
- Add `from .celery import app as celery_app` and `__all__ = ("celery_app",)` to `crm/__init__.py`.
- Centralize assignment-email behavior so accounts/contacts/leads/opportunities/cases/tasks/invoices do not duplicate nearly identical functions.
- Pass `org_id` into tasks that query org-scoped tables and set RLS context when RLS is enabled.
- Add Celery eager tests using real current models.

### 7. Migrations And Schema Are Missing

No app has generated migrations. That makes the current schema undefined, and any old database may not match the current model code.

Solution:

- Do not generate migrations until the model field drift is resolved.
- After cleanup, run `makemigrations` once per app and review the generated schema carefully.
- Add data migrations only for intentional old-to-new field moves.
- Keep the Prisma migration command separate from core app migrations.

### 8. API Key Authentication Is A Critical Security Risk

`common.external_auth.CustomDualAuthentication` maps an org API key to the first active admin profile in that org. That means possession of the org key becomes full admin impersonation. The risk is made worse because `OrganizationSerializer` exposes `api_key` in normal serialized output.

Solution:

- Store API keys hashed, not plaintext.
- Return raw API keys only once at creation or rotation time.
- Replace admin impersonation with a dedicated service principal/API key model.
- Scope API keys by allowed endpoint/action and org.
- Audit every API-key request.

### 9. Old User Contract Still Leaks Through The Code

The current `User` model is email-centric, while older code still references `username`, `role`, `has_sales_access`, `has_marketing_access`, `first_name`, `last_name`, and `file_prepend`.

Solution:

- Remove `jwt_payload_handler` phantom fields or add explicit profile-derived claims.
- Delete or rewrite `common/access_decorators_mixins.py` if the project is API-only.
- Update template tags and tasks to use `Profile` for role/access and `User.email` for identity.

### 10. Settings Are Development-Open

The settings file has development defaults that should not survive into production: `DEBUG = True`, wildcard hosts, wildcard CORS/CSRF trust, duplicate `DEFAULT_AUTO_FIELD`, import-time print output, and very long refresh-token lifetime.

Solution:

- Move environment-specific settings into explicit dev/prod modules or a typed settings loader.
- Fail fast with readable errors for required environment variables.
- Restrict CORS, CSRF trusted origins, and allowed hosts by environment.
- Shorten refresh-token lifetime or add rotation/revocation policy.

## App And Module Review

## `crm`

### `settings.py`

Issues:

- `DEBUG = True`, `ALLOWED_HOSTS = ["*"]`, `CORS_ORIGIN_ALLOW_ALL = True`, and wildcard `CSRF_TRUSTED_ORIGINS` are not production-safe.
- `REST_FRAMEWORK` does not set `DEFAULT_PERMISSION_CLASSES`; this should not be left to every individual view.
- Required environment variables are accessed with `os.environ[...]`; missing values crash startup without a clear validation message.
- Business apps are commented out while their URLs are still included.
- `GetProfileAndOrg` and `RequireOrgContext` middleware are commented out, so most views that expect `request.profile`/`request.org` depend on authentication side effects.
- `print(">>> ENV_TYPE", ENV_TYPE)` should be logging, not import-time output.
- `DEFAULT_AUTO_FIELD` is declared twice with different values.
- JWT refresh tokens last 365 days without a clearly wired rotation/revocation story.

Solution:

- Split settings into `base.py`, `dev.py`, and `prod.py` or use a typed settings loader.
- Install only working apps, then add the rest back one app at a time.
- Enable org middleware only after JWT org claims and API-key auth are fixed.
- Replace security wildcards with explicit env-configured origins/hosts.
- Add default authenticated/org-context permissions, then explicitly mark public endpoints with `AllowAny`.

### `urls.py` And `common.app_urls`

Issues:

- Top-level `api/` includes `common.app_urls`, which includes disabled apps.
- `common.urls` has no active `urlpatterns`.
- Boards are defined in `tasks.urls` as `board_urlpatterns` but never included.

Solution:

- Make URL registration match `INSTALLED_APPS`.
- Restore common API endpoints or remove the dead include.
- Include board routes under a stable prefix such as `/api/boards/`.

## `common`

### `models.py`

Strengths:

- `Org`, `Profile`, `Teams`, `Activity`, `Comment`, and `Attachments` provide a reasonable foundation.
- `Comment.clean()` and `Attachments.clean()` validate that the generic target belongs to the same org.
- UUID primary keys are consistent across current models.

Issues:

- `User` has only email/profile fields, but older code expects `username`, `role`, `has_sales_access`, `has_marketing_access`, `first_name`, `last_name`, and `file_prepend`.
- `Comment.get_files()` filters `comment_id=self`; it should filter by `comment=self` or `comment_id=self.id`.
- `Address.org` is required, but invoice serializers/forms create addresses without setting `org`.
- `Tags` uniqueness is by `(slug, org)`, but many views create tags without `org`.
- `Activity` stores `entity_type` and `entity_id` manually while comments/attachments use `ContentType`. That is inconsistent.
- Importing `SecurityAuditLog` at the bottom of `common.models` is a workaround for model discovery. It works, but it hides a model in a non-model module.

Solution:

- Move `SecurityAuditLog` into `common.models` or a real `audit` app.
- Add `GenericRelation` fields to entity models if reverse serializer fields are desired.
- Use `BaseOrgModel` consistently across org-scoped models.
- Remove all old `User` role/access assumptions; use `Profile`.
- Either delete `jwt_payload_handler` or rewrite it to emit only real `User` fields plus explicit current-profile claims.

### `base.py` And `mixins.py`

Issues:

- `common.mixins` imports `models` from `common.models`, creating an odd circular import path. It should import `from django.db import models`.
- `BaseOrgModel` exists but most org-scoped models still inherit `BaseModel` and define `org` manually.
- `OrgViewMixin` and permission helpers are mostly unused.
- `BaseModel.save()` sets `updated_by` even during create after setting `created_by`, so newly created records also get `updated_by`.

Solution:

- Fix `common.mixins` imports.
- Change `BaseModel.save()` so `updated_by` is assigned only on updates; new rows should keep `updated_by=None` unless a different audit contract is chosen deliberately.
- Move all org-scoped models to `BaseOrgModel` where practical.
- Use the org mixins in views or remove them and rely on DRF generic view base classes.

### `serializer.py`

Issues:

- `OrganizationSerializer` exposes `api_key`, which is too sensitive for ordinary org list/detail responses.
- `CommentSerializer` is used for creation in many views, but it has `content_type` read-only and no reliable way to attach to a target object.
- `CommentCreateSerializer` and `AttachmentsCreateSerializer` are closer to the generic design but not used by app views.
- `ActivitySerializer` comment says `get_action_display` is missing, but Django choice fields provide it. The comment is stale.
- `TeamCreateSerializer.validate_name()` checks global team name uniqueness on create instead of org-scoped uniqueness.
- `DocumentCreateSerializer` assumes `request_obj.profile.org` exists and will crash if middleware/auth has not set it.

Solution:

- Replace app-level comment/attachment creation with shared service functions.
- Split org serializers into public/read output and private/admin API-key management.
- Use serializer context for request/org/profile.
- Scope all uniqueness checks to `org`.

### `external_auth.py` And Middleware

Issues:

- `CustomDualAuthentication` still reads `request.headers["org"]` for JWT requests, which allows org spoofing if the user has a valid token.
- `GetProfileAndOrg` has the safer JWT `org_id` flow, but it is disabled in `settings.py`.
- API key auth maps an org key to the first admin profile; there is no API key permission model.
- `OrganizationSerializer` exposes `api_key`, so callers can receive long-lived org credentials through normal org serialization.
- Exceptions in JWT middleware are swallowed broadly, which can hide stale or invalid tokens.

Solution:

- Make JWT `org_id` claims mandatory for org-scoped endpoints.
- Keep org-switch as the only way to mint a token for another org.
- Introduce an `APIKey` model if public integrations need non-user credentials.
- Hash API keys at rest and make key fields write-only except at creation/rotation.
- Use middleware + permission classes together: middleware sets context, permissions enforce context.

### `tasks.py` And `token_generator.py`

Issues:

- `common/tasks.py` does not parse.
- It imports `account_activation_token`, but `token_generator.py` defines `account_acitvation_token`.
- It references `User.username` and `user.has_marketing_access`, which do not exist.
- `send_email_user_delete()` uses `html_context`, which is undefined.
- `remove_users()` uses `removed_users.list`, which is undefined.

Solution:

- Fix syntax first.
- Convert all tasks to `@shared_task`.
- Replace username mentions with email/profile-based mentions.
- Add unit tests for activation, reset, mention, team update, and user status tasks.

### `rls` And Management Commands

Issues:

- RLS SQL helpers are useful but not wired into migrations or active middleware.
- `manage_rls.py --test` queries `SELECT id FROM company LIMIT 2`, but orgs live in `organization`.
- RLS setup includes all org-scoped tables, but current app install state means several tables may not exist.
- `migrate_from_prisma.py` is a large ETL script coupled to current models; it imports every app, so it is fragile while apps are disabled/broken.

Solution:

- Fix application-level org isolation first.
- Add migration-managed RLS policies only after schema stabilizes.
- Make `migrate_from_prisma.py` idempotent, covered by fixtures, and run only in controlled staging.

## `accounts`

### `models.py`

Issues:

- `Account.contacts` is commented out, but `contact_values`, serializers, views, and migration code still use it.
- `AccountEmail.recipients` is commented out, but `save()`, serializers, tasks, and tests still use it.
- `AccountEmailLog.contact` is commented out, but `save()`, serializers, tasks, and tests still use it.
- Email models use `org`, which is good, but the code that populates org depends on removed relationships.

Solution:

- Decide whether account-contact and account-email-recipient relationships are part of the product.
- If yes, restore them explicitly with correct `Profile`/`Contact`/`Org` constraints.
- If no, remove account email endpoints, serializers, tasks, tests, and properties that reference them.

### `serializer.py`

Issues:

- `TagsSerailizer` is misspelled.
- `AccountSerializer` exposes `contacts` and `account_attachment`, neither of which exists on `Account`.
- `EmailLogSerializer` exposes `contact`, which does not exist on `AccountEmailLog`.
- `AccountWriteSerializer` exposes `contacts` and `account_attachment`, which do not exist.
- Read serializers are deeply nested and will create N+1 query problems without matching queryset prefetches.

Solution:

- Fix field names or add the missing relationships.
- Separate list/detail/write serializers.
- Add org-scoped M2M fields with explicit querysets.

### `views.py`

Issues:

- Imports serializers/models from contacts, leads, opportunity, tasks, and invoices, causing import failures when those apps are disabled.
- Manually parses JSON strings for M2M fields instead of accepting real JSON lists or serializer fields.
- Creates tags without setting `org`.
- Creates attachments by assigning `attachment.account`, which does not exist.
- Creates comments with `account_id=...`, which does not exist on `Comment`.
- Permission checks compare `Profile` to `User` in places.
- Email creation overwrites `data = {}` after reading request values, so recipient handling becomes dead code.
- No `transaction.atomic()` around multi-step create/update flows.

Solution:

- Reduce cross-app imports in list/detail contexts or move summaries behind optional services.
- Use serializers for M2M validation.
- Replace comment/attachment handling with shared generic service.
- Move email creation into a dedicated service and fix the missing recipient model decision.

### `tasks.py` And Tests

Issues:

- `send_email()` and `send_scheduled_emails()` reference `Email` and `EmailLog`, but the actual models are `AccountEmail` and `AccountEmailLog`.
- Tests import `Email` and `AccountCreateTest`, neither of which exists.

Solution:

- Rename imports and tests to current model names or remove the stale account-email feature.
- Add eager Celery tests after the model contract is fixed.

## `contacts`

### `models.py`

Strengths:

- The current `Contact` model is relatively coherent and uses flat address fields plus `org`.

Issues:

- There is no uniqueness constraint for `(email, org)`, even though serializer validation enforces it.
- `contact_attachment` is commented as needed but not implemented.

Solution:

- Add `UniqueConstraint(fields=["email", "org"], condition=...)` if duplicate emails per org should be blocked.
- Add `GenericRelation(Attachments)` and `GenericRelation(Comment)` only if you want reverse serializer fields.

### `serializer.py`

Issues:

- `ContactSerializer` exposes `contact_attachment`, but the model has no such relation.
- `get_country()` calls `get_country_display()` even when country is blank/null.

Solution:

- Remove `contact_attachment` from the serializer or add proper `GenericRelation`.
- Return `None` when country is empty.

### `views.py`

Issues:

- `from contacts.models import Contact, Profile` is invalid; `Profile` is in `common.models`.
- City filtering uses `address__city__icontains`, but `Contact` has flat `city`.
- Detail view references `contact_obj.account_contacts`, but `Account.contacts` is commented out.
- Delete references `self.object.address_id`, but `Contact` has no `address`.
- Comments are saved with `contact_id` and attachments with `attachment.contact`, neither of which exists.
- `ContactDetailView.post()` gets `Contact.objects.get(pk=pk)` without org filtering.
- Assignment notification diff is calculated after reassignment, so it can become empty.

Solution:

- Fix imports and flat-field filters.
- Remove dead account/address references or restore those relationships.
- Use org-scoped object fetching everywhere.
- Use shared generic comment/attachment service.

### `tasks.py` And Tests

Issues:

- Assignment email task duplicates the same logic used in other apps.
- Tests inherit from `ContactObjectsCreation`, which is not imported and does not exist in `contacts/tests.py`.

Solution:

- Replace duplicate task with shared notification service.
- Build current fixtures around `Org`, `User`, `Profile`, and `Contact`.

## `leads`

### `models.py`

Strengths:

- The `Lead` model has a clear sales workflow and uses `org`, assignments, teams, tags, contacts, and company.

Issues:

- `Company` is a lead company/account-like model, while `Org` is the tenant. The old code also uses a database table named `company`, which creates semantic confusion.
- There are no generic reverse relations for comments/attachments despite serializer fields expecting them.

Solution:

- Consider renaming lead `Company` to `LeadCompany` or replacing it with `Account` if it represents the same concept.
- Add or remove generic reverse fields consistently.

### `serializer.py`

Issues:

- `LeadSerializer` exposes `lead_attachment` and `lead_comments` without model relations.
- `LeadCreateSerializer` requires `request_obj.profile.org`; it will crash without active org context middleware/auth.
- `CompanySerializer` allows `org` as a normal field.

Solution:

- Use serializer context.
- Make org read-only and set it from `request.profile.org`.
- Remove unused imports and invalid reverse fields.

### `views.py`

Issues:

- Duplicate imports indicate merge/refactor residue.
- `post()` prints `test`.
- Name search uses `first_name AND last_name`; usually it should be OR or full-name search.
- Attachments/comments use old fields (`attachment.lead`, `lead_id`).
- Create conversion path references `self.lead_obj.id` even though only `lead_obj` exists.
- Old conversion code sets `billing_address_line`, `billing_street`, etc. on `Account`, but the current `Account` model has flat `address_line`, `city`, `state`, `postcode`, and `country`.
- There are two conversion implementations: old create/put conversion and newer `patch()` conversion.
- `CreateLeadFromSite` adds `User` objects to M2M fields that expect `Profile`.
- `CompanyDetail` fetches by `pk` without org filtering and can expose cross-org data.

Solution:

- Keep one lead conversion path, implemented as a transaction-safe `LeadConversionService`.
- Move comments/attachments using generic service.
- Fix public lead creation to assign `Profile`, not `User`.
- Scope company detail/update/delete to `org`.

### `forms.py`

Issues:

- CSV validation is minimal and uses broad exception handling with `print(e)`.
- Required headers only include `title`, while task creation expects email/phone/address fields.

Solution:

- Define a clear CSV contract and return structured row-level errors.
- Validate email/phone/country/status/source choices before queueing Celery work.

### `tasks.py` And Tests

Issues:

- `create_lead_from_file()` accepts five arguments, but tests call it with four.
- It assigns an `Account` object to `lead.company`, which expects `Company`.
- It assigns `lead.created_by = profile`, but `created_by` expects `User`.
- `update_leads_cache()` uses unscoped `Lead.objects.all()`.
- Tests inherit from `TestLeadModel`, which is not defined in `leads/tests.py`.

Solution:

- Fix task signatures and types.
- Pass `profile.user` to `created_by`.
- Scope tasks by org and set RLS context when enabled.

### `urls.py`

Issues:

- `path("<str:pk>/", ...)` appears before `path("upload/", ...)`, so `/api/leads/upload/` is shadowed by the detail route.
- `companies` and `company/<pk>` omit trailing slashes unlike the rest of the API.

Solution:

- Move fixed routes before dynamic `<pk>` routes.
- Normalize trailing slash style.

## `opportunity`

### `models.py`

Strengths:

- The core model is coherent: account, contacts, assigned users, teams, tags, financial fields, stage, and org are all present.

Issues:

- Stage choices are `CLOSED_WON`/`CLOSED_LOST`, but views check `"CLOSED WON"`/`"CLOSED LOST"`.
- No generic reverse relations for comments/attachments.

Solution:

- Use enum constants consistently.
- Add or remove generic reverse relation fields.

### `serializer.py`

Issues:

- `OpportunitySerializer` exposes `opportunity_attachment`, which does not exist.
- `closed_by = ProfileSerializer()` is not nullable-safe.
- Deep nested serializers can be expensive on list endpoints.

Solution:

- Use separate list/detail serializers.
- Make nullable nested fields `read_only=True, allow_null=True` where appropriate.
- Prefetch list querysets or return compact related summaries.

### `views.py`

Issues:

- `closed_on=params.get("due_date")` uses the wrong request field name.
- `closed_by` is assigned after save but not persisted in create/update flows.
- Attachments/comments use old fields (`attachment.opportunity`, `opportunity_id`).
- `get_object()` returns `None`; callers then access `.org`, causing 500s instead of 404s.
- Permission checks compare `Profile` to `User`.
- Tags are created without `org`.

Solution:

- Use `get_object_or_404`.
- Move create/update to a serializer/service with `transaction.atomic()`.
- Normalize stage constants and persist `closed_by`.
- Use generic comment/attachment service.

### `tasks.py` And Tests

Issues:

- Assignment email task duplicates app-level logic.
- Tests import `OpportunityModel` from `opportunity.tests`, causing self-import/circular invalid test structure.

Solution:

- Use shared assignment notification.
- Rebuild tests around current models.

## `cases`

### `models.py`

Strengths:

- `Case` and `Solution` are reasonable domain models.
- `Solution` has publish/unpublish methods and an org field.

Issues:

- `Case.contacts` has no explicit `related_name`, while other relationships use named reverse relations.
- No generic reverse relations for comments/attachments.

Solution:

- Add explicit related names for clarity.
- Use consistent generic relation strategy.

### `serializer.py`

Issues:

- `closed_on = serializers.DateField` is missing parentheses and is effectively not a serializer field.
- `CaseCreateSwaggerSerializer` includes `case_attachment`, which is not a model field.
- `CaseCreateSerializer` exposes `created_by`, `created_at`, `is_active`, `org`, and `created_on_arrow` in a create serializer.

Solution:

- Fix `closed_on = serializers.DateField(required=False, allow_null=True)`.
- Keep write serializers focused on writable fields only.
- Move attachments to generic service.

### `views.py`

Issues:

- Attachments/comments use old fields (`attachment.case`, `attachment.cases`, `case_id`).
- `get_object()` returns `None`; many callers access `.org` without checking.
- Delete permission compares `Profile` to `User`.
- Attachment delete fetches by `pk` only and does not filter `org`.

Solution:

- Use `get_object_or_404(..., org=request.profile.org)`.
- Use shared object permission helpers.
- Use generic interaction service.

### `solution_views.py`

Issues:

- Solution routes are shadowed in `cases/urls.py` because `<str:pk>/` comes before `solutions/`.
- Solution access requires authentication but no explicit org admin/role policy.
- List `case_count` and detail `linked_cases` can create N+1 queries.

Solution:

- Move all `solutions/` routes before `<str:pk>/`.
- Decide who can create/approve/publish solutions.
- Use `annotate(Count("cases"))` and `prefetch_related("cases")`.

### `tasks.py` And Tests

Issues:

- Imports `Profile` from `accounts.models`, but `Profile` lives in `common.models`.
- Tests inherit from undefined fixtures.

Solution:

- Fix imports and use shared notification code.
- Add real case and solution tests.

## `tasks`

### `models.py`

Strengths:

- The app now contains both classic CRM tasks and Kanban board models.
- Board, column, card, and membership concepts are useful.

Issues:

- `BoardMember` has `UniqueConstraint(fields=["user", "board"])`, but the model field is `profile`, not `user`.
- Classic `Task` has no generic reverse relations despite serializer fields expecting `task_attachment` and `task_comments`.
- Kanban and classic task concepts are mixed in one app without a clear API boundary.

Solution:

- Change the constraint to `fields=["profile", "board"]`.
- Separate Kanban serializers/views/URLs from classic tasks within the app.
- Decide whether board tasks and CRM tasks should remain separate models or share a base concept.

### `serializer.py`

Issues:

- `TaskSerializer` exposes `task_attachment` and `task_comments` without model relations.
- Board serializers use `fields = "__all__"` and may expose more than the API should promise.
- `task_count`, `member_count`, and `column_count` can produce N+1 queries.

Solution:

- Use explicit API fields.
- Annotate/prefetch counts in view querysets.
- Move classic task comments/attachments to generic service.

### `views.py`

Issues:

- Classic task comment/attachment logic uses old fields.
- `TaskDetailView.post()` fetches `Task.objects.get(pk=pk)` without org filtering.
- `TaskDetailView.get_context_data()` returns all teams with `Teams.objects.all()`.
- Board views are better structured than older views but are unreachable because `board_urlpatterns` are not included.
- Board member delete/update policies are minimal; any member can delete a board task.

Solution:

- Fix org filtering and generic interactions in classic task endpoints.
- Include board URLs under `/api/boards/`.
- Add role-specific board permissions and ordering/move tests.

### `swagger_params.py`

Issue:

- Syntax error at line 25.

Solution:

- Add the missing comma and flatten parameter lists.
- Move shared org OpenAPI parameter definitions into one common module.

### `celery_tasks.py` And Tests

Issues:

- Imports `Email` from `accounts.models`, but there is no `Email` model.
- Uses templates/namespaces that may not exist.
- Tests are placeholders.

Solution:

- Remove unused imports.
- Use `@shared_task`.
- Add classic task assignment notification tests after the model API is fixed.

## `invoices`

### `models.py`

Strengths:

- Invoice, history, product, and line-item models show a useful direction.
- Line items calculate totals and carry org.

Issues:

- `Invoice.invoice_number` is a `CharField`, but the generator returns integers.
- Invoice number uniqueness is enforced by a while loop but not by a DB constraint.
- `formatted_*` helpers concatenate `None` currency values.
- `InvoiceHistory` overrides `updated_by` from `BaseModel` with a `Profile` FK, while `created_by` remains a `User` FK. That is confusing and easy to misuse.
- Invoice totals are calculated in views, not in a domain method/service.
- Current create/update code converts money through `float(...)`, so `DecimalField` values can pick up rounding errors.
- `Address` records require `org`, but invoice view serializers create addresses without it.

Solution:

- Add a real unique invoice-number strategy scoped by org.
- Move total/tax calculation to model/service and keep all money math in `Decimal` with explicit rounding.
- Rename history actor fields clearly, e.g. `changed_by_profile`, or keep inherited `updated_by` as `User`.
- Ensure address creation always sets `org`.

### `serializer.py` And `serializers.py`

Issues:

- There are two serializer modules: `serializer.py` and `serializers.py`.
- `InvoiceSerailizer` and `InvoiceSwaggerSerailizer` are misspelled.
- `serializer.py` uses `ProfileSerializer` for `created_by`, but `created_by` is a `User`.
- `InvoiceSwaggerSerailizer` includes `quality_hours`, which is not a model field.
- The newer `serializers.py` has better write fields (`assigned_to_ids`, `account_ids`, `team_ids`) but is not used by `api_views.py`.

Solution:

- Keep one final module, preferably `invoices/serializers.py`, after switching imports and porting the useful write-field design from the unused module.
- Rename serializers correctly.
- Use explicit list/detail/write serializers.
- Support line items in the API or remove line-item models until exposed.

### `api_views.py`

Issues:

- Uses `company`, `request.company`, and `request.user.role` throughout.
- Saves `company=request.company` into `Invoice`, but `Invoice` has no `company` field.
- Filters `User`, `Teams`, and `Account` by `company`, but those models use `org`.
- Creates addresses without `org`.
- Calculates totals, discounts, tax, and balances with `float(...)` instead of `Decimal`.
- Returns `Response({"error": True}, data)`, where `data` is incorrectly passed as the status argument.
- Calls `send_email.delay(recipients, invoice_obj.id, ...)`, but task signature is `send_email(invoice_id, recipients, ...)`.
- Comments and attachments use old fields (`invoice_id`, `attachment.invoice`).
- Detail endpoints can access `.company` on `None` if the invoice is not found.

Solution:

- Rewrite invoice APIs around `request.profile.org`.
- Use `InvoiceSerializer` from `serializers.py` as the starting point, not the older misspelled serializers.
- Add org-scoped account/team/profile querysets.
- Use `Decimal`/`quantize()` for all currency calculations.
- Move totals/history/email into services and transactions.

### `forms.py`

Issues:

- Still uses `request_user.role`, `company=request_obj.company`, and `Account.status="open"`, none of which match current models.
- Comment and attachment forms reference `task` fields on generic models.

Solution:

- Delete form code if the backend is API-only.
- If admin/server-rendered forms are still needed, refactor them to `org`/`Profile` and generic comments/attachments.

### `tasks.py` And Tests

Issues:

- URL reversing uses namespace `invoices:invoice_details`, but the app namespace is `api_invoices` and no route is named `invoice_details`.
- `invoice.accounts.filter(status="open")` references `Account.status`, which does not exist.
- `create_invoice_history()` loads a `User` for a field that is currently a `Profile` on `InvoiceHistory`.
- Tests inherit from undefined `InvoiceCreateTest`.

Solution:

- Fix namespace names or use a configured frontend URL builder.
- Use profile recipients for assignment emails.
- Add tests for total calculation, history creation, email task signatures, and tenant isolation.

## Admin, Templates, And Miscellaneous

Issues:

- `common/admin.py` registers only a subset of important models.
- Several admin classes assume fields that may not exist after cleanup.
- Email templates exist, but task code references some names that are not present.
- `backend/main.py` is a placeholder from project scaffolding.
- `backend/README.md` is empty.

Solution:

- Update admin after models stabilize.
- Add a real README with setup, env vars, commands, and API/auth flow.
- Remove placeholder files if unused.

## High-Priority Quick Reference After Claude Comparison

| Priority | Problem | First fix |
|---|---|---|
| 1 | URLConf includes disabled apps and empty `common.urls` | Sync `INSTALLED_APPS` with URL includes and restore/remove `common.urls` |
| 2 | Common auth/org HTTP surface is missing | Implement or explicitly remove the commented common URL contract |
| 3 | No project default permissions | Add authenticated/org-context defaults and mark public endpoints explicitly |
| 4 | API key grants admin impersonation and is serialized | Replace with hashed scoped credentials and hide keys from normal serializers |
| 5 | Generic comments/attachments still use phantom FKs | Add shared generic relation helpers and migrate every app to them |
| 6 | `User`/`Profile` contract is mixed | Keep identity on `User`; keep role/access/org membership on `Profile` |
| 7 | Celery apps are disconnected | Use `@shared_task` and expose `celery_app` from `crm/__init__.py` |
| 8 | `BaseModel.save()` audit behavior is wrong on create | Assign `updated_by` only on updates |
| 9 | Invoice money/email/response paths are incorrect | Use `Decimal`, fix `Response()` calls, and align Celery task args |
| 10 | Production settings are development-open | Env-drive `DEBUG`, hosts, CORS/CSRF, token lifetime, and duplicate defaults |

## Recommended Refactor Plan

### Phase 0: Freeze Scope And Choose Contracts

Decisions to make before coding:

- `Org` is the tenant; there is no `Company` tenant.
- `Profile` is the membership/role/access object; `User` only authenticates.
- Keep generic comments/attachments, but finish the refactor everywhere.
- Decide whether Account has Contacts and AccountEmail has Recipients. Either restore those relationships or remove that feature from API/tasks/tests.
- Decide whether `leads.Company` should stay or be merged into `Account`.

### Phase 1: Make The Project Importable

Tasks:

- Fix syntax errors in `common/tasks.py`, `common/token_generator.py`, and `tasks/swagger_params.py`.
- Add the standard Celery app export to `crm/__init__.py`.
- Align `INSTALLED_APPS` and URL includes.
- Restore or remove `common.urls`; if restored, add the minimal auth/org/profile views it advertises.
- Temporarily disable endpoints for apps that still fail imports.
- Fix broken test imports enough that the test runner can collect the suite.
- Run `python manage.py check` until it passes.

Exit criteria:

- `manage.py check` passes.
- Importing every installed URL module succeeds.
- OpenAPI schema generation runs.

### Phase 2: Normalize Tenancy And Authentication

Tasks:

- Add project-level `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` for authenticated org APIs.
- Replace all `request.company` and `company=` usage with `request.profile.org` and `org=`.
- Replace all `request.user.role/access` checks with `request.profile`.
- Fix `BaseModel.save()` so `updated_by` is not set during creation.
- Enable `GetProfileAndOrg`.
- Remove JWT org-header trust from `CustomDualAuthentication`.
- Remove phantom `User` fields from `jwt_payload_handler`, decorators, template tags, and tasks.
- Replace org API-key admin impersonation with hashed, scoped API credentials or an explicit service principal.
- Split org API-key serialization so keys are not exposed in normal org responses.
- Apply `HasOrgContext` and object permissions to every org-scoped endpoint.

Exit criteria:

- Every org-scoped query has an org filter.
- Cross-org object access returns 404/403 consistently.
- Org context comes from signed token/API key, not a mutable client header.

### Phase 3: Finish Generic Comments And Attachments

Tasks:

- Add shared create/list/delete helpers for generic comments and attachments.
- Replace all `*_id=` and `attachment.* = target` old field writes.
- Decide whether to add `GenericRelation` on Account, Contact, Lead, Opportunity, Case, Task, and Invoice.
- Update serializers accordingly.

Exit criteria:

- Comment and attachment creation works for every entity.
- Cross-org generic references are rejected.
- Entity detail endpoints return comments/files consistently.

### Phase 4: Refactor Each App API

Order:

1. `contacts` because its model is simplest.
2. `accounts` after deciding account-contact/email relationships.
3. `leads` because conversion depends on accounts and contacts.
4. `opportunity`.
5. `cases` and `solutions`.
6. `tasks` and boards.
7. `invoices`.

Tasks per app:

- Use DRF generic views or viewsets.
- Implement `get_queryset()` with org/role filtering.
- Use focused list/detail/write serializers.
- Move business workflows into services.
- Add `transaction.atomic()` around multi-model writes.
- Schedule email tasks with `transaction.on_commit()`.

### Phase 5: Rebuild Tests

Tasks:

- Create factories/fixtures for `Org`, `User`, `Profile`, Teams, and each entity.
- Add import/smoke tests for all URLs.
- Add serializer tests for validation and org-scoped uniqueness.
- Add API tests for list/create/detail/update/delete per app.
- Add cross-org isolation tests.
- Add Celery eager tests for notification/history tasks.
- Add lead conversion and invoice total/history workflow tests.

Exit criteria:

- Tests do not import undefined fixture classes.
- Tests fail before a tenant leak reaches production.

### Phase 6: Schema, RLS, And Migration

Tasks:

- Generate initial migrations after model cleanup.
- Add database constraints for org-scoped uniqueness and required fields.
- Fix `manage_rls.py` to use `organization`.
- Add RLS migrations only after app-level org tests pass.
- Run `migrate_from_prisma.py` against a fixture/staging database and compare row counts.

Exit criteria:

- Fresh database can be created from migrations.
- RLS status command reports expected tables.
- Prisma migration has repeatable dry-run output.

### Phase 7: Documentation And CI

Tasks:

- Write `backend/README.md` with setup, env vars, migrations, tests, Celery, Redis, and PostgreSQL requirements.
- Add `.env.example`.
- Add CI steps: formatting/linting, `python -m compileall` or `ruff`, `manage.py check`, migrations check, and tests.
- Decide on one dependency source: `pyproject.toml`/`uv.lock` or `requirements.txt`.

## Practical First Pull Requests

1. Fix syntax errors and token generator naming.
2. Make `INSTALLED_APPS` match URL includes or remove disabled app routes.
3. Add the Celery app export in `crm/__init__.py` and convert the first broken task module to `@shared_task`.
4. Restore a minimal `common.urls`/`common.views` auth-org surface or remove its include.
5. Add default DRF permissions plus a `HasOrgContext` enforcement path.
6. Replace API-key admin impersonation and stop serializing raw org API keys.
7. Replace `request.company` in invoices or temporarily disable invoice URLs.
8. Add a generic comment/attachment service and migrate one simple app (`contacts`) to prove the pattern.
9. Add factories and tenant-isolation tests for `contacts`.
10. Repeat the same pattern for accounts, leads, opportunities, cases, tasks, and invoices.

## Final Assessment

The codebase has useful pieces, but it is not a clean Django CRM yet. The main issue is not just style or DRY. The system has contradictory contracts: `company` versus `org`, `User` versus `Profile`, explicit comment/attachment fields versus generic relations, enabled URLs versus disabled apps, and old tests versus current models.

The correct solution is to stabilize the contracts first, then refactor app by app with tests. Once that foundation is fixed, the duplicated CRUD code can be reduced substantially with DRF generics, shared org-aware serializers, shared assignment/tag/comment/attachment services, and centralized permission classes.
