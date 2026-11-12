from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class TaskResourceAssignment(models.Model):
    """Asignación valorizada de un recurso a una actividad.

    `planned_units` y `actual_units` expresan consumo de unidades facturables.
    Profesionales: horas-persona. Materiales: unidades. Licencias/equipos:
    unidades-período (ej.: dos licencias durante tres meses = 6).
    Los precios se congelan al asignar; nunca se recalculan desde catálogo.
    """

    task = models.ForeignKey(
        'tasks.Task', on_delete=models.PROTECT, related_name='resource_assignments'
    )
    resource = models.ForeignKey(
        'projects.Resource', on_delete=models.PROTECT, related_name='task_assignments'
    )
    planned_units = models.DecimalField(max_digits=12, decimal_places=2)
    actual_units = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    planned_unit_cost = models.DecimalField(max_digits=15, decimal_places=2)
    actual_unit_cost = models.DecimalField(max_digits=15, decimal_places=2)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'task_resource_assignments'
        ordering = ['task_id', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(planned_units__gt=0), name='assignment_planned_units_positive'),
            models.CheckConstraint(condition=Q(actual_units__gte=0), name='assignment_actual_units_nonnegative'),
            models.CheckConstraint(condition=Q(planned_unit_cost__gte=0), name='assignment_planned_cost_nonnegative'),
            models.CheckConstraint(condition=Q(actual_unit_cost__gte=0), name='assignment_actual_cost_nonnegative'),
        ]

    @property
    def planned_cost(self):
        return (self.planned_units * self.planned_unit_cost).quantize(Decimal('0.01'))

    @property
    def actual_cost(self):
        return (self.actual_units * self.actual_unit_cost).quantize(Decimal('0.01'))

    def clean(self):
        super().clean()
        errors = {}
        if self.task_id and self.resource_id:
            if self.task.project_id != self.resource.project_id:
                errors['resource'] = 'La actividad y el recurso deben pertenecer al mismo proyecto.'
        if self.planned_units is not None and self.planned_units <= 0:
            errors['planned_units'] = 'Las unidades planificadas deben ser mayores que cero.'
        if self.actual_units is not None and self.actual_units < 0:
            errors['actual_units'] = 'Las unidades reales no pueden ser negativas.'
        for field in ('planned_unit_cost', 'actual_unit_cost'):
            value = getattr(self, field)
            if value is not None and value < 0:
                errors[field] = 'El costo unitario no puede ser negativo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.task_id} · {self.resource_id} · {self.planned_units}'
