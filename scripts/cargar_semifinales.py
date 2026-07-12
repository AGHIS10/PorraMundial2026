"""Actualiza partidos.json con las semifinales reales.

Carga equipos desde CSV en input/ (sufijo - 2) o, si no hay CSV, resuelve
W97–W100 desde resultados.json. Sincroniza fecha/hora en CEST (España) con
football-data.org emparejando por local/visitante.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
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
INPUT_DIR = PROYECTO_DIR.parent / "mundial-json-converter" / "input"
CLASIFICA_HEADER = "CLASIFICA"
INICIO_INDICE = 100  # partido id 101
FIN_INDICE = 102  # exclusivo, partido id 102
STAGE_SEMIFINALES = "SEMI_FINALS"
ZONA_CEST = ZoneInfo("Europe/Madrid")

TEAM_NAME_PATTERN = re.compile(r"[A-Za-zÀ-ÿ]")
NOMBRES_CANONICOS = {
    "Bosnia": "Bosnia y Herzegovina",
}

CRUCE_SEMIFINALES: list[tuple[str, str]] = [
    ("W97", "W98"),  # id 101
    ("W99", "W100"),  # id 102
]


def normalizar_equipo(value: Any) -> str:
    if pd.isna(value):
        raise ValueError("Nombre de equipo vacío en el CSV.")
    texto = str(value).strip()
    coincidencia = TEAM_NAME_PATTERN.search(texto)
    if coincidencia:
        texto = texto[coincidencia.start() :].strip()
    return NOMBRES_CANONICOS.get(texto, texto)


def utc_a_fecha_hora_cest(utc_date: str) -> tuple[str, str]:
    instante = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    local = instante.astimezone(ZONA_CEST)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


def ganadores_cuartos(
    partidos: list[dict[str, Any]],
    resultados: list[Any],
) -> dict[str, str]:
    """Mapa W{id} → nombre del equipo clasificado en cuartos."""
    ganadores: dict[str, str] = {}
    pendientes: list[str] = []

    for indice, partido in enumerate(partidos):
        if partido.get("fase") != "cuartos":
            continue
        match_id = partido.get("id")
        resultado = resultados[indice] if indice < len(resultados) else None
        etiqueta = f"W{match_id} · {partido.get('local')} vs {partido.get('visitante')}"

        if not isinstance(resultado, dict) or not resultado.get("clasifica"):
            pendientes.append(etiqueta)
            continue

        clasifica = str(resultado["clasifica"]).strip()
        if clasifica == "1":
            ganadores[f"W{match_id}"] = partido["local"]
        elif clasifica == "2":
            ganadores[f"W{match_id}"] = partido["visitante"]
        else:
            pendientes.append(etiqueta)

    if pendientes:
        raise ValueError(
            "Faltan resultados de cuartos para resolver semifinales:\n  "
            + "\n  ".join(pendientes)
        )
    return ganadores


def resolver_semifinales_desde_ganadores(
    ganadores: dict[str, str],
) -> list[dict[str, str]]:
    """Genera local/visitante para las 2 semifinales a partir del cuadro FIFA."""
    partidos: list[dict[str, str]] = []
    for local_ph, visitante_ph in CRUCE_SEMIFINALES:
        if local_ph not in ganadores:
            raise ValueError(f"No hay ganador para {local_ph}.")
        if visitante_ph not in ganadores:
            raise ValueError(f"No hay ganador para {visitante_ph}.")
        partidos.append(
            {
                "local": ganadores[local_ph],
                "visitante": ganadores[visitante_ph],
            }
        )
    return partidos


def leer_partidos_csv(csv_path: Path) -> list[dict[str, str]]:
    df = pd.read_csv(csv_path, encoding="utf-8", header=None)
    if df.shape[1] < 4:
        raise ValueError(f"{csv_path.name} no tiene columnas suficientes.")

    partidos: list[dict[str, str]] = []
    for _, fila in df.iloc[1:].iterrows():
        if pd.isna(fila[0]) and pd.isna(fila[1]):
            continue
        partidos.append(
            {
                "local": normalizar_equipo(fila[1]),
                "visitante": normalizar_equipo(fila[3]),
            }
        )

    esperados = FIN_INDICE - INICIO_INDICE
    if len(partidos) != esperados:
        raise ValueError(
            f"Se esperaban {esperados} partidos en {csv_path.name}, hay {len(partidos)}."
        )
    return partidos


def buscar_csv_semifinales(directorio: Path) -> Path | None:
    candidatos = sorted(directorio.glob("*- 2.csv")) + sorted(directorio.glob("*-2.csv"))
    return candidatos[0] if candidatos else None


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
            f"{partido.get('visitante')}: {len(candidatos)} coincidencias en la API."
        )

    invertido = {
        "local": partido["visitante"],
        "visitante": partido["local"],
    }
    candidatos_inv = [
        partido_api
        for partido_api in partidos_api
        if equipos_coinciden(invertido, partido_api, alias)
    ]
    if len(candidatos_inv) == 1:
        return candidatos_inv[0]
    if len(candidatos_inv) > 1:
        raise ValueError(
            f"Emparejamiento ambiguo (invertido) para {partido.get('local')} vs "
            f"{partido.get('visitante')}: {len(candidatos_inv)} coincidencias."
        )
    return None


def sincronizar_horarios_api(
    partidos: list[dict[str, Any]],
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
) -> int:
    semi = [
        partido_api
        for partido_api in partidos_api
        if partido_api.get("stage") == STAGE_SEMIFINALES
    ]
    sin_emparejar: list[str] = []

    for indice in range(INICIO_INDICE, FIN_INDICE):
        partido = partidos[indice]
        emparejado = _emparejar_api(partido, semi, alias)
        if emparejado is None:
            sin_emparejar.append(
                f"id {partido.get('id')} · {partido.get('local')} vs {partido.get('visitante')}"
            )
            continue

        utc_date = emparejado.get("utcDate")
        if not utc_date:
            home = nombre_equipo_api(emparejado, "home")
            away = nombre_equipo_api(emparejado, "away")
            raise ValueError(
                f"La API no devolvió utcDate para {home} vs {away}."
            )
        partido["fecha"], partido["hora"] = utc_a_fecha_hora_cest(utc_date)

    if sin_emparejar:
        raise ValueError(
            "No se pudo emparejar con la API:\n  "
            + "\n  ".join(sin_emparejar)
        )
    return FIN_INDICE - INICIO_INDICE


def actualizar_partidos(
    partidos_semifinales: list[dict[str, str]],
    partidos_api: list[dict[str, Any]] | None,
    alias: dict[str, str | list[str]],
) -> list[dict[str, Any]]:
    partidos = cargar_json(PARTIDOS_FILE)
    if not isinstance(partidos, list) or len(partidos) < FIN_INDICE:
        raise ValueError("partidos.json incompleto.")

    for offset, datos in enumerate(partidos_semifinales):
        indice = INICIO_INDICE + offset
        partido = partidos[indice]
        if partido.get("fase") != "semifinales":
            raise ValueError(
                f"Partido id {partido.get('id')} en índice {indice} "
                f"no es semifinales ({partido.get('fase')})."
            )
        partido["local"] = datos["local"]
        partido["visitante"] = datos["visitante"]

    if partidos_api is not None:
        sincronizar_horarios_api(partidos, partidos_api, alias)
    else:
        print(
            "Aviso: sin FOOTBALL_DATA_API_KEY no se sincronizan fecha/hora desde la API.",
            file=sys.stderr,
        )

    guardar_json(partidos, PARTIDOS_FILE)
    return partidos[INICIO_INDICE:FIN_INDICE]


def main() -> int:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    partidos_api: list[dict[str, Any]] | None = None

    try:
        alias = cargar_json(ALIAS_FILE)
        if not isinstance(alias, dict):
            raise ValueError("equipos_alias.json debe ser un objeto JSON.")

        partidos = cargar_json(PARTIDOS_FILE)
        resultados = cargar_json(RESULTADOS_FILE)
        if not isinstance(partidos, list) or not isinstance(resultados, list):
            raise ValueError("partidos.json o resultados.json inválidos.")

        csv_path = (
            Path(sys.argv[1])
            if len(sys.argv) > 1
            else buscar_csv_semifinales(INPUT_DIR)
        )

        if csv_path is not None:
            partidos_semifinales = leer_partidos_csv(csv_path)
            origen = csv_path.name
        else:
            ganadores = ganadores_cuartos(partidos, resultados)
            partidos_semifinales = resolver_semifinales_desde_ganadores(ganadores)
            origen = "ganadores de cuartos"

        if api_key:
            partidos_api = consultar_api(api_key)

        actualizados = actualizar_partidos(partidos_semifinales, partidos_api, alias)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"✓ {len(actualizados)} semifinales cargadas desde {origen}\n")
    for partido in actualizados:
        print(
            f"  id {partido['id']:>2} · {partido['fecha']} {partido['hora']} · "
            f"{partido['local']} vs {partido['visitante']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
