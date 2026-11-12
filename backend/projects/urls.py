
from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .change_views import ChangeRequestViewSet
from .change_kpi_views import project_change_kpis
from .views import ProjectViewSet
from .milestone_views import MilestoneViewSet
from .milestone_kpi_views import MilestoneKPIViewSet
from .resource_views import ResourceViewSet
from .resource_availability_views import project_weekly_resource_availability
from .resource_assignment_views import (
    TaskResourceAssignmentViewSet, project_resource_cost_summary, task_resource_cost_summary,
)


router = DefaultRouter()

router.register(
    r"projects",
    ProjectViewSet,
    basename="project",
)


router.register(r"milestones", MilestoneViewSet, basename="milestone")
router.register(r"milestone-kpis", MilestoneKPIViewSet, basename="milestone-kpi")
router.register(r"resources", ResourceViewSet, basename="resource")
router.register(r"change-requests", ChangeRequestViewSet, basename="change-request")
router.register(r"resource-assignments", TaskResourceAssignmentViewSet, basename="resource-assignment")

urlpatterns = [
    path("change-kpis/projects/<int:project_id>/", project_change_kpis, name="project-change-kpis"),
    path("resource-availability/projects/<int:project_id>/", project_weekly_resource_availability),
    path("resource-costs/projects/<int:project_id>/", project_resource_cost_summary),
    path("resource-costs/tasks/<int:task_id>/", task_resource_cost_summary),
    path("", include(router.urls)),
]
