from core.access import ProjectScopedViewSetMixin
from decimal import Decimal
from core.access import project_or_404, task_or_404

from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from tasks.models import Task
from .models import Project
from .resource_assignment_models import TaskResourceAssignment
from .resource_assignment_serializers import TaskResourceAssignmentSerializer


class TaskResourceAssignmentViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD /api/resource-assignments/; filtros ?project=, ?task= y ?resource=."""

    queryset = TaskResourceAssignment.objects.select_related('task', 'resource').all()
    serializer_class = TaskResourceAssignmentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        for key in ('project', 'task', 'resource'):
            value = self.request.query_params.get(key)
            if value is None:
                continue
            if not value.isdecimal() or int(value) <= 0:
                raise ValidationError({key: 'Debe ser un identificador positivo.'})
            if key == 'project':
                queryset = queryset.filter(task__project_id=int(value))
            elif key == 'task':
                queryset = queryset.filter(task_id=int(value))
            else:
                queryset = queryset.filter(resource_id=int(value))
        return queryset


MONEY_FIELD = DecimalField(max_digits=29, decimal_places=2)


def _totals(assignments):
    planned_expr = ExpressionWrapper(F('planned_units') * F('planned_unit_cost'), output_field=MONEY_FIELD)
    actual_expr = ExpressionWrapper(F('actual_units') * F('actual_unit_cost'), output_field=MONEY_FIELD)
    totals = assignments.aggregate(
        planned=Coalesce(Sum(planned_expr), Value(Decimal('0.00')), output_field=MONEY_FIELD),
        actual=Coalesce(Sum(actual_expr), Value(Decimal('0.00')), output_field=MONEY_FIELD),
    )
    planned = totals['planned'].quantize(Decimal('0.01'))
    actual = totals['actual'].quantize(Decimal('0.01'))
    return planned, actual


def _money(value):
    return f'{value:.2f}'


@api_view(['GET'])
def project_resource_cost_summary(request, project_id):
    project = project_or_404(request.user, project_id)

    assignments = TaskResourceAssignment.objects.filter(task__project_id=project_id)
    planned, actual = _totals(assignments)
    budget = project.baseline_budget
    return Response({
        'project': project.id,
        'baseline_budget': _money(budget),
        'planned_resource_cost': _money(planned),
        'actual_resource_cost': _money(actual),
        'planned_budget_variance': _money(budget - planned),
        'actual_budget_variance': _money(budget - actual),
        'actual_minus_planned': _money(actual - planned),
        'assignment_count': assignments.count(),
    })


@api_view(['GET'])
def task_resource_cost_summary(request, task_id):
    task = task_or_404(request.user, task_id)
    assignments = TaskResourceAssignment.objects.filter(task_id=task_id)
    planned, actual = _totals(assignments)
    return Response({
        'task': task.id,
        'project': task.project_id,
        'planned_resource_cost': _money(planned),
        'actual_resource_cost': _money(actual),
        'actual_minus_planned': _money(actual - planned),
        'assignment_count': assignments.count(),
    })
