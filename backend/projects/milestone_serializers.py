from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from core.access import ScopedRelationsMixin, scope_queryset
from tasks.models import Task
from .models import Milestone


class MilestoneSerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    # Las IDs de actividades pueden omitirse al editar o crear un hito antiguo.
    # Se validan contra membresías y contra el proyecto del hito.
    tasks = serializers.PrimaryKeyRelatedField(many=True, queryset=Task.objects.all(), required=False)

    class Meta:
        model = Milestone
        fields = [
            'id', 'project', 'name', 'due_date', 'responsible',
            'acceptance_criteria', 'evidence', 'status', 'status_display',
            'completed_at', 'tasks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status_display', 'created_at', 'updated_at']

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request is not None:
            # Un ManyRelatedField tiene su propio child_relation: el mixin de
            # seguridad protege las FK directas, pero no esta lista.
            fields['tasks'].child_relation.queryset = scope_queryset(Task.objects.all(), request.user)
        return fields

    def validate(self, attrs):
        instance = self.instance
        data = {
            field: attrs.get(field, getattr(instance, field, None))
            for field in (
                'project', 'name', 'due_date', 'responsible',
                'acceptance_criteria', 'evidence', 'status', 'completed_at',
            )
        }
        if instance is not None and 'project' in attrs and attrs['project'].pk != instance.project_id:
            raise serializers.ValidationError({'project': 'No se permite trasladar un hito a otro proyecto.'})

        project = data['project']
        if 'tasks' in attrs and project is not None:
            unrelated = [task.pk for task in attrs['tasks'] if task.project_id != project.pk]
            if unrelated:
                raise serializers.ValidationError({
                    'tasks': 'Todas las actividades asociadas deben pertenecer al mismo proyecto del hito.'
                })

        candidate = Milestone(**data)
        try:
            candidate.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )
        return attrs
