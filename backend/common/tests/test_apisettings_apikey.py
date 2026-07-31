"""
Regression tests for APISettingsListSerializer (bug 27).

- The lead-capture `apikey` is a secret and must not appear for non-admin org
  members; admins still receive it (they configure it on their site).
- `id` must be present so listed rows can be addressed for edit/delete.
"""

from types import SimpleNamespace

import pytest

from common.models import APISettings
from common.serializer import APISettingsListSerializer


@pytest.mark.django_db
class TestAPISettingsApikeyMasking:
    def _make(self, org, user):
        return APISettings.objects.create(
            title="site", website="http://example.com", org=org, created_by=user
        )

    def _ctx(self, profile):
        return {"request": SimpleNamespace(profile=profile)}

    def test_id_present(self, org_a, admin_user, admin_profile):
        obj = self._make(org_a, admin_user)
        data = APISettingsListSerializer(obj, context=self._ctx(admin_profile)).data
        assert "id" in data  # bug 27: needed to edit/delete a listed row

    def test_apikey_visible_to_admin(self, org_a, admin_user, admin_profile):
        obj = self._make(org_a, admin_user)
        data = APISettingsListSerializer(obj, context=self._ctx(admin_profile)).data
        assert data["apikey"] == obj.apikey

    def test_apikey_hidden_from_non_admin(self, org_a, admin_user, user_profile):
        obj = self._make(org_a, admin_user)
        data = APISettingsListSerializer(obj, context=self._ctx(user_profile)).data
        assert "apikey" not in data

    def test_apikey_hidden_without_request_context(self, org_a, admin_user):
        obj = self._make(org_a, admin_user)
        data = APISettingsListSerializer(obj).data  # no request → safe default: hide
        assert "apikey" not in data
