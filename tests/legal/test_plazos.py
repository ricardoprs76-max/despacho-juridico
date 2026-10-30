from datetime import date

import pytest

from agentes.legal.plazos import (
    CATALOGO,
    DISCLAIMER,
    PlazoDesconocido,
    calcular_plazo,
    en_vacancia_judicial,
    es_dia_habil,
    fecha_notificacion_efectiva,
    sumar_dias_habiles,
)


def test_weekend_and_holiday_not_business() -> None:
    assert not es_dia_habil(date(2026, 3, 7))  # Saturday
    assert not es_dia_habil(date(2026, 3, 8))  # Sunday
    assert not es_dia_habil(date(2026, 3, 23))  # San José (moved)
    assert es_dia_habil(date(2026, 3, 24))


def test_vacancy_bounds() -> None:
    assert es_dia_habil(date(2025, 12, 19))
    assert en_vacancia_judicial(date(2025, 12, 20))
    assert en_vacancia_judicial(date(2026, 1, 10))
    assert not es_dia_habil(date(2026, 1, 12))  # Reyes (moved), right after vacancy
    assert es_dia_habil(date(2026, 1, 13))


def test_holy_week_vacancy_2026() -> None:
    for day in (date(2026, 3, 30), date(2026, 3, 31), date(2026, 4, 1)):
        assert en_vacancia_judicial(day)
    assert not en_vacancia_judicial(date(2026, 4, 6))
    assert es_dia_habil(date(2026, 4, 6))


def test_petition_ignores_vacancy() -> None:
    assert es_dia_habil(date(2025, 12, 22), judicial=False)
    assert not es_dia_habil(date(2025, 12, 22))


def test_three_days_simple() -> None:
    assert calcular_plazo("reposicion", date(2026, 3, 2)).vencimiento == date(2026, 3, 5)


def test_counting_skips_holiday() -> None:
    # Fri 20/03 -> Mon 23/03 is a holiday -> 24, 25, 26
    assert calcular_plazo("reposicion", date(2026, 3, 20)).vencimiento == date(2026, 3, 26)


def test_crosses_year_and_vacancy() -> None:
    # 19/12 counts; 20/12-10/01 vacancy; 12/01 Reyes -> 13/01, 14/01
    result = calcular_plazo("reposicion", date(2025, 12, 18))
    assert result.vencimiento == date(2026, 1, 14)


def test_notified_on_saturday() -> None:
    result = calcular_plazo("reposicion", date(2026, 3, 7))
    assert result.inicio == date(2026, 3, 9)
    assert result.vencimiento == date(2026, 3, 11)


def test_electronic_notification_offset() -> None:
    assert fecha_notificacion_efectiva(date(2026, 3, 2)) == date(2026, 3, 4)
    # 10 business days from Wed 04/03: 5, 6, 9, 10, 11, 12, 13, 16, 17, 18
    result = calcular_plazo("excepciones_ejecutivo", date(2026, 3, 2), electronica=True)
    assert result.inicio == date(2026, 3, 5)
    assert result.vencimiento == date(2026, 3, 18)


def test_electronic_offset_ignored_for_recursos() -> None:
    # Autos are notified by estado; Ley 2213 art. 8 is for personal notification only.
    result = calcular_plazo("reposicion", date(2026, 3, 2), electronica=True)
    assert result.vencimiento == date(2026, 3, 5)
    assert "solo aplica a la notificación personal" in result.texto()
    assert "se entiende surtida" not in result.texto()


def test_petition_never_uses_ley_2213() -> None:
    result = calcular_plazo("respuesta_derecho_peticion", date(2026, 3, 2), electronica=True)
    assert (
        result.vencimiento
        == calcular_plazo("respuesta_derecho_peticion", date(2026, 3, 2)).vencimiento
    )


def test_personal_notification_terms() -> None:
    assert {k for k, t in CATALOGO.items() if t.admite_notif_personal} == {
        "contestacion_verbal",
        "contestacion_verbal_sumario",
        "excepciones_ejecutivo",
    }


def test_recursos_mention_fuera_de_audiencia() -> None:
    for key in ("reposicion", "apelacion_auto", "apelacion_sentencia"):
        text = calcular_plazo(key, date(2026, 3, 2)).texto()
        assert "fuera de audiencia" in text, key
    assert (
        "fuera de audiencia" not in calcular_plazo("contestacion_verbal", date(2026, 3, 2)).texto()
    )


def test_petition_text_says_radicacion() -> None:
    text = calcular_plazo("respuesta_derecho_peticion", date(2026, 3, 2)).texto()
    assert "Radicación: 02/03/2026." in text
    assert "Notificación:" not in text


def test_petition_variants() -> None:
    assert CATALOGO["respuesta_peticion_documentos"].dias == 10
    assert CATALOGO["respuesta_peticion_consulta"].dias == 30
    for key in ("respuesta_peticion_documentos", "respuesta_peticion_consulta"):
        assert CATALOGO[key].norma == "Ley 1755 de 2015 art. 14"
        assert CATALOGO[key].judicial is False


def test_notified_on_holiday() -> None:
    # Mon 23/03/2026 is San José: counting starts Tue 24/03
    result = calcular_plazo("reposicion", date(2026, 3, 23))
    assert result.inicio == date(2026, 3, 24)
    assert result.vencimiento == date(2026, 3, 26)


def test_notified_during_vacancy() -> None:
    # 22/12/2025 is vacancy; 12/01/2026 Reyes -> 13, 14, 15
    result = calcular_plazo("reposicion", date(2025, 12, 22))
    assert result.inicio == date(2026, 1, 13)
    assert result.vencimiento == date(2026, 1, 15)


def test_petition_15_days() -> None:
    # Business days after Mon 14/12/2026, not judicial: 15-18 (4), 21-24 (8), 25 holiday,
    # 28-31 (12), 01/01 holiday, 04, 05, 06/01/2027 (15). Reyes 2027 moves to Mon 11/01.
    result = calcular_plazo("respuesta_derecho_peticion", date(2026, 12, 14))
    assert result.vencimiento == date(2027, 1, 6)


def test_zero_days_rejected() -> None:
    with pytest.raises(ValueError, match="al menos un día"):
        sumar_dias_habiles(date(2026, 3, 2), 0)


def test_unknown_key_lists_options() -> None:
    with pytest.raises(PlazoDesconocido) as info:
        calcular_plazo("casacion", date(2026, 3, 2))
    message = str(info.value)
    assert "casacion" in message
    assert "reposicion" in message
    assert "impugnacion_tutela" in message


def test_catalogue_contents() -> None:
    assert {k: (t.dias, t.norma, t.judicial) for k, t in CATALOGO.items()} == {
        "reposicion": (3, "CGP art. 318", True),
        "apelacion_auto": (3, "CGP art. 322", True),
        "apelacion_sentencia": (3, "CGP art. 322", True),
        "contestacion_verbal": (20, "CGP art. 369", True),
        "contestacion_verbal_sumario": (10, "CGP art. 391", True),
        "excepciones_ejecutivo": (10, "CGP art. 442", True),
        "impugnacion_tutela": (3, "Decreto 2591 de 1991 art. 31", True),
        "respuesta_derecho_peticion": (15, "Ley 1755 de 2015 art. 14", False),
        "respuesta_peticion_documentos": (10, "Ley 1755 de 2015 art. 14", False),
        "respuesta_peticion_consulta": (30, "Ley 1755 de 2015 art. 14", False),
    }


def test_texto_format() -> None:
    text = calcular_plazo("reposicion", date(2026, 3, 2)).texto()
    assert text == (
        "Recurso de reposición (CGP art. 318): 3 días hábiles. Notificación: 02/03/2026. "
        "Corre desde 03/03/2026. Vence el 05/03/2026 (jueves). "
        "Aplica a providencias dictadas fuera de audiencia; si se dictan en audiencia, "
        "el recurso se interpone en ella.\n" + DISCLAIMER
    )
    assert DISCLAIMER == (
        "Cálculo orientativo: verifique el expediente, suspensiones y días de cierre "
        "extraordinario del despacho."
    )


def test_texto_electronic_line() -> None:
    text = calcular_plazo("excepciones_ejecutivo", date(2026, 3, 2), electronica=True).texto()
    assert (
        "Notificación personal por mensaje de datos: se entiende surtida el 04/03/2026 "
        "(Ley 2213 de 2022 art. 8). Según la sentencia C-420 de 2020, el término corre desde "
        "el acuse de recibo o desde que se constate el acceso al mensaje."
    ) in text
    assert "Vence el 18/03/2026 (miércoles)." in text
