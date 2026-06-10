"""Configuración definitiva de fases y pesos — Mundial 2026 (104 partidos)."""

from __future__ import annotations

from dataclasses import dataclass

TOTAL_PARTIDOS = 104
PUNTOS_MAXIMOS = 275


@dataclass(frozen=True)
class ConfigFase:
    fase: str
    peso: int
    inicio: int
    fin: int
    partidos: int

    @property
    def puntos_maximos(self) -> int:
        return self.partidos * self.peso


FASES: tuple[ConfigFase, ...] = (
    ConfigFase("grupos", 1, 1, 72, 72),
    ConfigFase("dieciseisavos", 2, 73, 88, 16),
    ConfigFase("octavos", 4, 89, 96, 8),
    ConfigFase("cuartos", 8, 97, 100, 4),
    ConfigFase("semifinales", 16, 101, 102, 2),
    ConfigFase("tercer_puesto", 25, 103, 103, 1),
    ConfigFase("final", 50, 104, 104, 1),
)

FASES_VALIDAS = frozenset(config.fase for config in FASES)
PESO_POR_FASE = {config.fase: config.peso for config in FASES}


def asignar_fase_y_peso(partido_id: int) -> tuple[str, int]:
    """Devuelve fase y peso según la posición del partido."""
    for config in FASES:
        if config.inicio <= partido_id <= config.fin:
            return config.fase, config.peso

    raise ValueError(
        f"Partido {partido_id} fuera de rango válido (1-{TOTAL_PARTIDOS})."
    )


def validar_fase_y_peso(partido_id: int, fase: str, peso: int) -> list[str]:
    """Devuelve advertencias si la fase o el peso no son válidos."""
    advertencias: list[str] = []

    if fase not in FASES_VALIDAS:
        advertencias.append(f"Partido {partido_id}: fase '{fase}' no es válida.")

    if peso <= 0:
        advertencias.append(f"Partido {partido_id}: peso {peso} debe ser positivo.")

    if fase in PESO_POR_FASE and peso != PESO_POR_FASE[fase]:
        advertencias.append(
            f"Partido {partido_id}: peso {peso} no coincide con la fase '{fase}' "
            f"(esperado: {PESO_POR_FASE[fase]})."
        )

    try:
        fase_esperada, peso_esperado = asignar_fase_y_peso(partido_id)
    except ValueError as exc:
        advertencias.append(str(exc))
        return advertencias

    if fase != fase_esperada or peso != peso_esperado:
        advertencias.append(
            f"Partido {partido_id}: corregido de "
            f"'{fase}'/{peso} a '{fase_esperada}'/{peso_esperado}."
        )

    return advertencias


def validar_cantidad_partidos(cantidad: int) -> list[str]:
    """Valida el total de partidos. Permite menos de 104 durante la migración."""
    if cantidad > TOTAL_PARTIDOS:
        raise ValueError(
            f"ERROR: {cantidad} partidos encontrados, máximo permitido: {TOTAL_PARTIDOS}."
        )

    if cantidad == TOTAL_PARTIDOS:
        return []

    return [
        f"Solo {cantidad} de {TOTAL_PARTIDOS} partidos cargados. "
        "Las fases eliminatorias se aplicarán automáticamente al completar partidos.json."
    ]


def validar_integridad_partidos(ids: list[int]) -> list[str]:
    """Comprueba que los IDs sean consecutivos cuando el torneo está completo."""
    if len(ids) != TOTAL_PARTIDOS:
        return []

    esperados = set(range(1, TOTAL_PARTIDOS + 1))
    actuales = set(ids)
    faltantes = sorted(esperados - actuales)

    if faltantes:
        raise ValueError(
            f"ERROR: faltan partidos con id: {', '.join(map(str, faltantes))}."
        )

    return []
