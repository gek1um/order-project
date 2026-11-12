from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class MilestoneKPI(models.Model):
    """Indicador medible asociado a un hito; independiente de los KPI de cambios."""

    class Kind(models.TextChoices):
        VALUE = 'VALUE', 'Valor directo'
        PERCENTAGE = 'PERCENTAGE', 'Porcentaje (numerador / denominador)'

    class Direction(models.TextChoices):
        AT_LEAST = 'AT_LEAST', 'Mayor o igual a la meta'
        AT_MOST = 'AT_MOST', 'Menor o igual a la meta'

    milestone = models.ForeignKey(
        'projects.Milestone', on_delete=models.CASCADE,
        related_name='kpis',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    responsible = models.CharField(max_length=150)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.VALUE)
    direction = models.CharField(max_length=12, choices=Direction.choices, default=Direction.AT_LEAST)
    unit = models.CharField(max_length=30, default='unidad')
    target_value = models.DecimalField(max_digits=15, decimal_places=2)
    measured_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    numerator = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    denominator = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    measured_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_milestone_kpis'
        ordering = ['milestone_id', 'id']

    @property
    def exact_actual_value(self):
        if self.kind == self.Kind.VALUE:
            return self.measured_value
        if self.numerator is None or self.denominator is None or self.denominator <= 0:
            return None
        return self.numerator / self.denominator * Decimal('100')

    @property
    def achievement_status(self):
        actual = self.exact_actual_value
        if actual is None:
            return 'NOT_MEASURED'
        if self.direction == self.Direction.AT_MOST:
            return 'MET' if actual <= self.target_value else 'NOT_MET'
        return 'MET' if actual >= self.target_value else 'NOT_MET'

    def clean(self):
        super().clean()
        errors = {}
        if self.target_value is not None and self.target_value < 0:
            errors['target_value'] = 'La meta no puede ser negativa.'
        if self.kind == self.Kind.VALUE:
            if self.numerator is not None or self.denominator is not None:
                errors['kind'] = 'Un indicador directo no admite numerador ni denominador.'
            if self.measured_value is not None and self.measured_value < 0:
                errors['measured_value'] = 'El valor medido no puede ser negativo.'
            if not (self.unit or '').strip():
                errors['unit'] = 'Indica la unidad de medición.'
        elif self.kind == self.Kind.PERCENTAGE:
            if self.measured_value is not None:
                errors['measured_value'] = 'Un porcentaje se calcula desde numerador y denominador.'
            if (self.numerator is None) != (self.denominator is None):
                errors['numerator'] = 'Completa numerador y denominador juntos.'
            if self.numerator is not None and self.numerator < 0:
                errors['numerator'] = 'El numerador no puede ser negativo.'
            if self.denominator is not None and self.denominator <= 0:
                errors['denominator'] = 'El denominador debe ser mayor que cero.'
            if self.unit != '%':
                errors['unit'] = 'La unidad del indicador porcentual debe ser %.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.milestone_id} · {self.name}'
