from core.access import ScopedRelationsMixin
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Project
from .resource_models import Resource


class ResourceSerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_code = serializers.CharField(source="project.code", read_only=True)
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    estimated_catalog_cost = serializers.DecimalField(max_digits=19, decimal_places=2, read_only=True)

    class Meta:
        model = Resource
        fields = [
            "id", "project", "project_code", "kind", "kind_display", "name",
            "description", "specialty", "unit", "hours_per_week", "weeks",
            "hourly_rate", "quantity", "unit_cost", "periods",
            "estimated_catalog_cost", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        if self.instance and 'project' in attrs and attrs['project'].pk != self.instance.project_id:
            if self.instance.task_assignments.exists():
                raise serializers.ValidationError({
                    'project': 'No puedes trasladar a otro proyecto un recurso con asignaciones existentes.'
                })
        if self.instance and 'kind' in attrs and attrs['kind'] != self.instance.kind:
            if self.instance.task_assignments.exists():
                raise serializers.ValidationError({
                    'kind': 'No puedes cambiar el tipo de un recurso con asignaciones existentes.'
                })
        # Valida estado final en PATCH y PUT; no solo los campos enviados.
        model = self.Meta.model
        candidate = model()
        if self.instance:
            for field in model._meta.concrete_fields:
                if field.name not in ("id", "created_at", "updated_at"):
                    setattr(candidate, field.attname, getattr(self.instance, field.attname))
        for key, value in attrs.items():
            setattr(candidate, key, value)
        try:
            # No consultar unique constraints del registro temporal; DRF gestiona id.
            candidate.full_clean(validate_unique=False, validate_constraints=False)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages}
            ) from exc
        return attrs
