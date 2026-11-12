
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from scheduling.views import (
    TaskDependencyViewSet,
)

from scheduling.calendar_views import (
    CalendarExceptionViewSet,
    ProjectCalendarCalculateView,
    ProjectCalendarEffectiveView,
    WorkCalendarViewSet,
)

from scheduling.planning_views import (
    ProjectScheduleView,
    TaskSchedulePreviewView,
    TaskScheduleRescheduleView,
)


router = DefaultRouter()

# ==========================================
# DEPENDENCIAS
# ==========================================

router.register(
    r"dependencies",
    TaskDependencyViewSet,
    basename="task-dependency",
)


# ==========================================
# CALENDARIOS
# ==========================================

router.register(
    r"calendars",
    WorkCalendarViewSet,
    basename="work-calendar",
)


# ==========================================
# EXCEPCIONES
# ==========================================

router.register(
    r"exceptions",
    CalendarExceptionViewSet,
    basename="calendar-exception",
)


# ==========================================
# RUTAS
# ==========================================

urlpatterns = [

    # Calendario efectivo de un proyecto
    path(
        "projects/<int:project_id>/calendar/",
        ProjectCalendarEffectiveView.as_view(),
        name="project-effective-calendar",
    ),

    # Cálculo de fechas con calendario
    path(
        "projects/<int:project_id>/calculate/",
        ProjectCalendarCalculateView.as_view(),
        name="project-calendar-calculate",
    ),

    # Consulta del cronograma
    path(
        "projects/<int:project_id>/schedule/",
        ProjectScheduleView.as_view(),
        name="project-schedule",
    ),

    # Simulación de reprogramación
    path(
        "tasks/<int:task_id>/preview/",
        TaskSchedulePreviewView.as_view(),
        name="task-schedule-preview",
    ),

    # Confirmación de reprogramación
    path(
        "tasks/<int:task_id>/reschedule/",
        TaskScheduleRescheduleView.as_view(),
        name="task-schedule-reschedule",
    ),

    # Endpoints de los ViewSets
    path(
        "",
        include(router.urls),
    ),
]
