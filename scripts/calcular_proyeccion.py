"""Genera proyeccion.json: probabilidades de campeón y Top 3 vía Monte Carlo.

Reutiliza los loaders de `calcular_clasificacion` (no duplica I/O ni reglas) y
delega toda la simulación en el módulo `proyeccion.py`. Se ejecuta en el
workflow después de generar la evolución y antes de sincronizar el frontend.

Añade a la salida los metadatos visuales (inicial y color) reutilizando las
mismas funciones que la evolución, para que el frontend solo pinte.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))
sys.path.insert(0, str(PROYECTO_DIR / "scripts"))

from apuestas import partido_tiene_resultado  # noqa: E402
from calcular_clasificacion import (  # noqa: E402
    PARTIDOS_FILE,
    RESULTADOS_FILE,
    PARTICIPANTES_DIR,
    cargar_participante,
    cargar_partidos,
    cargar_resultados,
    listar_participantes,
)
from evolucion import COLORES_FIJOS, color_para, inicial  # noqa: E402
from probabilidades import cargar_proveedor  # noqa: E402
from proyeccion import RANDOM_SEED, SIMULACIONES, simular  # noqa: E402
from reparto_premios import es_participante_virtual  # noqa: E402

PROBABILIDADES_FILE = PROYECTO_DIR / "probabilidades.json"
PROYECCION_FILE = PROYECTO_DIR / "proyeccion.json"
MARCADORES_FILE = PROYECTO_DIR / "marcadores.json"
DOCS_DIR = PROYECTO_DIR / "docs"
DOCS_PROYECCION_FILE = DOCS_DIR / "proyeccion.json"
DOCS_PROYECCION_JS_FILE = DOCS_DIR / "proyeccion.js"

# Umbral mínimo (puntos porcentuales) para destacar un movimiento. Filtra el
# ruido de muestreo Monte Carlo (~0,3 pp con 20.000 simulaciones).
UMBRAL_MOVIMIENTO_PP = 0.5


def _calcular_indice_emocion(campeon: list[tuple[str, float]]) -> dict[str, Any]:
    """Interpreta lo abierto que sigue el campeonato a partir de las probabilidades.

    No modifica ninguna simulación: solo analiza la distribución de campeón.

    Métricas:
    - Entropía normalizada H_norm ∈ [0, 1]: 1 = todos iguales, 0 = un solo favorito.
    - Concentración (HHI normalizado): 0 = repartido, 1 = monopolio.
    - Probabilidad del líder P_max.

    Umbrales (de más abierto a más decidido):
    - Muy abierto:   H_norm ≥ 0.88 y P_max < 30 %
    - Abierto:       H_norm ≥ 0.72 o P_max < 38 %
    - Muy igualado:  P_max ≥ 38 % y P_max < 55 % (favorito claro pero no dominante)
    - Decidido:      P_max ≥ 55 % o concentración ≥ 0.55
    """
    probs = [p / 100.0 for _, p in campeon if p > 0]
    n = len(probs)
    if n == 0:
        return {
            "nivel": "abierto",
            "etiqueta": "Abierto",
            "emoji": "🟡",
            "entropia": 0.0,
            "concentracion": 0.0,
            "lider_pct": 0.0,
        }

    p_max = max(probs)
    h = -sum(p * math.log(p) for p in probs)
    h_norm = h / math.log(n) if n > 1 else 0.0

    hhi = sum(p * p for p in probs)
    hhi_min = 1.0 / n
    concentracion = (hhi - hhi_min) / (1.0 - hhi_min) if n > 1 else 1.0

    if p_max >= 0.55 or concentracion >= 0.55:
        nivel, etiqueta, emoji = "decidido", "Prácticamente decidido", "🔴"
    elif p_max >= 0.38:
        nivel, etiqueta, emoji = "igualado", "Muy igualado", "🟠"
    elif h_norm >= 0.88:
        nivel, etiqueta, emoji = "muy_abierto", "Muy abierto", "🟢"
    elif h_norm >= 0.72 or p_max < 0.30:
        nivel, etiqueta, emoji = "abierto", "Abierto", "🟡"
    else:
        nivel, etiqueta, emoji = "igualado", "Muy igualado", "🟠"

    return {
        "nivel": nivel,
        "etiqueta": etiqueta,
        "emoji": emoji,
        "entropia": round(h_norm, 3),
        "concentracion": round(concentracion, 3),
        "lider_pct": round(p_max * 100, 1),
    }


def guardar_json(contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def guardar_modulo_js(variable: str, contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        archivo.write(f"window.{variable} = ")
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write(";\n")


def _meta_visual(nombres: list[str]) -> dict[str, dict[str, str]]:
    """Inicial y color por participante (mismos criterios que la evolución)."""
    meta: dict[str, dict[str, str]] = {}
    indice_reserva = 0
    for nombre in nombres:
        meta[nombre] = {"inicial": inicial(nombre), "color": color_para(nombre, indice_reserva)}
        if nombre.strip().upper() not in COLORES_FIJOS:
            indice_reserva += 1
    return meta


def _cargar_proyeccion_previa() -> dict[str, Any] | None:
    """Lee la proyección anterior (si existe) para calcular la evolución."""
    if not PROYECCION_FILE.exists():
        return None
    try:
        datos = json.loads(PROYECCION_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return datos if isinstance(datos, dict) else None


def _mapa_probabilidades(seccion: list[dict[str, Any]] | None) -> dict[str, float]:
    """Convierte una lista de la proyección previa en {nombre: probabilidad}."""
    if not isinstance(seccion, list):
        return {}
    return {
        str(fila.get("nombre")): float(fila.get("probabilidad", 0.0))
        for fila in seccion
        if isinstance(fila, dict) and fila.get("nombre")
    }


def _con_delta(
    filas: list[tuple[str, float]],
    previas: dict[str, float],
    hay_previa: bool,
) -> list[dict[str, float]]:
    """Añade el delta (pp) de cada probabilidad respecto a la proyección previa."""
    salida: list[dict[str, Any]] = []
    for nombre, prob in filas:
        entrada: dict[str, Any] = {"nombre": nombre, "probabilidad": prob}
        if hay_previa:
            entrada["delta"] = round(prob - previas.get(nombre, 0.0), 2)
        else:
            entrada["delta"] = 0.0
        salida.append(entrada)
    return salida


def _contar_jugados(partidos: list[Any], resultados: list[Any]) -> int:
    """Número de partidos con resultado oficial."""
    return sum(
        1
        for partido, resultado in zip(partidos, resultados)
        if partido_tiene_resultado(resultado, partido.fase)
    )


def _instante(partido: Any) -> tuple[str, str]:
    """Clave ordenable (fecha, hora) de un partido."""
    return (partido.fecha or "0000-00-00", partido.hora or "00:00")


def _ultimo_partido_jugado(
    partidos: list[Any],
    resultados: list[Any],
    marcadores: list[Any],
) -> dict[str, Any] | None:
    """Partido jugado más reciente por calendario (gancho narrativo del cambio)."""
    jugados = [
        idx
        for idx, (partido, resultado) in enumerate(zip(partidos, resultados))
        if partido_tiene_resultado(resultado, partido.fase)
    ]
    if not jugados:
        return None

    idx = max(jugados, key=lambda i: _instante(partidos[i]))
    partido = partidos[idx]
    marcador = marcadores[idx] if idx < len(marcadores) else None
    marcador_str = None
    if isinstance(marcador, dict) and marcador.get("home") is not None:
        marcador_str = f"{marcador['home']}-{marcador['away']}"

    return {
        "id": partido.id,
        "local": partido.local,
        "visitante": partido.visitante,
        "fase": partido.fase,
        "marcador": marcador_str,
    }


def _movimiento(
    campeon: list[dict[str, Any]],
    previa: dict[str, Any] | None,
    partidos_jugados: int,
    ultimo_partido: dict[str, Any] | None,
    meta: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Mayor beneficiado y perjudicado desde la proyección anterior.

    Solo se considera un cambio real cuando se ha jugado algún partido nuevo
    (la semilla fija garantiza que sin nuevos resultados el delta sería nulo).
    """
    jugados_previos = previa.get("partidos_jugados") if isinstance(previa, dict) else None
    hay_cambio = (
        isinstance(jugados_previos, int) and partidos_jugados > jugados_previos
    )

    base = {
        "hay_cambio": False,
        "desde": previa.get("generatedAt") if isinstance(previa, dict) else None,
        "ultimo_partido": ultimo_partido,
        "beneficiado": None,
        "perjudicado": None,
    }
    if not hay_cambio:
        return base

    con_delta = [f for f in campeon if abs(f.get("delta", 0.0)) >= UMBRAL_MOVIMIENTO_PP]
    if not con_delta:
        return base

    def tarjeta(fila: dict[str, Any]) -> dict[str, Any]:
        nombre = fila["nombre"]
        return {
            "nombre": nombre,
            "inicial": meta[nombre]["inicial"],
            "color": meta[nombre]["color"],
            "probabilidad": fila["probabilidad"],
            "delta": fila["delta"],
        }

    mejor = max(con_delta, key=lambda f: f["delta"])
    peor = min(con_delta, key=lambda f: f["delta"])

    base["hay_cambio"] = True
    if mejor["delta"] > 0:
        base["beneficiado"] = tarjeta(mejor)
    if peor["delta"] < 0:
        base["perjudicado"] = tarjeta(peor)
    return base


def construir_salida(
    resultado: Any,
    nombres: list[str],
    generado: str,
    *,
    partidos_jugados: int,
    ultimo_partido: dict[str, Any] | None,
    previa: dict[str, Any] | None,
) -> dict[str, Any]:
    """Estructura serializable, diseñada para ampliarse sin romper compatibilidad."""
    meta = _meta_visual(nombres)
    hay_previa = isinstance(previa, dict) and bool(previa.get("campeon"))
    prev_campeon = _mapa_probabilidades(previa.get("campeon") if previa else None)
    prev_top3 = _mapa_probabilidades(previa.get("top3") if previa else None)

    campeon = [
        {
            **fila,
            "inicial": meta[fila["nombre"]]["inicial"],
            "color": meta[fila["nombre"]]["color"],
            "es_ia": es_participante_virtual(fila["nombre"]),
        }
        for fila in _con_delta(resultado.campeon, prev_campeon, hay_previa)
    ]
    top3 = [
        {
            **fila,
            "inicial": meta[fila["nombre"]]["inicial"],
            "color": meta[fila["nombre"]]["color"],
        }
        for fila in _con_delta(resultado.top3, prev_top3, hay_previa)
    ]

    movimiento = _movimiento(
        campeon, previa, partidos_jugados, ultimo_partido, meta
    )
    indice_emocion = _calcular_indice_emocion(resultado.campeon)

    return {
        "generatedAt": generado,
        "simulaciones": resultado.simulaciones,
        "seed": resultado.seed,
        "partidos_pendientes": resultado.partidos_pendientes,
        "puntos_max_restantes": resultado.puntos_max_restantes,
        "partidos_jugados": partidos_jugados,
        "movimiento": movimiento,
        "indice_emocion": indice_emocion,
        "campeon": campeon,
        "top3": top3,
        "distribucion": resultado.distribucion,
        "stats": resultado.stats,
        "frecuencia_empate_liderato": resultado.frecuencia_empate_liderato,
    }


def _cargar_marcadores(total: int) -> list[Any]:
    if not MARCADORES_FILE.exists():
        return [None] * total
    try:
        datos = json.loads(MARCADORES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [None] * total
    return datos if isinstance(datos, list) else [None] * total


def main() -> int:
    try:
        partidos, _ = cargar_partidos(PARTIDOS_FILE)
        resultados = cargar_resultados(RESULTADOS_FILE)

        participantes = []
        for ruta in listar_participantes(PARTICIPANTES_DIR):
            try:
                participantes.append(cargar_participante(ruta))
            except ValueError as exc:
                print(f"⚠ Participante {ruta.stem} ignorado: {exc}", file=sys.stderr)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not participantes:
        print("No hay participantes válidos para proyectar.", file=sys.stderr)
        return 1

    # La proyección previa se lee ANTES de sobrescribir el fichero.
    previa = _cargar_proyeccion_previa()
    marcadores = _cargar_marcadores(len(partidos))

    proveedor = cargar_proveedor(PROBABILIDADES_FILE)
    resultado = simular(
        participantes,
        partidos,
        resultados,
        proveedor,
        simulaciones=SIMULACIONES,
        seed=RANDOM_SEED,
    )

    generado = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    nombres = [p.nombre for p in participantes]
    partidos_jugados = _contar_jugados(partidos, resultados)
    ultimo_partido = _ultimo_partido_jugado(partidos, resultados, marcadores)
    salida = construir_salida(
        resultado,
        nombres,
        generado,
        partidos_jugados=partidos_jugados,
        ultimo_partido=ultimo_partido,
        previa=previa,
    )

    guardar_json(salida, PROYECCION_FILE)
    if DOCS_DIR.exists():
        guardar_json(salida, DOCS_PROYECCION_FILE)
        guardar_modulo_js("__PROYECCION__", salida, DOCS_PROYECCION_JS_FILE)

    lider = salida["campeon"][0] if salida["campeon"] else None
    print(
        f"✓ proyeccion.json → {resultado.simulaciones} simulaciones, "
        f"{resultado.partidos_pendientes} partidos pendientes"
    )
    if lider:
        print(f"  🏆 Favorito: {lider['nombre']} ({lider['probabilidad']:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
