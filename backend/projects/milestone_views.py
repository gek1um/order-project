from core.access import ProjectScopedViewSetMixin
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, serializers
from .models import Milestone, Project
from .milestone_serializers import MilestoneSerializer


class MilestoneViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = MilestoneSerializer
    queryset = Milestone.objects.select_related('project').all()

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id is not None:
            if not project_id.isdecimal():
                raise serializers.ValidationError({'project': 'Identificador de proyecto inválido.'})
            queryset = queryset.filter(project_id=int(project_id))
        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        project_id = serializer.validated_data['project'].pk
        get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        project_id = serializer.instance.project_id
        get_object_or_404(Project.objects.select_for_update(), pk=project_id)
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        get_object_or_404(Project.objects.select_for_update(), pk=instance.project_id)
        instance.delete()
