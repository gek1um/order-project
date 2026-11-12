from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.access import visible_projects
from .models import Milestone, MilestoneKPI


class MilestoneKPISerializer(serializers.ModelSerializer):
    actual_value = serializers.SerializerMethodField()
    achievement_status = serializers.CharField(read_only=True)
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)

    class Meta:
        model = MilestoneKPI
        fields = [
            'id', 'milestone', 'name', 'description', 'responsible',
            'kind', 'kind_display', 'direction', 'direction_display', 'unit',
            'target_value', 'measured_value', 'numerator', 'denominator',
            'measured_at', 'actual_value', 'achievement_status',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'kind_display', 'direction_display', 'actual_value',
            'achievement_status', 'created_at', 'updated_at',
        ]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request is not None:
            fields['milestone'].queryset = Milestone.objects.filter(
                project_id__in=visible_projects(request.user).values('pk')
            )
        return fields

    def get_actual_value(self, obj):
        value = obj.exact_actual_value
        if value is None:
            return None
        return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def validate(self, attrs):
        if self.instance is not None and 'milestone' in attrs:
            if attrs['milestone'].pk != self.instance.milestone_id:
                raise serializers.ValidationError({
                    'milestone': 'No se permite trasladar un KPI a otro hito.'
                })
        field_names = [
            'milestone', 'name', 'description', 'responsible', 'kind',
            'direction', 'unit', 'target_value', 'measured_value',
            'numerator', 'denominator', 'measured_at',
        ]
        effective = {
            field: attrs.get(field, getattr(self.instance, field, None))
            for field in field_names
        }
        # El porcentaje siempre se expresa en %, incluso si se omitió la unidad.
        if effective['kind'] == MilestoneKPI.Kind.PERCENTAGE:
            if 'unit' in attrs and attrs['unit'] != '%':
                raise serializers.ValidationError({'unit': 'La unidad debe ser %.'})
            attrs['unit'] = '%'
            effective['unit'] = '%'
        elif 'unit' not in attrs and self.instance is None:
            attrs['unit'] = 'unidad'
            effective['unit'] = 'unidad'

        candidate = MilestoneKPI(**effective)
        try:
            candidate.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
            )
        return attrs
