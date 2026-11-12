"""Validación temporal de una dependencia después de guardarla.

Se ejecuta dentro de la misma transacción que crea o actualiza la relación.
Si la relación nueva no es satisfacible con las fechas actuales, la vista
lanza un error y PostgreSQL revierte la escritura.

La comprobación es deliberadamente local: no bloquea la operación por
inconsistencias preexistentes ajenas a la dependencia editada.
"""

from rest_framework.exceptions import ValidationError

from scheduling.services.schedule_audit import ScheduleAuditService


class DependencyConsistencyService:
    RELEVANT_CODES = frozenset({
        "INVALID_DEPENDENCY",
        "DEPENDENCY_DATES_INVALID",
        "DEPENDENCY_NOT_EVALUABLE",
        "DEPENDENCY_VIOLATION",
    })

    @classmethod
    def validate_saved_dependency(cls, dependency):
        report = ScheduleAuditService.audit(dependency.predecessor.project_id)
        issues = [
            issue for issue in report["issues"]
            if issue["dependency_id"] == dependency.pk
            and issue["severity"] == "error"
            and issue["code"] in cls.RELEVANT_CODES
        ]
        if issues:
            raise ValidationError({
                "non_field_errors": [
                    "La dependencia no es compatible con el cronograma actual. "
                    "Reprograma primero las actividades involucradas."
                ],
                "schedule_issues": issues,
            })
        return report
