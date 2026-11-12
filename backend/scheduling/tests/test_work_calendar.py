
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project
from scheduling.models import (
    CalendarException,
    WorkCalendar,
)


class WorkCalendarTests(TestCase):
    """
    Pruebas de los calendarios laborales
    y sus excepciones.
    """

    def setUp(self):
        self.project = Project.objects.create(
            code="CAL-001",
            name="Proyecto de calendario",
            description="Pruebas de calendarios",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

        self.other_project = Project.objects.create(
            code="CAL-002",
            name="Segundo proyecto",
            description="Calendario independiente",
            manager_name="Responsable QA",
            status=Project.Status.PLANNED,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 12, 31),
            baseline_budget=Decimal("1000000.00"),
        )

    def create_calendar(self, project=None, **kwargs):
        calendar = WorkCalendar(
            project=project or self.project,
            **kwargs,
        )

        calendar.full_clean()
        calendar.save()

        return calendar

    def test_create_calendar_successfully(self):
        calendar = self.create_calendar()

        self.assertEqual(
            WorkCalendar.objects.count(),
            1,
        )

        self.assertEqual(
            calendar.project_id,
            self.project.id,
        )

    def test_default_working_days(self):
        calendar = self.create_calendar()

        self.assertEqual(
            calendar.working_weekdays,
            frozenset({0, 1, 2, 3, 4}),
        )

    def test_allow_custom_working_days(self):
        calendar = self.create_calendar(
            saturday=True,
            friday=False,
        )

        self.assertEqual(
            calendar.working_weekdays,
            frozenset({0, 1, 2, 3, 5}),
        )

    def test_reject_calendar_without_working_days(self):
        calendar = WorkCalendar(
            project=self.project,
            monday=False,
            tuesday=False,
            wednesday=False,
            thursday=False,
            friday=False,
            saturday=False,
            sunday=False,
        )

        with self.assertRaises(ValidationError):
            calendar.full_clean()

    def test_reject_second_calendar_for_same_project(self):
        self.create_calendar()

        duplicate = WorkCalendar(
            project=self.project,
            name="Calendario duplicado",
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_allow_different_project_calendars(self):
        self.create_calendar()

        self.create_calendar(
            project=self.other_project,
            saturday=True,
        )

        self.assertEqual(
            WorkCalendar.objects.count(),
            2,
        )

    def test_create_non_working_exception(self):
        calendar = self.create_calendar()

        exception = CalendarException(
            calendar=calendar,
            date=date(2026, 11, 16),
            is_working=False,
            description="Cierre excepcional",
        )

        exception.full_clean()
        exception.save()

        self.assertFalse(exception.is_working)

        self.assertEqual(
            calendar.exceptions.count(),
            1,
        )

    def test_create_extra_working_day(self):
        calendar = self.create_calendar()

        exception = CalendarException(
            calendar=calendar,
            date=date(2026, 11, 21),
            is_working=True,
            description="Jornada extraordinaria",
        )

        exception.full_clean()
        exception.save()

        self.assertTrue(exception.is_working)

    def test_reject_duplicate_exception_date(self):
        calendar = self.create_calendar()

        CalendarException.objects.create(
            calendar=calendar,
            date=date(2026, 11, 16),
            is_working=False,
        )

        duplicate = CalendarException(
            calendar=calendar,
            date=date(2026, 11, 16),
            is_working=True,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()
