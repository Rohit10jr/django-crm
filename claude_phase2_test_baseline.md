# Phase 2 — pytest baseline (adopt-upstream branch)

Recorded right after adopting the upstream backend and getting it to boot,
**before** Phase 3 (security) and Phase 4 (correctness) fixes. Diff future runs against this.

- Config: `crm.test_settings` — SQLite in-memory, MD5 hasher.
- RLS is Postgres-only and not exercised by the suite; RLS enforcement was verified separately (manage_rls: 51 tables ENABLED forced, crm_app non-superuser).
- Result: `=== 50 failed, 1986 passed, 16 skipped, 1450 warnings in 356.24s (0:05:56) ====`

## 50 failing tests (baseline)

- accounts/tests/test_accounts_api.py::TestAccountDetailView::test_update_account
- accounts/tests/test_accounts_api.py::TestAccountDetailView::test_update_account_clear_tags
- accounts/tests/test_accounts_api.py::TestAccountDetailView::test_update_account_with_contacts
- accounts/tests/test_accounts_api.py::TestAccountDetailView::test_update_account_with_tags_and_assigned_to
- accounts/tests/test_accounts_api.py::TestAccountDetailView::test_update_account_with_teams
- accounts/tests/test_accounts_api.py::TestAccountListView::test_create_account
- accounts/tests/test_accounts_api.py::TestAccountListView::test_create_account_unauthenticated
- accounts/tests/test_accounts_api.py::TestAccountListView::test_create_account_with_all_fields
- accounts/tests/test_accounts_api.py::TestAccountListView::test_create_account_with_tags
- accounts/tests/test_accounts_api.py::TestAccountListView::test_create_account_with_teams
- accounts/tests/test_accounts_api.py::TestAccountSerializerValidation::test_account_create_serializer_default_currency
- accounts/tests/test_accounts_api.py::TestAccountSerializerValidation::test_validate_name_update_same_name
- accounts/tests/test_accounts_api.py::TestAccountSerializerValidation::test_validate_name_update_to_new_name
- accounts/tests/test_custom_fields.py::TestAccountCreateWithCustomFields::test_create_drops_unknown_keys
- accounts/tests/test_custom_fields.py::TestAccountCreateWithCustomFields::test_create_with_valid_dropdown_value
- accounts/tests/test_custom_fields.py::TestAccountUpdateWithCustomFields::test_put_replaces_custom_fields
- cases/tests/test_audit_log.py::TestCaseSignalActivities::test_create_emits_create_activity
- cases/tests/test_cases_api.py::TestCaseListView::test_create_case_unauthenticated
- common/tests/test_auth.py::TestGoogleOAuthCallbackView::test_successful_oauth_new_user
- common/tests/test_auth.py::TestProfileDetailView::test_profile_detail_unauthenticated
- common/tests/test_dashboard.py::TestDashboardView::test_dashboard_unauthenticated
- common/tests/test_documents.py::TestDocumentListView::test_unauthenticated
- common/tests/test_magic_link.py::TestMagicLinkVerify::test_verify_marks_token_used
- common/tests/test_magic_link.py::TestMagicLinkVerify::test_verify_new_user_no_org
- common/tests/test_magic_link.py::TestMagicLinkVerify::test_verify_replay_attack_prevented
- common/tests/test_magic_link.py::TestMagicLinkVerify::test_verify_valid_token_new_user
- common/tests/test_magic_link.py::TestMagicLinkVerifyCode::test_verify_code_marks_used
- common/tests/test_magic_link.py::TestMagicLinkVerifyCode::test_verify_code_replay_rejected
- common/tests/test_magic_link.py::TestMagicLinkVerifyCode::test_verify_code_valid_new_user
- common/tests/test_organizations.py::TestOrgProfileCreateView::test_list_orgs_unauthenticated
- common/tests/test_settings.py::TestDomainListView::test_unauthenticated
- common/tests/test_tags.py::TestTagsListView::test_unauthenticated
- common/tests/test_teams.py::TestTeamsDetailView::test_update_team
- common/tests/test_teams.py::TestTeamsDetailView::test_update_team_with_users
- common/tests/test_users.py::TestUserDetailView::test_delete_user_as_admin
- common/tests/test_users.py::TestUsersListView::test_list_users_unauthenticated
- contacts/tests/test_contacts_api.py::TestContactListView::test_create_contact_unauthenticated
- contacts/tests/test_custom_fields.py::TestContactCreateWithCustomFields::test_create_drops_unknown_keys
- contacts/tests/test_custom_fields.py::TestContactCreateWithCustomFields::test_create_with_valid_dropdown_value
- contacts/tests/test_custom_fields.py::TestContactUpdateWithCustomFields::test_put_replaces_custom_fields
- invoices/tests/test_invoices_api.py::TestInvoiceListView::test_create_invoice_unauthenticated
- leads/tests/test_leads_api.py::TestLeadListView::test_create_lead_unauthenticated
- opportunity/tests/test_custom_fields.py::TestOpportunityCreateWithCustomFields::test_create_drops_unknown_keys
- opportunity/tests/test_custom_fields.py::TestOpportunityCreateWithCustomFields::test_create_with_valid_dropdown_value
- opportunity/tests/test_custom_fields.py::TestOpportunityUpdateWithCustomFields::test_put_replaces_custom_fields
- opportunity/tests/test_opportunities_api.py::TestOpportunityListView::test_create_opportunity_unauthenticated
- opportunity/tests/test_opportunities_api.py::TestOpportunitySerializer::test_validate_name_update_same_name_succeeds
- tasks/tests/test_tasks_api.py::TestTaskListView::test_create_task_duplicate_title_returns_400
- tasks/tests/test_tasks_api.py::TestTaskListView::test_create_task_unauthenticated
- tasks/tests/test_tasks_api.py::TestTaskListView::test_list_tasks_response_includes_metadata
