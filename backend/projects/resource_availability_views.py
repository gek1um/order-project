"""API GET de disponibilidad semanal; no modifica costos ni asignaciones."""
from datetime import date
from core.access import project_or_404

from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status

from .models import Project
from .resource_availability import build_weekly_availability


@api_view(['GET'])
def project_weekly_resource_availability(request, project_id):
    project = project_or_404(request.user, project_id)

    start_text = request.query_params.get('from', project.start_date.isoformat())
    end_text = request.query_params.get('to', project.end_date.isoformat())
    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except (ValueError, TypeError):
        raise ValidationError({'dates': 'Usa fechas válidas con formato YYYY-MM-DD.'})
    if start > end:
        raise ValidationError({'dates': 'La fecha inicial no puede ser posterior a la final.'})
    if (end - start).days > 730:
        raise ValidationError({'dates': 'Selecciona un rango máximo de 731 días.'})

    return Response(build_weekly_availability(project, start, end))
