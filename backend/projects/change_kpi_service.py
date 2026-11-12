"""Indicadores del control de cambios; cálculo de solo lectura.

Todas las cohortes se filtran por la fecha original de solicitud (requested_at).
Se evitan conversiones implícitas de nulos en resultados 0%.
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .change_models import ChangeRequest


DECIDED_STATUSES = (
    ChangeRequest.Status.APPROVED,
    ChangeRequest.Status.REJECTED,
    ChangeRequest.Status.IMPLEMENTING,
    ChangeRequest.Status.CLOSED,
)
APPROVED_STATUSES = (
    ChangeRequest.Status.APPROVED,
    ChangeRequest.Status.IMPLEMENTING,
    ChangeRequest.Status.CLOSED,
)


def _percent(numerator: int, denominator: int):
    if not denominator:
        return None
    return float((Decimal(numerator) * 100 / Decimal(denominator)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    ))


def _mean(days):
    if not days:
        return None
    return float((Decimal(sum(days)) / Decimal(len(days))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    ))


def calculate_change_kpis(project_id: int, date_from: date | None = None,
                          date_to: date | None = None) -> dict:
    """Retorna 3 KPI y contadores de cobertura, sin escribir en la BD.

    Días = diferencia entre fechas calendario, no horas transcurridas ni hábiles.
    El criterio de cumplimiento usa actual_completion_date <= committed_date.
    """
    qs = ChangeRequest.objects.filter(project_id=project_id)
    if date_from is not None:
        qs = qs.filter(requested_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(requested_at__lte=date_to)

    requests = list(qs.only(
        'status', 'requested_at', 'decided_at', 'committed_date',
        'actual_completion_date',
    ))

    decided = [item for item in requests if item.status in DECIDED_STATUSES]
    approved = [item for item in decided if item.status in APPROVED_STATUSES]
    rejected = [item for item in decided if item.status == ChangeRequest.Status.REJECTED]

    decision_days = [
        (item.decided_at.date() - item.requested_at).days
        for item in decided
        if item.decided_at is not None and item.decided_at.date() >= item.requested_at
    ]

    closed = [item for item in requests if item.status == ChangeRequest.Status.CLOSED]
    measurable_closed = [
        item for item in closed
        if item.committed_date is not None and item.actual_completion_date is not None
    ]
    on_time = [
        item for item in measurable_closed
        if item.actual_completion_date <= item.committed_date
    ]

    return {
        'project_id': project_id,
        'period': {
            'requested_from': date_from.isoformat() if date_from else None,
            'requested_to': date_to.isoformat() if date_to else None,
        },
        'counts': {
            'total': len(requests),
            'decided': len(decided),
            'approved': len(approved),
            'rejected': len(rejected),
            'closed': len(closed),
        },
        'kpis': {
            'approval_rate': {
                'value': _percent(len(approved), len(decided)),
                'unit': 'percent',
                'numerator': len(approved),
                'denominator': len(decided),
            },
            'average_decision_days': {
                'value': _mean(decision_days),
                'unit': 'calendar_days',
                'observations': len(decision_days),
                'excluded_missing_or_invalid_date': len(decided) - len(decision_days),
            },
            'on_time_closure_rate': {
                'value': _percent(len(on_time), len(measurable_closed)),
                'unit': 'percent',
                'numerator': len(on_time),
                'denominator': len(measurable_closed),
                'excluded_without_dates': len(closed) - len(measurable_closed),
            },
        },
    }
