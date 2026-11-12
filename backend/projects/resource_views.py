from core.access import ProjectScopedViewSetMixin
from django.db.models.deletion import ProtectedError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from .resource_models import Resource
from .resource_serializers import ResourceSerializer


class ResourceViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    """GET/POST /api/resources/; GET/PATCH/PUT/DELETE /api/resources/{id}/."""

    serializer_class = ResourceSerializer
    queryset = Resource.objects.select_related("project").all()

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get("project")
        kind = self.request.query_params.get("kind")
        if project_id is not None:
            if not project_id.isdecimal() or int(project_id) < 1:
                raise ValidationError({"project": "Debe ser un identificador positivo."})
            qs = qs.filter(project_id=int(project_id))
        if kind is not None:
            if kind not in Resource.Kind.values:
                raise ValidationError({"kind": "Tipo de recurso no reconocido."})
            qs = qs.filter(kind=kind)
        return qs

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError({
                'resource': 'No puedes eliminar un recurso asignado a actividades. Elimina primero sus asignaciones.'
            }) from exc
