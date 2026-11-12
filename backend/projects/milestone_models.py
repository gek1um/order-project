from django.core.exceptions import ValidationError
from django.db import models
from .models import Project


class Milestone(models.Model):
    """Hito independiente de las actividades del cronograma."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        COMPLETED = 'COMPLETED', 'Cumplido'

    project = models.ForeignKey(Project, related_name='milestones', on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    tasks = models.ManyToManyField('tasks.Task', blank=True, related_name='milestones')
    due_date = models.DateField()
    responsible = models.CharField(max_length=150)
    acceptance_criteria = models.TextField()
    evidence = models.TextField(blank=True, default='')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    completed_at = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'project_milestones'
        ordering = ['due_date', 'id']

    def clean(self):
        super().clean()
        errors = {}
        if self.project_id and self.due_date:
            if not (self.project.start_date <= self.due_date <= self.project.end_date):
                errors['due_date'] = 'El hito debe estar dentro de las fechas del proyecto.'
        if self.status == self.Status.COMPLETED:
            if not self.completed_at:
                errors['completed_at'] = 'Registra la fecha real de cumplimiento.'
            if not (self.evidence or '').strip():
                errors['evidence'] = 'Registra evidencia para cumplir el hito.'
        elif self.completed_at is not None:
            errors['completed_at'] = 'Un hito pendiente no puede tener fecha de cumplimiento.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.project.code} · {self.name}'
