"""
Regression tests for InboundMailboxSerializer (bug 14).

webhook_secret authenticates inbound email webhooks and must not appear for
non-admin org members; admins still receive it (they manage it).
"""

from types import SimpleNamespace

import pytest

from cases.models import InboundMailbox
from cases.serializer import InboundMailboxSerializer


@pytest.mark.django_db
class TestMailboxWebhookSecretMasking:
    def _make(self, org):
        return InboundMailbox.objects.create(
            org=org, address="in@example.com", webhook_secret="TOPSECRET"
        )

    def _ctx(self, profile):
        return {"request": SimpleNamespace(profile=profile)}

    def test_secret_visible_to_admin(self, org_a, admin_profile):
        obj = self._make(org_a)
        data = InboundMailboxSerializer(obj, context=self._ctx(admin_profile)).data
        assert data["webhook_secret"] == "TOPSECRET"

    def test_secret_hidden_from_non_admin(self, org_a, user_profile):
        obj = self._make(org_a)
        data = InboundMailboxSerializer(obj, context=self._ctx(user_profile)).data
        assert "webhook_secret" not in data

    def test_secret_hidden_without_request_context(self, org_a):
        obj = self._make(org_a)
        data = InboundMailboxSerializer(obj).data  # no request → safe default: hide
        assert "webhook_secret" not in data
