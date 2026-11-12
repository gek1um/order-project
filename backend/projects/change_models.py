from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ChangeRequest(models.Model):
    """Solicitud evaluable. No aplica modificaciones al cronograma por sí sola."""

    class Kind(models.TextChoices):
        SCOPE = "SCOPE", "Alcance"
        TIME = "TIME", "Tiempo"
        COST = "COST", "Costo"
        RESOURCE = "RESOURCE", "Recursos"
        TECHNOLOGY = "TECHNOLOGY", "Tecnología"
        ORGANIZATION = "ORGANIZATION", "Organización"

    class Priority(models.TextChoices):
        LOW = "LOW", "Baja"
        MEDIUM = "MEDIUM", "Media"
        HIGH = "HIGH", "Alta"
        CRITICAL = "CRITICAL", "Crítica"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Abierta"
        UNDER_REVIEW = "UNDER_REVIEW", "En evaluación"
        APPROVED = "APPROVED", "Aprobada"
        REJECTED = "REJECTED", "Rechazada"
        IMPLEMENTING = "IMPLEMENTING", "En implementación"
        CLOSED = "CLOSED", "Cerrada"

    project = models.ForeignKey('projects.Project', on_delete=models.PROTECT, related_name='change_requests')
    title = models.CharField(max_length=200)
    requester = models.CharField(max_length=150)
    requested_at = models.DateField(default=timezone.localdate)
    description = models.TextField()
    justification = models.TextField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    priority = models.CharField(max_length=12, choices=Priority.choices, default=Priority.MEDIUM)
    risk = models.TextField(blank=True, default='')
    impact_scope = models.TextField(blank=True, default='')
    impact_resources = models.TextField(blank=True, default='')
    estimated_delay_days = models.IntegerField(default=0, help_text='Impacto estimado en días calendario; positivo = retraso.')
    estimated_cost = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    actual_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    responsible = models.CharField(max_length=150, blank=True, default='')
    committed_date = models.DateField(null=True, blank=True)
    actual_completion_date = models.DateField(null=True, blank=True)
    result = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    decided_by = models.CharField(max_length=150, blank=True, default='')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_change_requests'
        ordering = ['-created_at', '-id']
        constraints = [
            models.CheckConstraint(condition=Q(estimated_cost__gte=0), name='change_estimated_cost_nonnegative'),
            models.CheckConstraint(condition=Q(actual_cost__isnull=True) | Q(actual_cost__gte=0), name='change_actual_cost_nonnegative'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.estimated_cost is not None and self.estimated_cost < 0:
            errors['estimated_cost'] = 'El costo estimado no puede ser negativo.'
        if self.actual_cost is not None and self.actual_cost < 0:
            errors['actual_cost'] = 'El costo real no puede ser negativo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Cambio #{self.pk} · {self.title}'


class ChangeEvent(models.Model):
    """Bitácora de acciones sobre una solicitud (solo lectura en API)."""
    change_request = models.ForeignKey(ChangeRequest, on_delete=models.PROTECT, related_name='events')
    action = models.CharField(max_length=30)
    from_status = models.CharField(max_length=20, blank=True, default='')
    to_status = models.CharField(max_length=20)
    actor = models.CharField(max_length=150)
    detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_change_events'
        ordering = ['created_at', 'id']


class ChangeApplication(models.Model):
    """Evidencia inmutable de una operación aplicada a una solicitud aprobada."""

    class Kind(models.TextChoices):
        SCHEDULE = 'SCHEDULE', 'Reprogramación'
        COST = 'COST', 'Registro de costo real'

    change_request = models.ForeignKey(
        ChangeRequest, on_delete=models.PROTECT, related_name='applications'
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    actor = models.CharField(max_length=150)
    task = models.ForeignKey(
        'tasks.Task', null=True, blank=True, on_delete=models.PROTECT,
        related_name='change_applications'
    )
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'project_change_applications'
        ordering = ['created_at', 'id']
