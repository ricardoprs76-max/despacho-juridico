"""Procedural deadlines counted in business days (Código General del Proceso, art. 118).

- A term in days counts business days only and starts the day after notification.
- Judicial terms do not run during the judicial vacancy: 20 December to 10 January,
  and Monday to Wednesday of Holy Week (Thursday and Friday are holidays anyway).
- Ley 2213 de 2022, art. 8: a PERSONAL notification sent by data message (e.g. auto
  admisorio, mandamiento de pago) is understood done when two business days have passed
  after sending. Autos and sentencias notified by estado do not get those two days.
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
    # Only terms that start with a personal notification can use Ley 2213 art. 8.
    admite_notif_personal: bool = False
    # Recursos: the 3 days apply to decisions issued outside a hearing (CGP 318, 322).
    fuera_de_audiencia: bool = False


CATALOGO: dict[str, Termino] = {
    t.clave: t
    for t in (
        Termino("reposicion", "Recurso de reposición", 3, "CGP art. 318", fuera_de_audiencia=True),
        Termino("apelacion_auto", "Apelación de auto", 3, "CGP art. 322", fuera_de_audiencia=True),
        Termino(
            "apelacion_sentencia",
            "Apelación de sentencia",
            3,
            "CGP art. 322",
            fuera_de_audiencia=True,
        ),
        Termino(
            "contestacion_verbal",
            "Contestación de demanda en proceso verbal",
            20,
            "CGP art. 369",
            admite_notif_personal=True,
        ),
        Termino(
            "contestacion_verbal_sumario",
            "Contestación de demanda en proceso verbal sumario",
            10,
            "CGP art. 391",
            admite_notif_personal=True,
        ),
        Termino(
            "excepciones_ejecutivo",
            "Excepciones en proceso ejecutivo",
            10,
            "CGP art. 442",
            admite_notif_personal=True,
        ),
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
        Termino(
            "respuesta_peticion_documentos",
            "Respuesta a petición de documentos o información",
            10,
            "Ley 1755 de 2015 art. 14",
            judicial=False,
        ),
        Termino(
            "respuesta_peticion_consulta",
            "Respuesta a consulta (derecho de petición)",
            30,
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


_PERSONAL_RULE = (
    "Notificación personal por mensaje de datos: se entiende surtida el {fecha} "
    "(Ley 2213 de 2022 art. 8). Según la sentencia C-420 de 2020, el término corre desde "
    "el acuse de recibo o desde que se constate el acceso al mensaje."
)
_PERSONAL_NOT_APPLICABLE = (
    "La regla de los dos días de la Ley 2213 de 2022 art. 8 solo aplica a la notificación "
    "personal (por ejemplo, auto admisorio o mandamiento de pago); esta actuación se cuenta "
    "desde su notificación o radicación ordinaria."
)
_HEARING_NOTE = (
    "Aplica a providencias dictadas fuera de audiencia; si se dictan en audiencia, "
    "el recurso se interpone en ella."
)


@dataclass(frozen=True)
class ResultadoPlazo:
    termino: Termino
    notificacion: date
    inicio: date
    vencimiento: date
    electronica: bool
    efectiva: date
    electronica_no_aplica: bool = False

    def texto(self) -> str:
        t = self.termino
        label = "Notificación" if t.judicial else "Radicación"
        parts = [
            f"{t.nombre} ({t.norma}): {t.dias} días hábiles.",
            f"{label}: {_fmt(self.notificacion)}.",
        ]
        if self.electronica:
            parts.append(_PERSONAL_RULE.format(fecha=_fmt(self.efectiva)))
        parts += [
            f"Corre desde {_fmt(self.inicio)}.",
            f"Vence el {_fmt(self.vencimiento)} ({_WEEKDAYS[self.vencimiento.weekday()]}).",
        ]
        if t.fuera_de_audiencia:
            parts.append(_HEARING_NOTE)
        if self.electronica_no_aplica:
            parts.append(_PERSONAL_NOT_APPLICABLE)
        return " ".join(parts) + "\n" + DISCLAIMER


def calcular_plazo(clave: str, notificacion: date, electronica: bool = False) -> ResultadoPlazo:
    """Deadline for a catalogue term.

    electronica=True only shifts the start (Ley 2213 art. 8) for terms that begin with a
    personal notification; for the rest it is ignored and the text says why.
    """
    termino = CATALOGO.get(clave)
    if termino is None:
        options = ", ".join(sorted(CATALOGO))
        raise PlazoDesconocido(f"Actuación desconocida: {clave}. Opciones: {options}.")
    aplica = electronica and termino.admite_notif_personal
    efectiva = (
        fecha_notificacion_efectiva(notificacion, termino.judicial) if aplica else notificacion
    )
    return ResultadoPlazo(
        termino=termino,
        notificacion=notificacion,
        inicio=siguiente_dia_habil(efectiva, termino.judicial),
        vencimiento=sumar_dias_habiles(efectiva, termino.dias, termino.judicial),
        electronica=aplica,
        efectiva=efectiva,
        electronica_no_aplica=electronica and not aplica,
    )
