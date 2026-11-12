"""Control central de acceso a proyectos y relaciones entre entidades.

La pertenencia se comprueba siempre contra PostgreSQL; nunca se confía en
un project_id suministrado por el cliente como prueba de autorización.
"""
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from .models import ProjectMembership, UserRole


def is_admin(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return bool(user.project_profile.role == UserRole.ADMIN) if hasattr(user, 'project_profile') else False


def visible_projects(user):
    from projects.models import Project
    if not user or not user.is_authenticated or not user.is_active:
        return Project.objects.none()
    if is_admin(user):
        return Project.objects.all()
    return Project.objects.filter(user_memberships__user_id=user.pk).distinct()


def visible_project_ids(user):
    return visible_projects(user).values('id')


def scope_queryset(queryset, user):
    """Filtrado de filas para las entidades del sistema con vínculo al proyecto."""
    from projects.models import Project
    from projects.milestone_models import Milestone
    from projects.resource_models import Resource
    from projects.resource_assignment_models import TaskResourceAssignment
    from projects.change_models import ChangeRequest
    from tasks.models import Task
    from scheduling.models import WorkCalendar, CalendarException, TaskDependency
    if is_admin(user):
        return queryset
    if not user or not user.is_authenticated or not user.is_active:
        return queryset.none()
    model = queryset.model
    paths = {
        Project: 'pk__in',
        Task: 'project_id__in',
        Milestone: 'project_id__in',
        Resource: 'project_id__in',
        TaskResourceAssignment: 'task__project_id__in',
        ChangeRequest: 'project_id__in',
        WorkCalendar: 'project_id__in',
        CalendarException: 'calendar__project_id__in',
        TaskDependency: 'predecessor__project_id__in',
    }
    lookup = paths.get(model)
    if not lookup:
        raise RuntimeError(f'Falta configurar el alcance de {model.__name__}')
    return queryset.filter(**{lookup: visible_project_ids(user)})


def project_or_404(user, pk):
    return get_object_or_404(visible_projects(user), pk=pk)


def task_or_404(user, pk):
    from tasks.models import Task
    return get_object_or_404(scope_queryset(Task.objects.all(), user), pk=pk)


class ProjectScopedViewSetMixin:
    """GET/list/detail/PUT/PATCH/DELETE restringidos por membresía."""
    def get_queryset(self):
        return scope_queryset(super().get_queryset(), self.request.user)


class ScopedRelationsMixin:
    """Restringe FK recibidas en POST/PUT/PATCH, incluidas las autogeneradas."""
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if not request:
            return fields
        for field in fields.values():
            if isinstance(field, serializers.PrimaryKeyRelatedField) and field.queryset is not None:
                field.queryset = scope_queryset(field.queryset, request.user)
        return fields


class IsAdministrator(BasePermission):
    message = 'Esta operación requiere el rol ADMIN.'

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsAdministratorForProjectMutation(BasePermission):
    message = 'Solo ADMIN puede crear, actualizar o eliminar proyectos.'

    def has_permission(self, request, view):
        if getattr(view, 'action', None) in {'create','update','partial_update','destroy'}:
            return is_admin(request.user)
        return request.user.is_authenticated and request.user.is_active


class IsAdministratorForChangeDecision(BasePermission):
    message = 'Solo ADMIN puede aprobar o rechazar solicitudes de cambio.'

    def has_permission(self, request, view):
        if getattr(view, 'action', None) in {'approve', 'reject'}:
            return is_admin(request.user)
        return request.user.is_authenticated and request.user.is_active
