from django.contrib import admin

from common.models import Address, Comment, CommentFiles, Org, Profile, User

# Register your models here.

admin.site.register(User)
admin.site.register(Address)
admin.site.register(Comment)
admin.site.register(CommentFiles)


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
    list_display = ("name", "id", "is_active", "default_currency", "created_at")
    list_filter = ("is_active", "default_currency", "created_at")
    search_fields = ("name", "company_name", "email")
    readonly_fields = ("api_key", "created_at", "updated_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "org",
        "role",
        "is_organization_admin",
        "is_active",
        "created_at",
    )
    list_filter = ("role", "is_organization_admin", "is_active", "created_at")
    search_fields = ("user__email", "org__name")
    raw_id_fields = ("user", "org")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


# Auto-register any remaining models in this app for admin browsing.
from django.apps import apps as _apps  # noqa: E402
from django.contrib.admin.sites import AlreadyRegistered as _AlreadyRegistered  # noqa: E402

for _model in _apps.get_app_config("common").get_models():
    try:
        admin.site.register(_model)
    except _AlreadyRegistered:
        pass
