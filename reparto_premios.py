"""Cálculo del reparto económico con soporte de empates por puntos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

PARTICIPANTES_VIRTUALES = frozenset({"GPT", "GEMINI"})
PREMIOS_FIJOS = {1: 40, 2: 30, 3: 20, 4: 8}
PREMIO_VARIABLE_TOTAL = 42


class FilaClasificacionLike(Protocol):
    """Contrato mínimo para calcular el reparto económico."""

    nombre: str
    puntos: int


@dataclass(frozen=True)
class FilaPremio:
    posicion: int
    nombre: str
    puntos: int
    premio_fijo: float
    premio_variable: float
    premio_total: float


def es_participante_virtual(nombre: str) -> bool:
    """Indica si un participante queda fuera del reparto económico."""
    return nombre.strip().upper() in PARTICIPANTES_VIRTUALES


def filtrar_humanos(filas: list[FilaClasificacionLike]) -> list[FilaClasificacionLike]:
    """Conserva solo participantes reales, manteniendo el orden de clasificación."""
    return [fila for fila in filas if not es_participante_virtual(fila.nombre)]


def agrupar_empates(
    humanos: list[FilaClasificacionLike],
) -> list[tuple[int, list[FilaClasificacionLike]]]:
    """Agrupa participantes humanos consecutivos empatados por puntos."""
    grupos: list[tuple[int, list[FilaClasificacionLike]]] = []
    indice = 0
    posicion = 1

    while indice < len(humanos):
        grupo = [humanos[indice]]
        siguiente = indice + 1
        while (
            siguiente < len(humanos)
            and humanos[siguiente].puntos == humanos[indice].puntos
        ):
            grupo.append(humanos[siguiente])
            siguiente += 1

        grupos.append((posicion, grupo))
        posicion += len(grupo)
        indice = siguiente

    return grupos


def calcular_premio_fijo_grupo(posicion_inicio: int, tamano_grupo: int) -> float:
    """Suma los premios fijos de las posiciones ocupadas y reparte a partes iguales."""
    total = sum(
        PREMIOS_FIJOS.get(posicion, 0)
        for posicion in range(posicion_inicio, posicion_inicio + tamano_grupo)
    )
    return round(total / tamano_grupo, 2)


def calcular_premios_variables(
    humanos: list[FilaClasificacionLike],
) -> dict[str, float]:
    """Reparte los 42 € proporcionalmente entre humanos excepto el último."""
    elegibles = humanos[:-1] if len(humanos) > 1 else []
    suma_puntos = sum(humano.puntos for humano in elegibles)
    premios: dict[str, float] = {}

    for humano in humanos:
        if humano not in elegibles:
            premios[humano.nombre] = 0.0
            continue

        if suma_puntos == 0:
            premio = PREMIO_VARIABLE_TOTAL / len(elegibles)
        else:
            premio = (humano.puntos / suma_puntos) * PREMIO_VARIABLE_TOTAL

        premios[humano.nombre] = round(premio, 2)

    return premios


def calcular_reparto_economico(
    filas: list[FilaClasificacionLike],
) -> list[FilaPremio]:
    """Calcula el reparto económico a partir de la clasificación ya ordenada."""
    humanos = filtrar_humanos(filas)
    if not humanos:
        return []

    premios_variables = calcular_premios_variables(humanos)
    reparto: list[FilaPremio] = []

    for posicion_inicio, grupo in agrupar_empates(humanos):
        premio_fijo = calcular_premio_fijo_grupo(posicion_inicio, len(grupo))
        for humano in grupo:
            premio_variable = premios_variables[humano.nombre]
            reparto.append(
                FilaPremio(
                    posicion=posicion_inicio,
                    nombre=humano.nombre,
                    puntos=humano.puntos,
                    premio_fijo=premio_fijo,
                    premio_variable=premio_variable,
                    premio_total=round(premio_fijo + premio_variable, 2),
                )
            )

    return reparto


def premios_a_dict(filas: list[FilaPremio]) -> list[dict[str, Any]]:
    """Convierte filas de premios a diccionarios serializables."""
    return [
        {
            "posicion": fila.posicion,
            "nombre": fila.nombre,
            "puntos": fila.puntos,
            "premio_fijo": fila.premio_fijo,
            "premio_variable": fila.premio_variable,
            "premio_total": fila.premio_total,
        }
        for fila in filas
    ]


@dataclass(frozen=True)
class _FilaPrueba:
    posicion: int
    nombre: str
    aciertos: int
    puntos: int


def _formatear_reparto(premios: list[FilaPremio]) -> str:
    lineas = []
    for fila in premios:
        lineas.append(
            f"  {fila.posicion}º {fila.nombre}: "
            f"fijo={fila.premio_fijo:.2f} €, "
            f"variable={fila.premio_variable:.2f} €, "
            f"total={fila.premio_total:.2f} €"
        )
    return "\n".join(lineas)


def _validar_escenario(
    nombre: str,
    filas: list[_FilaPrueba],
    esperados_fijos: dict[str, float],
) -> None:
    premios = calcular_reparto_economico(filas)
    print(f"\n=== {nombre} ===")
    print(_formatear_reparto(premios))

    for jugador, premio_fijo_esperado in esperados_fijos.items():
        fila = next(item for item in premios if item.nombre == jugador)
        if fila.premio_fijo != premio_fijo_esperado:
            raise AssertionError(
                f"{nombre}: {jugador} premio_fijo={fila.premio_fijo}, "
                f"esperado={premio_fijo_esperado}"
            )


def validar_escenarios() -> None:
    """Ejecuta escenarios de validación del reparto con empates."""
    _validar_escenario(
        "Empate por el primer puesto",
        [
            _FilaPrueba(1, "AGUSTIN", 0, 120),
            _FilaPrueba(2, "SERGIO", 0, 120),
            _FilaPrueba(3, "GABRIEL", 0, 118),
            _FilaPrueba(4, "MARIO", 0, 115),
        ],
        {
            "AGUSTIN": 35.0,
            "SERGIO": 35.0,
            "GABRIEL": 20.0,
            "MARIO": 8.0,
        },
    )

    _validar_escenario(
        "Empate por el segundo puesto (triple)",
        [
            _FilaPrueba(1, "AGUSTIN", 0, 100),
            _FilaPrueba(2, "SERGIO", 0, 90),
            _FilaPrueba(3, "GABRIEL", 0, 90),
            _FilaPrueba(4, "JORGE", 0, 90),
            _FilaPrueba(5, "MARIO", 0, 80),
        ],
        {
            "AGUSTIN": 40.0,
            "SERGIO": 19.33,
            "GABRIEL": 19.33,
            "JORGE": 19.33,
            "MARIO": 0.0,
        },
    )

    _validar_escenario(
        "Empate por el tercer puesto",
        [
            _FilaPrueba(1, "AGUSTIN", 0, 100),
            _FilaPrueba(2, "SERGIO", 0, 90),
            _FilaPrueba(3, "GABRIEL", 0, 85),
            _FilaPrueba(4, "JORGE", 0, 85),
        ],
        {
            "AGUSTIN": 40.0,
            "SERGIO": 30.0,
            "GABRIEL": 14.0,
            "JORGE": 14.0,
        },
    )

    _validar_escenario(
        "Empate de todos los jugadores",
        [
            _FilaPrueba(1, "AGUSTIN", 0, 50),
            _FilaPrueba(2, "SERGIO", 0, 50),
            _FilaPrueba(3, "GABRIEL", 0, 50),
            _FilaPrueba(4, "JORGE", 0, 50),
        ],
        {
            "AGUSTIN": 24.5,
            "SERGIO": 24.5,
            "GABRIEL": 24.5,
            "JORGE": 24.5,
        },
    )

    _validar_escenario(
        "Sin empates",
        [
            _FilaPrueba(1, "AGUSTIN", 0, 100),
            _FilaPrueba(2, "SERGIO", 0, 90),
            _FilaPrueba(3, "GABRIEL", 0, 80),
            _FilaPrueba(4, "JORGE", 0, 70),
        ],
        {
            "AGUSTIN": 40.0,
            "SERGIO": 30.0,
            "GABRIEL": 20.0,
            "JORGE": 8.0,
        },
    )

    premios_con_virtuales = calcular_reparto_economico(
        [
            _FilaPrueba(1, "GPT", 24, 200),
            _FilaPrueba(2, "GEMINI", 21, 200),
            _FilaPrueba(3, "AGUSTIN", 0, 120),
            _FilaPrueba(4, "SERGIO", 0, 120),
            _FilaPrueba(5, "GABRIEL", 0, 118),
        ]
    )
    print("\n=== GPT y GEMINI excluidos del reparto ===")
    print(_formatear_reparto(premios_con_virtuales))
    nombres = {fila.nombre for fila in premios_con_virtuales}
    if nombres & PARTICIPANTES_VIRTUALES:
        raise AssertionError("GPT/GEMINI no deben aparecer en el reparto económico")
    if premios_con_virtuales[0].premio_fijo != 35.0:
        raise AssertionError("Empate humano 1º debe repartir 35 €")

    print("\n✓ Todos los escenarios de validación pasaron correctamente.")


if __name__ == "__main__":
    validar_escenarios()
