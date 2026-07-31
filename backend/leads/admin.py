from django.contrib import admin

from leads.models import Lead

admin.site.register(Lead)


# Auto-register any remaining models in this app for admin browsing.
from django.apps import apps as _apps  # noqa: E402
from django.contrib.admin.sites import AlreadyRegistered as _AlreadyRegistered  # noqa: E402

for _model in _apps.get_app_config("leads").get_models():
    try:
        admin.site.register(_model)
    except _AlreadyRegistered:
        pass
