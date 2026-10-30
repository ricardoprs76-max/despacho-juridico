"""Colombian public holidays (días festivos).

Three kinds:
- fixed dates;
- dates moved to the following Monday by Ley 51 de 1983 ("Ley Emiliani");
- dates that depend on Easter Sunday (two not moved, three moved to Monday).
"""

from datetime import date, timedelta
from functools import cache

_FIXED: dict[tuple[int, int], str] = {
    (1, 1): "Año Nuevo",
    (5, 1): "Día del Trabajo",
    (7, 20): "Día de la Independencia",
    (8, 7): "Batalla de Boyacá",
    (12, 8): "La Inmaculada Concepción",
    (12, 25): "Navidad",
}

_MOVED_TO_MONDAY: dict[tuple[int, int], str] = {
    (1, 6): "Día de los Reyes Magos",
    (3, 19): "Día de San José",
    (6, 29): "San Pedro y San Pablo",
    (8, 15): "La Asunción de la Virgen",
    (10, 12): "Día de la Raza",
    (11, 1): "Todos los Santos",
    (11, 11): "Independencia de Cartagena",
}

# Offset in days from Easter Sunday, name, and whether Ley 51 moves it to Monday.
_EASTER_BASED: tuple[tuple[int, str, bool], ...] = (
    (-3, "Jueves Santo", False),
    (-2, "Viernes Santo", False),
    (39, "Ascensión del Señor", True),
    (60, "Corpus Christi", True),
    (68, "Sagrado Corazón", True),
)


def easter_sunday(year: int) -> date:
    """Easter Sunday in the Gregorian calendar (anonymous / Meeus algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    weekday_shift = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * weekday_shift) // 451
    month, day = divmod(h + weekday_shift - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _next_monday(day: date) -> date:
    return day + timedelta(days=(7 - day.weekday()) % 7)


@cache
def festivos(year: int) -> dict[date, str]:
    """All holidays of a year: date -> Spanish name ("A / B" when two share a date)."""
    days: dict[date, list[str]] = {}

    def add(day: date, name: str) -> None:
        days.setdefault(day, []).append(name)

    for (month, dom), name in _FIXED.items():
        add(date(year, month, dom), name)
    for (month, dom), name in _MOVED_TO_MONDAY.items():
        add(_next_monday(date(year, month, dom)), name)
    easter = easter_sunday(year)
    for offset, name, moved in _EASTER_BASED:
        day = easter + timedelta(days=offset)
        add(_next_monday(day) if moved else day, name)
    return {day: " / ".join(names) for day, names in sorted(days.items())}


def es_festivo(day: date) -> bool:
    return day in festivos(day.year)
