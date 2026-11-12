"""Reporte de disponibilidad semanal estimada (solo lectura).

La asignación registra horas totales, no distribución diaria. Para estimar la
carga por semana se reparten las horas planificadas uniformemente entre los
días laborables inclusivos de la actividad, según el calendario del proyecto.
No es un registro de turnos ni de horas efectivamente ejecutadas.
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from scheduling.services.project_calendar import ProjectCalendarService
from .resource_models import Resource
from .resource_assignment_models import TaskResourceAssignment

TWO = Decimal('0.01')
HUMAN_KINDS = (Resource.Kind.PROFESSIONAL, Resource.Kind.PROFESSIONAL_TYPE)


def _monday(day):
    return day - timedelta(days=day.weekday())


def _dates_between(start, end):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _number(value):
    return str(value.quantize(TWO, rounding=ROUND_HALF_UP))


def build_weekly_availability(project, start, end):
    """Resume capacidad y carga de recursos humanos en semanas ISO completas.

    La capacidad semanal se prorratea por días laborables dentro de los límites
    del proyecto (feriados incluidos). La carga planificada se distribuye entre
    los días laborables de cada tarea y luego suma por semana y recurso.
    """
    calendar = ProjectCalendarService(project.pk)
    resources = list(Resource.objects.filter(project=project, kind__in=HUMAN_KINDS).order_by('id'))
    assignments = list(TaskResourceAssignment.objects.filter(
        task__project=project, resource_id__in=[resource.pk for resource in resources]
    ).select_related('task', 'resource'))

    week_starts = []
    current = _monday(start)
    while current <= end:
        week_starts.append(current)
        current += timedelta(days=7)

    # Un lunes fuera del proyecto puede aparecer en una semana parcial.
    # Capacidad se prorratea al período real del proyecto.
    capacity_days = {}
    for week in week_starts:
        lo, hi = max(week, project.start_date), min(week + timedelta(days=6), project.end_date)
        capacity_days[week] = sum(calendar.is_working_day(day) for day in _dates_between(lo, hi)) if lo <= hi else 0

    planned_by_resource_week = defaultdict(lambda: Decimal('0'))
    assignment_ids_by_resource_week = defaultdict(set)
    warnings = []
    visible_weeks = set(week_starts)
    for assignment in assignments:
        task = assignment.task
        working_days = [day for day in _dates_between(task.start_date, task.end_date)
                        if calendar.is_working_day(day)]
        if not working_days:
            warnings.append({
                'code': 'TASK_NO_WORKING_DAYS', 'task_id': task.id,
                'resource_id': assignment.resource_id,
                'detail': 'La actividad no tiene días laborables; no se pudo distribuir su carga.',
            })
            continue
        daily_load = assignment.planned_units / Decimal(len(working_days))
        for day in working_days:
            week = _monday(day)
            if week in visible_weeks:
                key = (assignment.resource_id, week)
                planned_by_resource_week[key] += daily_load
                assignment_ids_by_resource_week[key].add(assignment.pk)

    results = []
    overallocated_weeks = 0
    for resource in resources:
        # PROFESSIONAL_TYPE representa un pool de quantity personas, no una persona única.
        headcount = resource.quantity if resource.kind == Resource.Kind.PROFESSIONAL_TYPE else Decimal('1')
        standard_days = Decimal(len(calendar.working_weekdays))
        for week in week_starts:
            # Capacidad semanal nominal 40h, prorrateada por días laborables efectivos.
            capacity = (resource.hours_per_week or Decimal('0')) * headcount * Decimal(capacity_days[week]) / standard_days
            planned = planned_by_resource_week[(resource.pk, week)]
            exceeded = planned > capacity
            if exceeded:
                overallocated_weeks += 1
            results.append({
                'resource_id': resource.pk,
                'resource_name': resource.name,
                'resource_kind': resource.kind,
                'week_start': week.isoformat(),
                'week_end': (week + timedelta(days=6)).isoformat(),
                'capacity_hours': _number(capacity),
                'planned_hours': _number(planned),
                'available_hours': _number(capacity - planned),
                'overallocation_hours': _number(max(Decimal('0'), planned - capacity)),
                'overallocated': exceeded,
                'assignment_ids': sorted(assignment_ids_by_resource_week[(resource.pk, week)]),
            })

    return {
        'project': project.pk,
        'range_start': start.isoformat(),
        'range_end': end.isoformat(),
        'calendar_source': calendar.source,
        'allocation_method': 'EVENLY_OVER_WORKING_DAYS',
        'note': ('Las horas planificadas se distribuyen uniformemente entre los días laborables '
                 'de la actividad. Es una estimación, no una agenda real ni una carga diaria registrada.'),
        'resource_count': len(resources),
        'week_count': len(week_starts),
        'overallocated_weeks': overallocated_weeks,
        'weeks': results,
        'warnings': warnings,
    }
