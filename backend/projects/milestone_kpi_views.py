from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated

from core.access import visible_projects
from .models import Milestone, MilestoneKPI, Project
from .milestone_kpi_serializers import MilestoneKPISerializer


class MilestoneKPIViewSet(viewsets.ModelViewSet):
    """CRUD de KPI, acotado a hitos de proyectos visibles por el usuario."""

    serializer_class = MilestoneKPISerializer
    permission_classes = [IsAuthenticated]
    queryset = MilestoneKPI.objects.select_related('milestone', 'milestone__project')

    def get_queryset(self):
        queryset = self.queryset.filter(
            milestone__project_id__in=visible_projects(self.request.user).values('pk')
        )
        for key, column in (('project', 'milestone__project_id'), ('milestone', 'milestone_id')):
            raw = self.request.query_params.get(key)
            if raw is not None:
                if not raw.isdecimal():
                    raise serializers.ValidationError({key: 'Identificador inválido.'})
                queryset = queryset.filter(**{column: int(raw)})
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        project_id = serializer.validated_data['milestone'].project_id
        get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        project_id = serializer.instance.milestone.project_id
        get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        get_object_or_404(Project.objects.select_for_update(), pk=instance.milestone.project_id)
        instance.delete()
