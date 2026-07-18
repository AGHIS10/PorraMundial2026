"""Actualiza partidos.json con tercer puesto y final reales.

Resuelve perdedores/ganadores de semifinales (ids 101–102) desde resultados.json
y sincroniza fecha/hora en CEST (España) con football-data.org.
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
sys.path.insert(0, str(PROYECTO_DIR))

from scripts.actualizar_resultados import (  # noqa: E402
    API_KEY_ENV,
    API_SEASON,
    API_URL,
    ALIAS_FILE,
    RESULTADOS_FILE,
    cargar_json,
    equipos_coinciden,
    guardar_json,
    nombre_equipo_api,
)

PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
INDICE_TERCER_PUESTO = 102  # partido id 103
INDICE_FINAL = 103  # partido id 104
STAGE_TERCER_PUESTO = "THIRD_PLACE"
STAGE_FINAL = "FINAL"
ZONA_CEST = ZoneInfo("Europe/Madrid")

IDS_SEMIFINALES = (101, 102)


def utc_a_fecha_hora_cest(utc_date: str) -> tuple[str, str]:
    instante = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    local = instante.astimezone(ZONA_CEST)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


def _equipo_clasificado(partido: dict[str, Any], resultado: Any) -> str:
    if not isinstance(resultado, dict) or not resultado.get("clasifica"):
        raise ValueError(
            f"Sin clasifica en semifinal id {partido.get('id')} "
            f"({partido.get('local')} vs {partido.get('visitante')})."
        )
    clasifica = str(resultado["clasifica"]).strip()
    if clasifica == "1":
        return partido["local"]
    if clasifica == "2":
        return partido["visitante"]
    raise ValueError(f"Clasifica inválido en id {partido.get('id')}: {clasifica!r}")


def _equipo_eliminado(partido: dict[str, Any], resultado: Any) -> str:
    if not isinstance(resultado, dict) or not resultado.get("clasifica"):
        raise ValueError(
            f"Sin clasifica en semifinal id {partido.get('id')} "
            f"({partido.get('local')} vs {partido.get('visitante')})."
        )
    clasifica = str(resultado["clasifica"]).strip()
    if clasifica == "1":
        return partido["visitante"]
    if clasifica == "2":
        return partido["local"]
    raise ValueError(f"Clasifica inválido en id {partido.get('id')}: {clasifica!r}")


def resolver_desde_semifinales(
    partidos: list[dict[str, Any]],
    resultados: list[Any],
) -> tuple[dict[str, str], dict[str, str]]:
    """Devuelve (tercer_puesto, final) con local/visitante."""
    ganadores: dict[int, str] = {}
    perdedores: dict[int, str] = {}

    for indice, partido in enumerate(partidos):
        match_id = partido.get("id")
        if match_id not in IDS_SEMIFINALES:
            continue
        resultado = resultados[indice] if indice < len(resultados) else None
        ganadores[match_id] = _equipo_clasificado(partido, resultado)
        perdedores[match_id] = _equipo_eliminado(partido, resultado)

    for match_id in IDS_SEMIFINALES:
        if match_id not in ganadores:
            raise ValueError(f"Falta resultado de semifinal id {match_id}.")

    return (
        {
            "local": perdedores[101],
            "visitante": perdedores[102],
        },
        {
            "local": ganadores[101],
            "visitante": ganadores[102],
        },
    )


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


def _emparejar_api(
    partido: dict[str, Any],
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
) -> dict[str, Any] | None:
    candidatos = [
        partido_api
        for partido_api in partidos_api
        if equipos_coinciden(partido, partido_api, alias)
    ]
    if len(candidatos) == 1:
        return candidatos[0]
    if len(candidatos) > 1:
        raise ValueError(
            f"Emparejamiento ambiguo para {partido.get('local')} vs "
            f"{partido.get('visitante')}: {len(candidatos)} coincidencias."
        )

    invertido = {"local": partido["visitante"], "visitante": partido["local"]}
    candidatos_inv = [
        partido_api
        for partido_api in partidos_api
        if equipos_coinciden(invertido, partido_api, alias)
    ]
    if len(candidatos_inv) == 1:
        return candidatos_inv[0]
    return None


def sincronizar_horario(
    partido: dict[str, Any],
    stage: str,
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
) -> None:
    pool = [m for m in partidos_api if m.get("stage") == stage]
    emparejado = _emparejar_api(partido, pool, alias)
    if emparejado is None:
        raise ValueError(
            f"No hay partido API ({stage}) para "
            f"{partido['local']} vs {partido['visitante']}."
        )
    utc_date = emparejado.get("utcDate")
    if not utc_date:
        home = nombre_equipo_api(emparejado, "home")
        away = nombre_equipo_api(emparejado, "away")
        raise ValueError(f"La API no devolvió utcDate para {home} vs {away}.")
    partido["fecha"], partido["hora"] = utc_a_fecha_hora_cest(utc_date)


def actualizar_partidos(
    tercer_puesto: dict[str, str],
    final: dict[str, str],
    partidos_api: list[dict[str, Any]] | None,
    alias: dict[str, str | list[str]],
) -> list[dict[str, Any]]:
    partidos = cargar_json(PARTIDOS_FILE)
    if not isinstance(partidos, list) or len(partidos) <= INDICE_FINAL:
        raise ValueError("partidos.json incompleto.")

    p3 = partidos[INDICE_TERCER_PUESTO]
    pf = partidos[INDICE_FINAL]
    if p3.get("fase") != "tercer_puesto" or pf.get("fase") != "final":
        raise ValueError("Índices de tercer puesto/final no coinciden con partidos.json.")

    p3["local"] = tercer_puesto["local"]
    p3["visitante"] = tercer_puesto["visitante"]
    pf["local"] = final["local"]
    pf["visitante"] = final["visitante"]

    if partidos_api is not None:
        sincronizar_horario(p3, STAGE_TERCER_PUESTO, partidos_api, alias)
        sincronizar_horario(pf, STAGE_FINAL, partidos_api, alias)
    else:
        print(
            "Aviso: sin FOOTBALL_DATA_API_KEY no se sincronizan fecha/hora desde la API.",
            file=sys.stderr,
        )

    guardar_json(partidos, PARTIDOS_FILE)
    return [p3, pf]


def main() -> int:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    try:
        alias = cargar_json(ALIAS_FILE)
        partidos = cargar_json(PARTIDOS_FILE)
        resultados = cargar_json(RESULTADOS_FILE)
        tercer_puesto, final = resolver_desde_semifinales(partidos, resultados)
        partidos_api = consultar_api(api_key) if api_key else None
        actualizados = actualizar_partidos(tercer_puesto, final, partidos_api, alias)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("✓ Partidos finales cargados desde semifinales\n")
    for partido in actualizados:
        print(
            f"  id {partido['id']:>2} · {partido['fecha']} {partido['hora']} · "
            f"{partido['local']} vs {partido['visitante']} ({partido['fase']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
