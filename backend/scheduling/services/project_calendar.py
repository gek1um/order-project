
"""
Calendario laboral vinculado a un proyecto.

Prioridad de reglas:
1. Excepción específica de una fecha.
2. Días semanales configurados en WorkCalendar.
3. Lunes a viernes si no existe WorkCalendar.

Las duraciones son inclusivas:
una actividad de 1 día comienza y termina
en la misma fecha laborable.
"""

from datetime import date, timedelta

from scheduling.models import WorkCalendar
from scheduling.services.calendar import (
    DEFAULT_WORKING_WEEKDAYS,
)


class ProjectCalendarService:
    MAX_SEARCH_DAYS = 36600

    def __init__(self, project_id: int):
        self.project_id = project_id

        self.calendar = (
            WorkCalendar.objects
            .filter(project_id=project_id)
            .first()
        )

        if self.calendar is None:
            self.working_weekdays = (
                DEFAULT_WORKING_WEEKDAYS
            )
            self.exceptions = {}
        else:
            self.working_weekdays = (
                self.calendar.working_weekdays
            )

            self.exceptions = dict(
                self.calendar.exceptions.values_list(
                    "date",
                    "is_working",
                )
            )

        if not self.working_weekdays:
            raise ValueError(
                "El calendario no tiene días "
                "laborables configurados."
            )

    @property
    def source(self) -> str:
        return (
            "configured"
            if self.calendar is not None
            else "default"
        )

    def is_working_day(self, day: date) -> bool:
        """
        La excepción tiene prioridad sobre
        la regla semanal, incluso si habilita
        un sábado o domingo.
        """

        if day in self.exceptions:
            return self.exceptions[day]

        return day.weekday() in self.working_weekdays

    def next_working_day(
        self,
        day: date,
        include_today: bool = True,
    ) -> date:
        current = day

        if not include_today:
            current += timedelta(days=1)

        for _ in range(self.MAX_SEARCH_DAYS):
            if self.is_working_day(current):
                return current

            current += timedelta(days=1)

        raise ValueError(
            "No se encontró un día laborable."
        )

    def previous_working_day(
        self,
        day: date,
        include_today: bool = True,
    ) -> date:
        current = day

        if not include_today:
            current -= timedelta(days=1)

        for _ in range(self.MAX_SEARCH_DAYS):
            if self.is_working_day(current):
                return current

            current -= timedelta(days=1)

        raise ValueError(
            "No se encontró un día laborable."
        )

    def shift_working_days(
        self,
        day: date,
        offset: int,
    ) -> date:
        """
        Desplaza una fecha en días laborables.

        El día de origen no cuenta como paso.
        El desplazamiento cero conserva la fecha.
        """

        if isinstance(offset, bool) or not isinstance(
            offset, int
        ):
            raise ValueError(
                "El desplazamiento debe ser entero."
            )

        if offset == 0:
            return day

        direction = 1 if offset > 0 else -1
        remaining = abs(offset)
        current = day
        searched = 0

        while remaining > 0:
            current += timedelta(days=direction)
            searched += 1

            if searched > self.MAX_SEARCH_DAYS:
                raise ValueError(
                    "Desplazamiento fuera del "
                    "rango de búsqueda."
                )

            if self.is_working_day(current):
                remaining -= 1

        return current

    def calculate_end_date(
        self,
        start_date: date,
        duration_days: int,
    ) -> date:
        """
        Cuenta el inicio como primer día
        laborable de la actividad.
        """

        if (
            isinstance(duration_days, bool)
            or not isinstance(duration_days, int)
            or duration_days < 1
        ):
            raise ValueError(
                "La duración debe ser un entero "
                "igual o mayor que uno."
            )

        if not self.is_working_day(start_date):
            raise ValueError(
                "El inicio debe ser laborable."
            )

        return self.shift_working_days(
            start_date,
            duration_days - 1,
        )

    def count_working_days(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        """
        Cuenta días laborables entre dos fechas,
        incluyendo ambos extremos.
        """

        if end_date < start_date:
            raise ValueError(
                "El término no puede ser anterior "
                "al inicio."
            )

        total = 0
        current = start_date

        while current <= end_date:
            if self.is_working_day(current):
                total += 1

            current += timedelta(days=1)

        return total
