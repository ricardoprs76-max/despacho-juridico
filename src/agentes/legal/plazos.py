"""Procedural deadlines counted in business days (Código General del Proceso, art. 118).

- A term in days counts business days only and starts the day after notification.
- Judicial terms do not run during the judicial vacancy: 20 December to 10 January,
  and Monday to Wednesday of Holy Week (Thursday and Friday are holidays anyway).
- Ley 2213 de 2022, art. 8: a personal notification sent by data message is understood
  done when two business days have passed after sending.
- Administrative terms (e.g. derecho de petición) skip weekends and holidays only.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from agentes.legal.festivos import easter_sunday, es_festivo

DISCLAIMER = (
    "Cálculo orientativo: verifique el expediente, suspensiones y días de cierre "
    "extraordinario del despacho."
)
_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


@dataclass(frozen=True)
class Termino:
    clave: str
    nombre: str
    dias: int
    norma: str
    judicial: bool = True


CATALOGO: dict[str, Termino] = {
    t.clave: t
    for t in (
        Termino("reposicion", "Recurso de reposición", 3, "CGP art. 318"),
        Termino("apelacion_auto", "Apelación de auto", 3, "CGP art. 322"),
        Termino("apelacion_sentencia", "Apelación de sentencia", 3, "CGP art. 322"),
        Termino(
            "contestacion_verbal", "Contestación de demanda en proceso verbal", 20, "CGP art. 369"
        ),
        Termino(
            "contestacion_verbal_sumario",
            "Contestación de demanda en proceso verbal sumario",
            10,
            "CGP art. 391",
        ),
        Termino("excepciones_ejecutivo", "Excepciones en proceso ejecutivo", 10, "CGP art. 442"),
        Termino(
            "impugnacion_tutela",
            "Impugnación de fallo de tutela",
            3,
            "Decreto 2591 de 1991 art. 31",
        ),
        Termino(
            "respuesta_derecho_peticion",
            "Respuesta a derecho de petición",
            15,
            "Ley 1755 de 2015 art. 14",
            judicial=False,
        ),
    )
}


class PlazoDesconocido(KeyError):
    """The requested procedural action is not in the catalogue."""

    def __str__(self) -> str:
        return str(self.args[0])


def en_vacancia_judicial(day: date) -> bool:
    if (day.month == 12 and day.day >= 20) or (day.month == 1 and day.day <= 10):
        return True
    holy_monday = easter_sunday(day.year) - timedelta(days=6)
    return holy_monday <= day <= holy_monday + timedelta(days=2)


def es_dia_habil(day: date, judicial: bool = True) -> bool:
    if day.weekday() >= 5 or es_festivo(day):
        return False
    return not (judicial and en_vacancia_judicial(day))


def siguiente_dia_habil(day: date, judicial: bool = True) -> date:
    """First business day strictly after day."""
    day += timedelta(days=1)
    while not es_dia_habil(day, judicial):
        day += timedelta(days=1)
    return day


def sumar_dias_habiles(desde: date, dias: int, judicial: bool = True) -> date:
    """The dias-th business day strictly after desde."""
    if dias < 1:
        raise ValueError("El término debe ser de al menos un día.")
    day = desde
    for _ in range(dias):
        day = siguiente_dia_habil(day, judicial)
    return day


def fecha_notificacion_efectiva(envio: date, judicial: bool = True) -> date:
    """Ley 2213 de 2022 art. 8: done once two business days have passed after sending."""
    return sumar_dias_habiles(envio, 2, judicial)


def _fmt(day: date) -> str:
    return day.strftime("%d/%m/%Y")


@dataclass(frozen=True)
class ResultadoPlazo:
    termino: Termino
    notificacion: date
    inicio: date
    vencimiento: date
    electronica: bool
    efectiva: date

    def texto(self) -> str:
        t = self.termino
        parts = [
            f"{t.nombre} ({t.norma}): {t.dias} días hábiles.",
            f"Notificación: {_fmt(self.notificacion)}.",
        ]
        if self.electronica:
            parts.append(
                f"Notificación electrónica: se entiende surtida el {_fmt(self.efectiva)} "
                "(Ley 2213 de 2022 art. 8)."
            )
        parts += [
            f"Corre desde {_fmt(self.inicio)}.",
            f"Vence el {_fmt(self.vencimiento)} ({_WEEKDAYS[self.vencimiento.weekday()]}).",
        ]
        return " ".join(parts) + "\n" + DISCLAIMER


def calcular_plazo(clave: str, notificacion: date, electronica: bool = False) -> ResultadoPlazo:
    termino = CATALOGO.get(clave)
    if termino is None:
        options = ", ".join(sorted(CATALOGO))
        raise PlazoDesconocido(f"Actuación desconocida: {clave}. Opciones: {options}.")
    efectiva = (
        fecha_notificacion_efectiva(notificacion, termino.judicial) if electronica else notificacion
    )
    return ResultadoPlazo(
        termino=termino,
        notificacion=notificacion,
        inicio=siguiente_dia_habil(efectiva, termino.judicial),
        vencimiento=sumar_dias_habiles(efectiva, termino.dias, termino.judicial),
        electronica=electronica,
        efectiva=efectiva,
    )
