"""Apuestas simples (grupos) y dual (eliminatoria: resultado + clasifica)."""

from __future__ import annotations

from typing import Any

from puntuacion_fases import PESO_POR_FASE

RESULTADOS_VALIDOS = frozenset({"1", "X", "2"})
CLASIFICA_VALIDOS = frozenset({"1", "2"})
PUNTOS_TERCER_PUESTO = {"resultado": 13, "clasifica": 12}


def es_eliminatoria(fase: str) -> bool:
    """Indica si la fase usa apuesta dual."""
    return fase != "grupos"


def puntos_por_tipo_apuesta(fase: str, tipo: str) -> int:
    """Puntos por acertar resultado o clasifica en una fase."""
    if fase == "grupos":
        return 1 if tipo == "resultado" else 0
    if fase == "tercer_puesto":
        return PUNTOS_TERCER_PUESTO[tipo]
    return PESO_POR_FASE[fase] // 2


def _validar_resultado(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip().upper()
    if texto.endswith(".0") and texto[:-2] in RESULTADOS_VALIDOS:
        texto = texto[:-2]
    if texto not in RESULTADOS_VALIDOS:
        raise ValueError(f"Resultado inválido: {valor!r} (esperado 1, X o 2).")
    return texto


def _validar_clasifica(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto not in CLASIFICA_VALIDOS:
        raise ValueError(f"Clasifica inválido: {valor!r} (esperado 1 o 2).")
    return texto


def normalizar_apuesta(valor: Any, fase: str) -> str | dict[str, str | None] | None:
    """Normaliza pronóstico o resultado según la fase."""
    if valor is None:
        return None

    if es_eliminatoria(fase):
        if isinstance(valor, str):
            return {"resultado": _validar_resultado(valor), "clasifica": None}
        if isinstance(valor, dict):
            return {
                "resultado": _validar_resultado(valor.get("resultado")),
                "clasifica": _validar_clasifica(valor.get("clasifica")),
            }
        raise ValueError(f"Apuesta eliminatoria inválida: {valor!r}.")

    if isinstance(valor, dict):
        return _validar_resultado(valor.get("resultado"))
    return _validar_resultado(valor)


def partido_tiene_resultado(valor: Any, fase: str) -> bool:
    """Indica si hay resultado oficial suficiente para puntuar."""
    if valor is None:
        return False
    if es_eliminatoria(fase):
        if isinstance(valor, dict):
            return valor.get("resultado") is not None
        return True
    return True


def contar_aciertos_apuesta(
    pronostico: Any,
    resultado: Any,
    fase: str,
) -> int:
    """Cuenta aciertos parciales (0–2 en eliminatoria, 0–1 en grupos)."""
    if not partido_tiene_resultado(resultado, fase):
        return 0

    pron = normalizar_apuesta(pronostico, fase)
    real = normalizar_apuesta(resultado, fase)
    if pron is None or real is None:
        return 0

    if es_eliminatoria(fase):
        assert isinstance(pron, dict)
        assert isinstance(real, dict)
        aciertos = 0
        if pron.get("resultado") and pron["resultado"] == real.get("resultado"):
            aciertos += 1
        if (
            pron.get("clasifica")
            and real.get("clasifica")
            and pron["clasifica"] == real["clasifica"]
        ):
            aciertos += 1
        return aciertos

    return 1 if pron == real else 0


def puntos_apuesta(pronostico: Any, resultado: Any, fase: str) -> int:
    """Calcula puntos obtenidos en un partido."""
    if not partido_tiene_resultado(resultado, fase):
        return 0

    pron = normalizar_apuesta(pronostico, fase)
    real = normalizar_apuesta(resultado, fase)
    if pron is None or real is None:
        return 0

    if es_eliminatoria(fase):
        assert isinstance(pron, dict)
        assert isinstance(real, dict)
        puntos = 0
        if pron.get("resultado") and pron["resultado"] == real.get("resultado"):
            puntos += puntos_por_tipo_apuesta(fase, "resultado")
        if (
            pron.get("clasifica")
            and real.get("clasifica")
            and pron["clasifica"] == real["clasifica"]
        ):
            puntos += puntos_por_tipo_apuesta(fase, "clasifica")
        return puntos

    if pron == real:
        return puntos_por_tipo_apuesta(fase, "resultado")
    return 0


def apuesta_completa(pronostico: Any, resultado: Any, fase: str) -> bool:
    """True si se acertaron todas las apuestas evaluables del partido."""
    if es_eliminatoria(fase):
        pron = normalizar_apuesta(pronostico, fase)
        real = normalizar_apuesta(resultado, fase)
        if not isinstance(pron, dict) or not isinstance(real, dict):
            return False
        partes = 0
        aciertos = 0
        if real.get("resultado") is not None and pron.get("resultado"):
            partes += 1
            if pron["resultado"] == real["resultado"]:
                aciertos += 1
        if real.get("clasifica") is not None and pron.get("clasifica"):
            partes += 1
            if pron["clasifica"] == real["clasifica"]:
                aciertos += 1
        return partes > 0 and aciertos == partes

    return pronostico is not None and pronostico == resultado
