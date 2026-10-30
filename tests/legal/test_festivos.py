from datetime import date

import pytest

from agentes.legal import easter_sunday, es_festivo, festivos


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ],
)
def test_easter_known_years(year: int, expected: date) -> None:
    assert easter_sunday(year) == expected


def test_festivos_2026_exact() -> None:
    expected = [
        "01-01",
        "01-12",
        "03-23",
        "04-02",
        "04-03",
        "05-01",
        "05-18",
        "06-08",
        "06-15",
        "06-29",
        "07-20",
        "08-07",
        "08-17",
        "10-12",
        "11-02",
        "11-16",
        "12-08",
        "12-25",
    ]
    assert sorted(d.strftime("%m-%d") for d in festivos(2026)) == expected


def test_festivos_2025_shared_monday() -> None:
    days = festivos(2025)
    assert len(days) == 17
    name = days[date(2025, 6, 30)]
    assert "San Pedro y San Pablo" in name
    assert "Sagrado Corazón" in name


def test_holiday_already_monday_not_moved() -> None:
    assert es_festivo(date(2026, 6, 29))
    assert es_festivo(date(2026, 10, 12))
    assert not es_festivo(date(2026, 7, 6))


def test_names_are_spanish() -> None:
    days = festivos(2026)
    assert days[date(2026, 8, 17)] == "La Asunción de la Virgen"
    assert days[date(2026, 4, 3)] == "Viernes Santo"
    assert days[date(2026, 7, 20)] == "Día de la Independencia"


def test_ordinary_day_is_not_holiday() -> None:
    assert not es_festivo(date(2026, 3, 2))
