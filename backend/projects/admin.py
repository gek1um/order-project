from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "manager_name",
        "status",
        "start_date",
        "end_date",
        "baseline_budget",
    )

    list_filter = (
        "status",
        "start_date",
    )

    search_fields = (
        "code",
        "name",
        "manager_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)
