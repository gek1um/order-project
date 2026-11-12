from core.access import ScopedRelationsMixin
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from tasks.models import Task
from .resource_models import Resource
from .resource_assignment_models import TaskResourceAssignment


class TaskResourceAssignmentSerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    task = serializers.PrimaryKeyRelatedField(queryset=Task.objects.all())
    resource = serializers.PrimaryKeyRelatedField(queryset=Resource.objects.all())
    task_name = serializers.CharField(source='task.name', read_only=True)
    resource_name = serializers.CharField(source='resource.name', read_only=True)
    resource_kind = serializers.CharField(source='resource.kind', read_only=True)
    project = serializers.IntegerField(source='task.project_id', read_only=True)
    planned_cost = serializers.DecimalField(max_digits=27, decimal_places=2, read_only=True)
    actual_cost = serializers.DecimalField(max_digits=27, decimal_places=2, read_only=True)

    class Meta:
        model = TaskResourceAssignment
        fields = [
            'id', 'project', 'task', 'task_name', 'resource', 'resource_name',
            'resource_kind', 'planned_units', 'actual_units', 'planned_unit_cost',
            'actual_unit_cost', 'planned_cost', 'actual_cost', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'project', 'task_name', 'resource_name', 'resource_kind',
            'planned_cost', 'actual_cost', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'planned_unit_cost': {'required': False},
            'actual_unit_cost': {'required': False},
        }

    def validate(self, attrs):
        task = attrs.get('task', self.instance.task if self.instance else None)
        resource = attrs.get('resource', self.instance.resource if self.instance else None)
        if task is not None and resource is not None and task.project_id != resource.project_id:
            raise serializers.ValidationError({
                'resource': 'La actividad y el recurso deben pertenecer al mismo proyecto.'
            })

        if self.instance is None:
            if resource is None:
                raise serializers.ValidationError({'resource': 'El recurso es obligatorio.'})
            if 'planned_unit_cost' not in attrs:
                cost = (resource.hourly_rate if resource.kind in (
                    Resource.Kind.PROFESSIONAL, Resource.Kind.PROFESSIONAL_TYPE
                ) else resource.unit_cost)
                if cost is None:
                    raise serializers.ValidationError({'planned_unit_cost': 'El recurso no tiene tarifa de catálogo.'})
                attrs['planned_unit_cost'] = cost
            attrs.setdefault('actual_unit_cost', attrs['planned_unit_cost'])

        # En PATCH se comprueba el estado final completo, no solo el payload.
        candidate = TaskResourceAssignment()
        if self.instance:
            for field in TaskResourceAssignment._meta.concrete_fields:
                if field.name not in ('id', 'created_at', 'updated_at'):
                    setattr(candidate, field.attname, getattr(self.instance, field.attname))
        for key, value in attrs.items():
            setattr(candidate, key, value)
        try:
            candidate.full_clean(validate_unique=False, validate_constraints=False)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else {'non_field_errors': exc.messages}
            ) from exc
        return attrs
