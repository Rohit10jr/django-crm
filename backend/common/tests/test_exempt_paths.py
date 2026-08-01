"""
Regression tests for RequireOrgContext.EXEMPT_PATHS (bug 23).

Intended-public routes must NOT be blocked by the tenancy middleware with a
403 "Organization context is required" — each of these views runs its own auth
(opaque portal token, api_setting apikey, SNS signature) once the request is
allowed to reach it. The existing suite exercised these endpoints with an
*authenticated* client, which is exactly why the anonymous-path gate went
unnoticed; these tests hit them anonymously.
"""

import pytest

ORG_CONTEXT_DETAIL = "Organization context is required"


@pytest.mark.django_db
class TestExemptPaths:
    """Each intended-public route must get past RequireOrgContext anonymously."""

    def _reaches_view(self, client, method, path, **kwargs):
        """True if the request got past RequireOrgContext.

        The middleware rejects with a *returned* 403 JsonResponse carrying
        ORG_CONTEXT_DETAIL. Anything else — a different status, or the view
        raising its own exception (e.g. a bad-id 500, bug 10) — means the
        request reached its view, which is all bug 23 is about.
        """
        try:
            resp = getattr(client, method)(path, **kwargs)
        except Exception:
            return True  # view was reached and raised its own error
        if resp.status_code == 403:
            body = resp.content.decode(errors="replace")
            return ORG_CONTEXT_DETAIL not in body
        return True

    def test_healthz_reachable(self, unauthenticated_client):
        assert self._reaches_view(unauthenticated_client, "get", "/healthz/")

    def test_schema_document_reachable(self, unauthenticated_client):
        assert self._reaches_view(unauthenticated_client, "get", "/schema/")

    def test_logout_reachable(self, unauthenticated_client):
        assert self._reaches_view(unauthenticated_client, "get", "/logout/")

    def test_public_portal_reachable(self, unauthenticated_client):
        assert self._reaches_view(
            unauthenticated_client, "get", "/api/public/invoice/not-a-real-token/"
        )

    def test_lead_capture_reachable(self, unauthenticated_client):
        assert self._reaches_view(
            unauthenticated_client, "post", "/api/leads/create-from-site/", data={}
        )

    def test_inbound_webhook_reachable(self, unauthenticated_client):
        assert self._reaches_view(
            unauthenticated_client,
            "post",
            "/api/cases/inbound/00000000-0000-0000-0000-000000000000/",
            data={},
        )
