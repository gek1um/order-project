"""Control de regresiones del cronograma para escrituras de calendarios y proyectos.

Debe ejecutarse bajo transaction.atomic(), tras bloquear el registro Project.
El servicio no hace escrituras: captura errores antes y comprueba que una operación
no incorpore errores nuevos. Las advertencias anteriores no impiden cambios.
"""
from collections import Counter

from rest_framework.exceptions import ValidationError

from scheduling.services.schedule_audit import ScheduleAuditService


class ScheduleConsistencyService:
    @staticmethod
    def _key(issue):
        # El mensaje distingue, por ejemplo, inicio y fin no laborables
        # que comparten código y task_id.
        return (
            issue.get("code"),
            issue.get("task_id"),
            issue.get("dependency_id"),
            issue.get("message"),
        )

    @classmethod
    def capture(cls, project_id):
        """Obtiene línea base de incidencias antes de la escritura."""
        return ScheduleAuditService.audit(project_id)

    @classmethod
    def validate_no_new_errors(cls, project_id, before):
        """Lanza error DRF 400 si la operación introduce errores nuevos.

        El caller debe ejecutarlo *dentro* de transaction.atomic().
        Si se produce una excepción, Django revierte el cambio.
        """
        after = ScheduleAuditService.audit(project_id)
        old_errors = Counter(
            cls._key(item) for item in before["issues"]
            if item["severity"] == "error"
        )
        new_items = []
        for item in after["issues"]:
            if item["severity"] != "error":
                continue
            key = cls._key(item)
            if old_errors[key]:
                old_errors[key] -= 1
            else:
                new_items.append(item)
        if new_items:
            raise ValidationError({
                "non_field_errors": [
                    "El cambio genera nuevas inconsistencias en el cronograma. "
                    "No se guardó la operación."
                ],
                "schedule_issues": new_items,
            })
        return after
