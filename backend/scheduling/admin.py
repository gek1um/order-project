
from django.contrib import admin

from .models import (
    CalendarException,
    TaskDependency,
    WorkCalendar,
)


# ==================================================
# DEPENDENCIAS
# ==================================================

@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "predecessor",
        "successor",
        "dependency_type",
        "lag_days",
        "created_at",
    )

    list_filter = (
        "dependency_type",
        "created_at",
    )

    search_fields = (
        "predecessor__name",
        "successor__name",
        "predecessor__project__code",
        "successor__project__code",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "predecessor",
        "successor",
    )

    ordering = ("-created_at",)


# ==================================================
# EXCEPCIONES DENTRO DEL CALENDARIO
# ==================================================

class CalendarExceptionInline(admin.TabularInline):
    model = CalendarException

    extra = 1

    fields = (
        "date",
        "is_working",
        "description",
    )

    ordering = ("date",)


# ==================================================
# CALENDARIOS LABORALES
# ==================================================

@admin.register(WorkCalendar)
class WorkCalendarAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "project",
        "name",
        "working_days_display",
        "updated_at",
    )

    search_fields = (
        "name",
        "project__code",
        "project__name",
    )

    autocomplete_fields = ("project",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = [CalendarExceptionInline]

    fieldsets = (
        (
            "Información general",
            {
                "fields": (
                    "project",
                    "name",
                )
            },
        ),
        (
            "Días laborables",
            {
                "fields": (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )
            },
        ),
        (
            "Auditoría",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(
        description="Días laborables",
    )
    def working_days_display(self, obj):
        names = [
            "Lun",
            "Mar",
            "Mié",
            "Jue",
            "Vie",
            "Sáb",
            "Dom",
        ]

        return ", ".join(
            names[index]
            for index in sorted(obj.working_weekdays)
        )


# ==================================================
# ADMINISTRACIÓN DIRECTA DE EXCEPCIONES
# ==================================================

@admin.register(CalendarException)
class CalendarExceptionAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "calendar",
        "date",
        "is_working",
        "description",
    )

    list_filter = (
        "is_working",
        "date",
    )

    search_fields = (
        "calendar__name",
        "calendar__project__code",
        "description",
    )

    autocomplete_fields = ("calendar",)

    ordering = ("-date",)
