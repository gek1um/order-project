"""Endpoint de solo lectura para indicadores de gestión del cambio."""
from django.shortcuts import get_object_or_404
from core.access import project_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .change_kpi_service import calculate_change_kpis
from .models import Project


class ChangeKpiFiltersSerializer(serializers.Serializer):
    # Convención: fechas de creación de la solicitud, inclusivas.
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)

    def validate(self, attrs):
        start = attrs.get('from_date')
        end = attrs.get('to_date')
        if start and end and start > end:
            raise serializers.ValidationError({'to': 'No puede ser anterior a from.'})
        return attrs


@api_view(['GET'])
def project_change_kpis(request, project_id: int):
    project = project_or_404(request.user, project_id)
    # Si un filtro no viene, quitar la clave para no convertir None en fecha inválida.
    data = {}
    if 'from' in request.query_params:
        data['from_date'] = request.query_params['from']
    if 'to' in request.query_params:
        data['to_date'] = request.query_params['to']
    params = ChangeKpiFiltersSerializer(data=data)
    params.is_valid(raise_exception=True)
    return Response(calculate_change_kpis(
        project.id,
        date_from=params.validated_data.get('from_date'),
        date_to=params.validated_data.get('to_date'),
    ))
