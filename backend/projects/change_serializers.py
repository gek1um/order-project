from core.access import ScopedRelationsMixin
from rest_framework import serializers
from .change_models import ChangeApplication, ChangeEvent, ChangeRequest


class ChangeEventSerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    class Meta:
        model = ChangeEvent
        fields = ('id', 'action', 'from_status', 'to_status', 'actor', 'detail', 'created_at')
        read_only_fields = fields


class ChangeApplicationSerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    class Meta:
        model = ChangeApplication
        fields = ('id', 'kind', 'actor', 'task', 'before', 'after', 'detail', 'created_at')
        read_only_fields = fields


class ChangeRequestSerializer(ScopedRelationsMixin, serializers.ModelSerializer):
    events = ChangeEventSerializer(many=True, read_only=True)
    applications = ChangeApplicationSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ChangeRequest
        fields = (
            'id', 'project', 'title', 'requester', 'requested_at', 'description',
            'justification', 'kind', 'priority', 'risk', 'impact_scope',
            'impact_resources', 'estimated_delay_days', 'estimated_cost',
            'actual_cost', 'responsible', 'committed_date',
            'actual_completion_date', 'result', 'status', 'status_display',
            'decided_by', 'decided_at', 'decision_reason', 'events', 'applications',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'status', 'status_display', 'decided_by', 'decided_at',
            'decision_reason', 'events', 'applications', 'created_at', 'updated_at',
            # La ejecución y costos reales se implementarán en 6.2.
            'actual_cost', 'actual_completion_date', 'result',
        )

    def validate(self, attrs):
        instance = self.instance
        if instance and instance.status != ChangeRequest.Status.OPEN:
            raise serializers.ValidationError({
                'detail': 'Solo se pueden editar solicitudes en estado Abierta.'
            })
        if instance and 'project' in attrs and attrs['project'].pk != instance.project_id:
            raise serializers.ValidationError({'project': 'No se puede trasladar una solicitud a otro proyecto.'})
        estimated = attrs.get('estimated_cost', instance.estimated_cost if instance else 0)
        if estimated < 0:
            raise serializers.ValidationError({'estimated_cost': 'No puede ser negativo.'})
        return attrs


class ChangeDecisionSerializer(serializers.Serializer):
    actor = serializers.CharField(max_length=150, allow_blank=False, trim_whitespace=True)
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)


class ChangeSubmitSerializer(serializers.Serializer):
    actor = serializers.CharField(max_length=150, allow_blank=False, trim_whitespace=True)


class ChangeImplementSerializer(serializers.Serializer):
    actor = serializers.CharField(max_length=150, trim_whitespace=True, allow_blank=False)
    committed_date = serializers.DateField(required=False)


class ChangeScheduleSerializer(serializers.Serializer):
    actor = serializers.CharField(max_length=150, trim_whitespace=True, allow_blank=False)
    task_id = serializers.IntegerField(min_value=1)
    start_date = serializers.DateField()
    duration_days = serializers.IntegerField(min_value=1)
    detail = serializers.CharField(required=False, allow_blank=True, default='')


class ChangeActualCostSerializer(serializers.Serializer):
    actor = serializers.CharField(max_length=150, trim_whitespace=True, allow_blank=False)
    actual_cost = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=0)
    detail = serializers.CharField(required=False, allow_blank=True, default='')


class ChangeCloseSerializer(serializers.Serializer):
    actor = serializers.CharField(max_length=150, trim_whitespace=True, allow_blank=False)
    actual_completion_date = serializers.DateField()
    result = serializers.CharField(trim_whitespace=True, allow_blank=False)
