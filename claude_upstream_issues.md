# Upstream issues to raise (MicroPyramid/Django-CRM)

Issues found while adopting the upstream backend that need an upstream decision
before we implement, or upstream bugs worth reporting. Each entry is written so it
can be pasted into a GitHub issue.

---

## 1. Task create — test asserts unique task titles per org, but no such rule exists

**Type:** question / test-vs-behavior mismatch
**Files:** `tasks/tests/test_tasks_api.py::TestTaskListView::test_create_task_duplicate_title_returns_400`,
`tasks/views/task_views.py` (`TaskListView.post`), `tasks/models.py` (`Task`)

### Summary
The test asserts that creating a second task with the same `title` in the same org
returns **400**:

```python
def test_create_task_duplicate_title_returns_400(self, admin_client, admin_user, org_a):
    Task.objects.create(title="Unique Title", status="New", priority="Low",
                        org=org_a, created_by=admin_user)          # 1st, via ORM
    response = admin_client.post("/api/tasks/",                     # 2nd, via API
                                 {"title": "Unique Title", "status": "New", "priority": "Low"},
                                 format="json")
    assert response.status_code == 400
    assert response.json()["error"] is True
```

But **nothing enforces uniqueness**:
- `Task` has no `unique` / `UniqueConstraint` on `title` (only the Board/pipeline
  models have unique constraints).
- `TaskListView.post` does not check for an existing title before creating.

So the test **fails** against the current code — it asserts intended-but-
unimplemented behavior.

### Question for upstream
Is **unique task title per org** actually intended? It is an unusual constraint —
task lists commonly repeat titles ("Follow up", "Call client", …). If it is *not*
intended, the test should be removed/rewritten; if it *is*, it needs to be
implemented.

### Options
1. **Remove/rewrite the test** — if duplicate titles are allowed by design.
2. **Enforce in the view** — reject a duplicate title on create with 400. Light,
   but doesn't cover rename (PUT/PATCH) or ORM/import, and is race-prone (no lock).
3. **Enforce at the DB** — `UniqueConstraint(fields=["org", "title"])` migration.
   Strongest (covers every write path), but blocks ORM/import too and needs a
   data-dedup step for existing rows.

### How the fork handles it for now
Not enforcing uniqueness (option 1 direction). The test is marked
`@pytest.mark.xfail` (referencing this file) so the suite stays green while the
intended-but-unimplemented behavior stays documented. If upstream decides to
enforce it, drop the xfail and implement option 2 or 3.

<details>
<summary>The view-level check we prototyped, then reverted</summary>

```python
# TaskListView.post — reverted
if params.get("title") and Task.objects.filter(
    org=request.profile.org, title=params.get("title")
).exists():
    return Response(
        {"error": True, "errors": "A task with this title already exists."},
        status=status.HTTP_400_BAD_REQUEST,
    )
```
</details>
