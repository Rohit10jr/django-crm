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

### task create — duplicate title should 400
`POST /api/tasks/` with a title that already exists in the org created a second
task instead of returning 400. Added a view-level duplicate-title check (no
DB-level unique constraint exists on `title`). *Judgment call:* enforces unique
task titles per org — flag if that's not desired.
- File: `tasks/views/task_views.py`.

### task list — response missing form-helper metadata
`GET /api/tasks/` omitted `status`, `priority`, `accounts_list`, `contacts_list`
that the frontend list/form needs (other list views expose equivalent helpers).
Added them to the list context.
- File: `tasks/views/task_views.py`.
- Upstream-relevant: **yes.**
