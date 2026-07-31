"""Django admin registration for the macros app.

Auto-registers every model in this app so all records are browsable in the
Django admin without hand-writing a ModelAdmin for each one.
"""

from django.apps import apps
from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered

for _model in apps.get_app_config("macros").get_models():
    try:
        admin.site.register(_model)
    except AlreadyRegistered:
        pass
