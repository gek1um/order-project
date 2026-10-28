from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "status",
        "start_date",
        "end_date",
        "position",
    )

    list_filter = (
        "status",
        "project",
    )

    search_fields = (
        "name",
        "project__name",
        "project__code",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "project",
        "position",
    )
