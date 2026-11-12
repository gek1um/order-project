
from datetime import date

from django.test import SimpleTestCase

from scheduling.services.calendar import (
    calculate_end_date,
    count_working_days,
    is_working_day,
    next_working_day,
    previous_working_day,
    shift_working_days,
)


class CalendarServiceTests(SimpleTestCase):
    """
    Pruebas del motor de calendario laboral.

    No requiere conexión a PostgreSQL.
    """

    def setUp(self):
        self.friday = date(2026, 11, 13)
        self.saturday = date(2026, 11, 14)
        self.sunday = date(2026, 11, 15)
        self.monday = date(2026, 11, 16)
        self.tuesday = date(2026, 11, 17)

    def test_friday_is_working_day(self):
        self.assertTrue(
            is_working_day(self.friday)
        )

    def test_weekend_is_not_working_day(self):
        self.assertFalse(
            is_working_day(self.saturday)
        )

        self.assertFalse(
            is_working_day(self.sunday)
        )

    def test_next_working_day_after_friday(self):
        result = next_working_day(
            self.friday,
            include_today=False,
        )

        self.assertEqual(
            result,
            self.monday,
        )

    def test_previous_working_day_before_monday(self):
        result = previous_working_day(
            self.monday,
            include_today=False,
        )

        self.assertEqual(
            result,
            self.friday,
        )

    def test_three_working_days_from_friday(self):
        result = calculate_end_date(
            self.friday,
            3,
        )

        self.assertEqual(
            result,
            self.tuesday,
        )

    def test_one_working_day_ends_same_day(self):
        result = calculate_end_date(
            self.friday,
            1,
        )

        self.assertEqual(
            result,
            self.friday,
        )

    def test_count_working_days_across_weekend(self):
        result = count_working_days(
            self.friday,
            self.tuesday,
        )

        self.assertEqual(
            result,
            3,
        )

    def test_holiday_is_excluded(self):
        holidays = {
            self.monday,
        }

        self.assertFalse(
            is_working_day(
                self.monday,
                holidays=holidays,
            )
        )

        result = calculate_end_date(
            self.friday,
            3,
            holidays=holidays,
        )

        self.assertEqual(
            result,
            date(2026, 11, 18),
        )

    def test_positive_working_day_shift(self):
        result = shift_working_days(
            self.friday,
            2,
        )

        self.assertEqual(
            result,
            self.tuesday,
        )

    def test_negative_working_day_shift(self):
        result = shift_working_days(
            self.monday,
            -1,
        )

        self.assertEqual(
            result,
            self.friday,
        )

    def test_reject_non_working_start(self):
        with self.assertRaises(ValueError):
            calculate_end_date(
                self.saturday,
                3,
            )

    def test_reject_invalid_duration_and_dates(self):
        with self.assertRaises(ValueError):
            calculate_end_date(
                self.friday,
                0,
            )

        with self.assertRaises(ValueError):
            count_working_days(
                self.tuesday,
                self.friday,
            )
