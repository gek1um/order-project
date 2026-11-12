
"""
Motor base de calendario laboral de order-project.

Convenciones:
- Los días laborables por defecto son lunes a viernes.
- Los feriados pueden enviarse como fechas.
- La duración cuenta ambos extremos del intervalo.
- Una tarea de un día inicia y termina el mismo día.
- Los desplazamientos pueden ser positivos o negativos.

Este módulo no modifica registros de PostgreSQL.
"""

from datetime import date, timedelta
from typing import Collection


DEFAULT_WORKING_WEEKDAYS = frozenset({
    0,  # Lunes
    1,  # Martes
    2,  # Miércoles
    3,  # Jueves
    4,  # Viernes
})


def _validate_calendar(
    working_weekdays: Collection[int],
) -> None:
    """
    Comprueba que exista al menos un día laborable
    y que los valores estén entre 0 y 6.
    """

    if not working_weekdays:
        raise ValueError(
            "El calendario debe tener al menos "
            "un día laborable."
        )

    for day in working_weekdays:
        if (
            isinstance(day, bool)
            or not isinstance(day, int)
            or day < 0
            or day > 6
        ):
            raise ValueError(
                "Los días laborales deben ser "
                "números enteros entre 0 y 6."
            )


def is_working_day(
    day: date,
    holidays: Collection[date] = frozenset(),
    working_weekdays: Collection[int] = DEFAULT_WORKING_WEEKDAYS,
) -> bool:
    """
    Indica si una fecha es laborable.

    weekday():
        0 = lunes
        6 = domingo
    """

    _validate_calendar(working_weekdays)

    return (
        day.weekday() in working_weekdays
        and day not in holidays
    )


def next_working_day(
    day: date,
    holidays: Collection[date] = frozenset(),
    working_weekdays: Collection[int] = DEFAULT_WORKING_WEEKDAYS,
    include_today: bool = True,
) -> date:
    """
    Obtiene el siguiente día laborable.

    Si include_today=True y la fecha ya es
    laborable, devuelve esa misma fecha.
    """

    _validate_calendar(working_weekdays)

    current = day

    if not include_today:
        current += timedelta(days=1)

    # Límite de seguridad frente a calendarios
    # con períodos excepcionalmente largos sin
    # días disponibles.
    for _ in range(36600):
        if is_working_day(
            current,
            holidays,
            working_weekdays,
        ):
            return current

        current += timedelta(days=1)

    raise ValueError(
        "No se encontró un día laborable disponible."
    )


def previous_working_day(
    day: date,
    holidays: Collection[date] = frozenset(),
    working_weekdays: Collection[int] = DEFAULT_WORKING_WEEKDAYS,
    include_today: bool = True,
) -> date:
    """
    Obtiene el día laborable anterior.
    """

    _validate_calendar(working_weekdays)

    current = day

    if not include_today:
        current -= timedelta(days=1)

    for _ in range(36600):
        if is_working_day(
            current,
            holidays,
            working_weekdays,
        ):
            return current

        current -= timedelta(days=1)

    raise ValueError(
        "No se encontró un día laborable disponible."
    )


def shift_working_days(
    day: date,
    offset: int,
    holidays: Collection[date] = frozenset(),
    working_weekdays: Collection[int] = DEFAULT_WORKING_WEEKDAYS,
) -> date:
    """
    Desplaza una fecha una cantidad de días
    laborables.

    offset =  0 -> devuelve la fecha original
    offset =  2 -> avanza dos días laborables
    offset = -2 -> retrocede dos días laborables

    El día de origen no cuenta como un paso.
    """

    _validate_calendar(working_weekdays)

    if isinstance(offset, bool) or not isinstance(offset, int):
        raise ValueError(
            "El desplazamiento debe ser un entero."
        )

    if offset == 0:
        return day

    direction = 1 if offset > 0 else -1

    remaining = abs(offset)
    current = day

    while remaining > 0:
        current += timedelta(days=direction)

        if is_working_day(
            current,
            holidays,
            working_weekdays,
        ):
            remaining -= 1

    return current


def calculate_end_date(
    start_date: date,
    duration_days: int,
    holidays: Collection[date] = frozenset(),
    working_weekdays: Collection[int] = DEFAULT_WORKING_WEEKDAYS,
) -> date:
    """
    Calcula la fecha de término a partir de una
    fecha de inicio y una duración laborable.

    Convención inclusiva:
    - Duración 1: termina el día de inicio.
    - Duración 3: inicio + 2 días laborables.

    El inicio debe ser un día laborable.
    """

    _validate_calendar(working_weekdays)

    if (
        isinstance(duration_days, bool)
        or not isinstance(duration_days, int)
        or duration_days < 1
    ):
        raise ValueError(
            "La duración debe ser un entero "
            "igual o mayor que 1."
        )

    if not is_working_day(
        start_date,
        holidays,
        working_weekdays,
    ):
        raise ValueError(
            "La fecha de inicio debe ser laborable."
        )

    return shift_working_days(
        start_date,
        duration_days - 1,
        holidays,
        working_weekdays,
    )


def count_working_days(
    start_date: date,
    end_date: date,
    holidays: Collection[date] = frozenset(),
    working_weekdays: Collection[int] = DEFAULT_WORKING_WEEKDAYS,
) -> int:
    """
    Cuenta los días laborables de un período.

    El intervalo es inclusivo:
    incluye inicio y término si son laborables.
    """

    _validate_calendar(working_weekdays)

    if end_date < start_date:
        raise ValueError(
            "La fecha de término no puede ser "
            "anterior a la fecha de inicio."
        )

    total = 0
    current = start_date

    while current <= end_date:
        if is_working_day(
            current,
            holidays,
            working_weekdays,
        ):
            total += 1

        current += timedelta(days=1)

    return total
