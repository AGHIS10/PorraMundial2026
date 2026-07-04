"""Genera partidos.json completo (104 partidos) desde football-data.org.

Conserva los 72 partidos de grupos existentes y añade las eliminatorias
con fechas/horas reales (CEST) y placeholders FIFA para los equipos.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

PROYECTO_DIR = Path(__file__).resolve().parent.parent
PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
RESULTADOS_FILE = PROYECTO_DIR / "resultados.json"
MARCADORES_FILE = PROYECTO_DIR / "marcadores.json"
PARTICIPANTES_DIR = PROYECTO_DIR / "participantes"
API_URL = "https://api.football-data.org/v4/competitions/WC/matches"
API_SEASON = 2026
API_KEY_ENV = "FOOTBALL_DATA_API_KEY"
ZONA_CEST = ZoneInfo("Europe/Madrid")

STAGE_POR_FASE: dict[str, str] = {
    "dieciseisavos": "LAST_32",
    "octavos": "LAST_16",
    "cuartos": "QUARTER_FINALS",
    "semifinales": "SEMI_FINALS",
    "tercer_puesto": "THIRD_PLACE",
    "final": "FINAL",
}

# Placeholders FIFA en orden cronológico dentro de cada fase (calendario oficial).
PLACEHOLDERS_ELIMINATORIAS: dict[str, list[tuple[str, str]]] = {
    "dieciseisavos": [
        ("2A", "2B"),
        ("1C", "2F"),
        ("1E", "3ABCDF"),
        ("1F", "2C"),
        ("2E", "2I"),
        ("1I", "3CDFGH"),
        ("1A", "3CEFHI"),
        ("1L", "3EHIJK"),
        ("1G", "3AEHIJ"),
        ("1D", "3BEFIJ"),
        ("1H", "2J"),
        ("2K", "2L"),
        ("1B", "3EFGIJ"),
        ("2D", "2G"),
        ("1J", "2H"),
        ("1K", "3DEIJL"),
    ],
    "octavos": [
        ("W75", "W77"),
        ("W73", "W76"),
        ("W74", "W78"),
        ("W79", "W80"),
        ("W83", "W84"),
        ("W81", "W82"),
        ("W86", "W88"),
        ("W85", "W87"),
    ],
    "cuartos": [
        ("W89", "W90"),
        ("W93", "W94"),
        ("W91", "W92"),
        ("W95", "W96"),
    ],
    "semifinales": [
        ("W97", "W98"),
        ("W99", "W100"),
    ],
    "tercer_puesto": [
        ("Perdedor 101", "Perdedor 102"),
    ],
    "final": [
        ("W101", "W102"),
    ],
}

RANGOS_FASE: dict[str, tuple[int, int, int]] = {
    "dieciseisavos": ("dieciseisavos", 2, 73),
    "octavos": ("octavos", 4, 89),
    "cuartos": ("cuartos", 8, 97),
    "semifinales": ("semifinales", 16, 101),
    "tercer_puesto": ("tercer_puesto", 25, 103),
    "final": ("final", 50, 104),
}


def cargar_json(ruta: Path) -> Any:
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def guardar_json(contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def consultar_api(api_key: str) -> list[dict[str, Any]]:
    respuesta = requests.get(
        API_URL,
        headers={"X-Auth-Token": api_key},
        params={"season": API_SEASON},
        timeout=30,
    )
    respuesta.raise_for_status()
    datos = respuesta.json()
    partidos = datos.get("matches", datos) if isinstance(datos, dict) else datos
    if not isinstance(partidos, list):
        raise ValueError("La API no devolvió una lista de partidos.")
    return partidos


def utc_a_fecha_hora_cest(utc_date: str) -> tuple[str, str]:
    instante = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    local = instante.astimezone(ZONA_CEST)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


def partidos_por_stage(partidos_api: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    filtrados = [partido for partido in partidos_api if partido.get("stage") == stage]
    return sorted(filtrados, key=lambda partido: partido.get("utcDate", ""))


def construir_eliminatorias(partidos_api: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nuevos: list[dict[str, Any]] = []

    for clave_fase, (nombre_fase, peso, id_inicio) in RANGOS_FASE.items():
        stage = STAGE_POR_FASE[clave_fase]
        placeholders = PLACEHOLDERS_ELIMINATORIAS[clave_fase]
        partidos_stage = partidos_por_stage(partidos_api, stage)

        if len(partidos_stage) != len(placeholders):
            raise ValueError(
                f"Fase {nombre_fase}: la API tiene {len(partidos_stage)} partidos "
                f"pero se esperaban {len(placeholders)} placeholders."
            )

        for indice, (partido_api, (local, visitante)) in enumerate(
            zip(partidos_stage, placeholders)
        ):
            partido_id = id_inicio + indice
            fecha, hora = utc_a_fecha_hora_cest(partido_api["utcDate"])
            nuevos.append(
                {
                    "id": partido_id,
                    "fecha": fecha,
                    "hora": hora,
                    "local": local,
                    "visitante": visitante,
                    "fase": nombre_fase,
                    "peso": peso,
                }
            )

    return nuevos


def validar_grupos_existentes(
    grupos_locales: list[dict[str, Any]],
    partidos_api: list[dict[str, Any]],
) -> list[str]:
    """Comprueba que los 72 grupos locales sigan alineados con la API."""
    advertencias: list[str] = []
    grupos_api = partidos_por_stage(partidos_api, "GROUP_STAGE")

    if len(grupos_locales) != 72:
        raise ValueError(
            f"Se esperaban 72 partidos de grupos locales, hay {len(grupos_locales)}."
        )
    if len(grupos_api) != 72:
        raise ValueError(
            f"Se esperaban 72 partidos GROUP_STAGE en la API, hay {len(grupos_api)}."
        )

    for partido_local in grupos_locales:
        candidatos = [
            partido_api
            for partido_api in grupos_api
            if utc_a_fecha_hora_cest(partido_api["utcDate"])
            == (partido_local["fecha"], partido_local["hora"])
        ]
        if not candidatos:
            advertencias.append(
                f"Partido id {partido_local['id']} ({partido_local['local']} vs "
                f"{partido_local['visitante']}): fecha/hora {partido_local['fecha']} "
                f"{partido_local['hora']} no encontrada en la API."
            )

    return advertencias


def extender_lista_nula(actual: list[Any] | None, total: int) -> list[Any | None]:
    lista = list(actual or [])
    if len(lista) > total:
        raise ValueError(f"La lista tiene {len(lista)} entradas, máximo {total}.")
    return lista + [None] * (total - len(lista))


def extender_participantes(total_partidos: int) -> int:
    actualizados = 0
    for ruta in sorted(PARTICIPANTES_DIR.glob("*.json")):
        datos = cargar_json(ruta)
        pronosticos = datos.get("pronosticos")
        if not isinstance(pronosticos, list):
            raise ValueError(f"{ruta.name}: falta el campo 'pronosticos'.")
        if len(pronosticos) == total_partidos:
            continue
        if len(pronosticos) > total_partidos:
            raise ValueError(
                f"{ruta.name}: {len(pronosticos)} pronósticos, máximo {total_partidos}."
            )
        datos["pronosticos"] = extender_lista_nula(pronosticos, total_partidos)
        guardar_json(datos, ruta)
        actualizados += 1
    return actualizados


def main() -> int:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        print(
            f"Error: falta la variable de entorno {API_KEY_ENV}.",
            file=sys.stderr,
        )
        return 1

    try:
        partidos_actuales = cargar_json(PARTIDOS_FILE)
        if not isinstance(partidos_actuales, list) or not partidos_actuales:
            raise ValueError("partidos.json debe ser un array no vacío.")

        grupos_locales = [partido for partido in partidos_actuales if partido.get("fase") == "grupos"]
        if len(grupos_locales) != len(partidos_actuales):
            print(
                "Aviso: partidos.json ya contiene eliminatorias; "
                "se regenerarán desde la API.",
            )
            grupos_locales = [partido for partido in partidos_actuales if partido.get("fase") == "grupos"]
            if len(grupos_locales) != 72:
                raise ValueError(
                    f"No se encontraron 72 partidos de grupos (hay {len(grupos_locales)})."
                )

        partidos_api = consultar_api(api_key)
        if len(partidos_api) != 104:
            raise ValueError(f"Se esperaban 104 partidos en la API, hay {len(partidos_api)}.")

        for aviso in validar_grupos_existentes(grupos_locales, partidos_api):
            print(f"[WARN] {aviso}")

        eliminatorias = construir_eliminatorias(partidos_api)
        partidos_completos = grupos_locales + eliminatorias

        if len(partidos_completos) != 104:
            raise ValueError(f"Total inesperado: {len(partidos_completos)} partidos.")

        guardar_json(partidos_completos, PARTIDOS_FILE)
        print(f"✓ partidos.json → {len(partidos_completos)} partidos")

        resultados = extender_lista_nula(
            cargar_json(RESULTADOS_FILE) if RESULTADOS_FILE.exists() else None,
            104,
        )
        marcadores = extender_lista_nula(
            cargar_json(MARCADORES_FILE) if MARCADORES_FILE.exists() else None,
            104,
        )
        guardar_json(resultados, RESULTADOS_FILE)
        guardar_json(marcadores, MARCADORES_FILE)
        print(f"✓ resultados.json → {len(resultados)} entradas")
        print(f"✓ marcadores.json → {len(marcadores)} entradas")

        participantes_actualizados = extender_participantes(104)
        print(f"✓ {participantes_actualizados} participantes ampliados a 104 pronósticos")

        return 0
    except requests.RequestException as exc:
        print(f"Error de API: {exc}", file=sys.stderr)
        return 1
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
