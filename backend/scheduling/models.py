
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from projects.models import Project
from tasks.models import Task


# ==================================================
# DEPENDENCIAS ENTRE TAREAS
# ==================================================

class TaskDependency(models.Model):
    """
    Relación dirigida entre dos tareas:

        predecessor -> successor

    Tipos admitidos:
    FS: Fin-Inicio
    SS: Inicio-Inicio
    FF: Fin-Fin
    SF: Inicio-Fin

    lag_days representa el desfase en días
    laborables. La propagación automática
    se implementará posteriormente.
    """

    class DependencyType(models.TextChoices):
        FINISH_TO_START = "FS", "Fin-Inicio"
        START_TO_START = "SS", "Inicio-Inicio"
        FINISH_TO_FINISH = "FF", "Fin-Fin"
        START_TO_FINISH = "SF", "Inicio-Fin"

    predecessor = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="outgoing_dependencies",
        verbose_name="Tarea predecesora",
    )

    successor = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="incoming_dependencies",
        verbose_name="Tarea sucesora",
    )

    dependency_type = models.CharField(
        max_length=2,
        choices=DependencyType.choices,
        default=DependencyType.FINISH_TO_START,
        verbose_name="Tipo de dependencia",
    )

    lag_days = models.IntegerField(
        default=0,
        verbose_name="Desfase en días laborables",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        db_table = "task_dependencies"

        verbose_name = "Dependencia de tarea"
        verbose_name_plural = "Dependencias de tareas"

        ordering = [
            "predecessor_id",
            "successor_id",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "predecessor",
                    "successor",
                ],
                name="unique_task_dependency",
            ),

            models.CheckConstraint(
                condition=~Q(
                    predecessor=F("successor")
                ),
                name="dependency_no_self_reference",
            ),
        ]

    def clean(self):
        """
        Valida:
        - Tipos y desfases.
        - Autodependencias.
        - Proyecto común.
        - Ciclos.
        """

        super().clean()

        valid_types = {
            value
            for value, _label in self.DependencyType.choices
        }

        if self.dependency_type not in valid_types:
            raise ValidationError({
                "dependency_type": (
                    "Tipo de dependencia no válido."
                )
            })

        if (
            isinstance(self.lag_days, bool)
            or not isinstance(self.lag_days, int)
        ):
            raise ValidationError({
                "lag_days": (
                    "El desfase debe ser un entero."
                )
            })

        if (
            self.predecessor_id is None
            or self.successor_id is None
        ):
            return

        if self.predecessor_id == self.successor_id:
            raise ValidationError({
                "successor": (
                    "Una tarea no puede depender "
                    "de sí misma."
                )
            })

        task_ids = {
            self.predecessor_id,
            self.successor_id,
        }

        tasks = {
            task.id: task
            for task in Task.objects.filter(
                id__in=task_ids
            )
        }

        if len(tasks) != 2:
            return

        predecessor = tasks[self.predecessor_id]
        successor = tasks[self.successor_id]

        if predecessor.project_id != successor.project_id:
            raise ValidationError({
                "successor": (
                    "Las tareas deben pertenecer "
                    "al mismo proyecto."
                )
            })

        if self._creates_cycle(
            project_id=predecessor.project_id
        ):
            raise ValidationError({
                "successor": (
                    "La dependencia genera un ciclo "
                    "en el cronograma."
                )
            })

    def _creates_cycle(self, project_id: int) -> bool:
        """
        Detecta si agregar predecessor -> successor
        crearía un ciclo dirigido.
        """

        dependencies = TaskDependency.objects.filter(
            predecessor__project_id=project_id
        )

        if self.pk is not None:
            dependencies = dependencies.exclude(
                pk=self.pk
            )

        graph = {}

        for predecessor_id, successor_id in (
            dependencies.values_list(
                "predecessor_id",
                "successor_id",
            )
        ):
            graph.setdefault(
                predecessor_id,
                set(),
            ).add(successor_id)

        pending = [self.successor_id]
        visited = set()

        while pending:
            current = pending.pop()

            if current == self.predecessor_id:
                return True

            if current in visited:
                continue

            visited.add(current)

            pending.extend(
                graph.get(current, set()) - visited
            )

        return False

    def __str__(self):
        return (
            f"{self.predecessor_id} -> "
            f"{self.successor_id} "
            f"({self.dependency_type}, "
            f"desfase={self.lag_days})"
        )


# ==================================================
# CALENDARIO LABORAL DE UN PROYECTO
# ==================================================

class WorkCalendar(models.Model):
    """
    Define qué días de la semana son laborables
    para un proyecto.

    Cada proyecto puede tener como máximo
    un calendario.

    Los proyectos sin calendario utilizarán
    las reglas predeterminadas del motor hasta
    que configuremos su integración.
    """

    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="work_calendar",
        verbose_name="Proyecto",
    )

    name = models.CharField(
        max_length=150,
        default="Calendario laboral",
        verbose_name="Nombre del calendario",
    )

    monday = models.BooleanField(
        default=True,
        verbose_name="Lunes",
    )

    tuesday = models.BooleanField(
        default=True,
        verbose_name="Martes",
    )

    wednesday = models.BooleanField(
        default=True,
        verbose_name="Miércoles",
    )

    thursday = models.BooleanField(
        default=True,
        verbose_name="Jueves",
    )

    friday = models.BooleanField(
        default=True,
        verbose_name="Viernes",
    )

    saturday = models.BooleanField(
        default=False,
        verbose_name="Sábado",
    )

    sunday = models.BooleanField(
        default=False,
        verbose_name="Domingo",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "work_calendars"

        verbose_name = "Calendario laboral"
        verbose_name_plural = "Calendarios laborales"

        ordering = ["project_id"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(monday=True)
                    | Q(tuesday=True)
                    | Q(wednesday=True)
                    | Q(thursday=True)
                    | Q(friday=True)
                    | Q(saturday=True)
                    | Q(sunday=True)
                ),
                name="calendar_has_working_day",
            ),
        ]

    def clean(self):
        super().clean()

        if not self.working_weekdays:
            raise ValidationError({
                "monday": (
                    "El calendario debe tener "
                    "al menos un día laborable."
                )
            })

    @property
    def working_weekdays(self) -> frozenset[int]:
        """
        Devuelve los índices de los días laborables:

        0 = lunes
        1 = martes
        ...
        6 = domingo

        Compatible con datetime.date.weekday().
        """

        flags = [
            self.monday,
            self.tuesday,
            self.wednesday,
            self.thursday,
            self.friday,
            self.saturday,
            self.sunday,
        ]

        return frozenset(
            index
            for index, enabled in enumerate(flags)
            if enabled
        )

    def __str__(self):
        return (
            f"{self.project.code} - {self.name}"
        )


# ==================================================
# EXCEPCIONES DEL CALENDARIO
# ==================================================

class CalendarException(models.Model):
    """
    Sobrescribe la regla semanal para una fecha.

    is_working=False:
        Día no laborable excepcional.

    is_working=True:
        Día laborable excepcional.

    Cada fecha solo puede tener una excepción
    dentro del mismo calendario.
    """

    calendar = models.ForeignKey(
        WorkCalendar,
        on_delete=models.CASCADE,
        related_name="exceptions",
        verbose_name="Calendario",
    )

    date = models.DateField(
        verbose_name="Fecha",
    )

    is_working = models.BooleanField(
        default=False,
        verbose_name="¿Es laborable?",
    )

    description = models.CharField(
        max_length=250,
        blank=True,
        verbose_name="Descripción",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "calendar_exceptions"

        verbose_name = "Excepción del calendario"
        verbose_name_plural = "Excepciones del calendario"

        ordering = ["date", "id"]

        constraints = [
            models.UniqueConstraint(
                fields=["calendar", "date"],
                name="unique_calendar_exception_date",
            ),
        ]

    def __str__(self):
        label = "Laborable" if self.is_working else "No laborable"

        return (
            f"{self.calendar.project.code} - "
            f"{self.date} - {label}"
        )
