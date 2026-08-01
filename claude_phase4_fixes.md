# Phase 4 — correctness, contract & test-reconciliation fixes

Applied on `adopt-upstream`, on top of Phase 3. Non-security remainder of
`backend/docs/bug_list.md` plus getting the suite green. One commit per bug (or
per tight group); recorded here for the planned upstream PR.

Phase 2 baseline: 50 failed / 1986 passed. After Phase 3: 16 failed / 2033 passed.

## Group 0 — test reconciliation

### 14 `test_*_unauthenticated` expectations (test bug, not app bug)
The app **correctly** denies anonymous requests with a **403** (the org-context
middleware short-circuits before DRF would emit a 401). 14 tests wrongly expected
`pytest.raises(PermissionDenied)` or `== 401` and failed. Converged them on the
convention the codebase already uses elsewhere: `assert status_code in (401, 403)`.
- Files: `test_{users,tags,dashboard,documents,settings,auth,organizations}.py`
  (common) + `test_{accounts,cases,invoices,leads,contacts,opportunities}_api.py`
  + `tasks/tests/test_tasks_api.py`.
- Upstream-relevant: **yes** (these are upstream's tests).

### task create — duplicate title (REVERTED → recorded as upstream issue)
`test_create_task_duplicate_title_returns_400` asserts a duplicate title → 400,
but no unique-title rule exists (neither the model nor the view). A view-level
check was prototyped, then **reverted** — unique task titles per org is an
unusual constraint to impose just to satisfy one test. The test is now
`@pytest.mark.xfail` and the question is written up in `claude_upstream_issues.md`
for an upstream decision. (`tasks/views/task_views.py`, `tasks/tests/test_tasks_api.py`.)

### task list — response missing form-helper metadata
`GET /api/tasks/` omitted `status`, `priority`, `accounts_list`, `contacts_list`
that the frontend list/form needs (other list views expose equivalent helpers).
Added them to the list context.
- File: `tasks/views/task_views.py`.
- Upstream-relevant: **yes.**

## Group A — endpoints that can't work at all

### bug 9 — contacts `?city` / `?assigned_to` filters
`?city` filtered on a non-existent `address__city` relation (FieldError → 500);
Contact has a flat `city` column → `city__icontains`. `?assigned_to` gated on
`getlist` but filtered with `get`, passing a string to `__in` (per-character
match) → use `getlist`. (`contacts/views.py`.)

### bug 8 — comment-append silently dropped (accounts & contacts)
Both passed a non-existent `account_id`/`contact_id` to `CommentSerializer.save()`
and required `object_id`/`org` in the body, so a plain `{"comment": …}` failed
validation and the comment was dropped while the handler returned 200. Create the
`Comment` directly with the generic FK + server-derived org/commented_by.
(`accounts/views.py`, `contacts/views.py`.)

### bug 7 — accounts `create_mail` TypeError + dropped recipients
`EmailSerializer.__init__` forwarded `request_obj` to `ModelSerializer.__init__`
(TypeError); pop it. The handler reassigned `data = {}` right after
`data = request.data`, so `recipients` were never read; use a distinct `errors`
accumulator. (`accounts/serializer.py`, `accounts/views.py`.)

### bug 15 — business-hours calendar routes
`PUT /calendar/` (no pk) 500'd on the missing positional; `GET /calendar/<pk>/`
ignored the pk and returned the default. Both methods now take an optional pk
(use it if present, else the org default). (`business_hours/views.py`.)

### bug 6 — InvoiceFromOpportunityView broken 4 ways
`title=`→`invoice_title=`, `"DRAFT"`→`"Draft"`, dropped hand-rolled numbering for
the model's `INV-YYYYMMDD-XXXX`, and fixed the `create_invoice_history` args to
match its `(id, actor_id, changed_fields, org_id)` signature.
(`invoices/api_views.py`.)

### characterization tests updated (bugs 8, 9)
Three contacts tests pinned the *buggy* behavior (`_hits_save_bug`,
`pytest.raises(FieldError/ValidationError)`); rewritten to assert the fixed
behavior. (`contacts/tests/test_contacts_api.py`.)

## Group B — wrong status codes

### bug 19 — revenue report 500 on a malformed date
`start_date`/`end_date` were parsed with a bare `strptime`, so `?start_date=notadate`
raised an uncaught `ValueError` → 500. Wrap each and return 400.
(`invoices/api_views.py`.)

### bug 13 — detail-view 403 double-wrapped
`LeadDetailView.get` / `TaskDetailView.get` re-wrapped the `Response` that
`get_context_data` returns on the permission-denied path in a second `Response`,
losing the 403 (caller saw a 200, or a `TypeError` on render). Return the
helper's `Response` directly. (`leads/views/lead_views.py`, `tasks/views/task_views.py`.)

### bug 10 — bare `.get()` 500 instead of 404
`LeadDetailView.post` did `Lead.objects.get(pk=pk)` (no org filter),
`OpportunityDetailView.post` a bare `Opportunity.objects.get` → 500 on an unknown
pk. Use `get_object_or_404` with the org. The attachment-delete sites in bug 10's
list were already covered by bugs 4/30. (`leads/…`, `opportunity/…`.)

### characterization tests updated (bugs 10, 13)
Three tests pinned the old bugs (double-wrapped `TypeError`, cross-org POST → 403);
rewritten to assert the fixed behavior (403 / 404). (`leads/tests/test_leads_api.py`,
`tasks/tests/test_tasks_api.py`.)

## Group E — dev-experience

### bug 21 — `django.server` formatter crashes on client disconnect
The formatter used percent style `[%(server_time)s]`, so `ServerFormatter`'s
`server_time` fallback never fired; the broken-pipe log path (no `server_time`)
then crashed with a KeyError on every disconnect (~40-line traceback). Use brace
style + `style="{"`. Dev-server only. (`crm/settings.py`.)
