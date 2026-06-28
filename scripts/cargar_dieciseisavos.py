"""Actualiza partidos.json con los dieciseisavos reales desde un CSV de porra.

Carga equipos desde el CSV y sincroniza fecha/hora en CEST desde football-data.org
emparejando por local/visitante. Así evitamos mezclar el día del calendario US
del CSV con la hora CEST del slot FIFA anterior.
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
    cargar_json,
    equipos_coinciden,
    guardar_json,
)

PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
INPUT_DIR = PROYECTO_DIR.parent / "mundial-json-converter" / "input"
CLASIFICA_HEADER = "CLASIFICA"
INICIO_INDICE = 72  # partido id 73
FIN_INDICE = 88  # exclusivo, partido id 88
STAGE_Dieciseisavos = "LAST_32"
ZONA_CEST = ZoneInfo("Europe/Madrid")

TEAM_NAME_PATTERN = re.compile(r"[A-Za-zÀ-ÿ]")
NOMBRES_CANONICOS = {
    "Bosnia": "Bosnia y Herzegovina",
}


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


def leer_partidos_csv(csv_path: Path) -> list[dict[str, str]]:
    df = pd.read_csv(csv_path, encoding="utf-8", header=None)
    if df.shape[1] < 4:
        raise ValueError(f"{csv_path.name} no tiene columnas suficientes.")

    inicio = 1
    if str(df.iloc[0, 4 if df.shape[1] >= 5 else 0]).strip().upper() == CLASIFICA_HEADER:
        inicio = 1

    partidos: list[dict[str, str]] = []
    for _, fila in df.iloc[inicio:].iterrows():
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


def buscar_csv_dieciseisavos(directorio: Path) -> Path:
    candidatos = sorted(directorio.glob("*- 16.csv")) + sorted(directorio.glob("*-16.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"No se encontró ningún CSV de dieciseisavos en {directorio.as_posix()}/."
        )
    return candidatos[0]


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


def sincronizar_horarios_api(
    partidos: list[dict[str, Any]],
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
) -> int:
    """Actualiza fecha/hora CEST de dieciseisavos emparejando equipos con la API."""
    last32 = [
        partido_api
        for partido_api in partidos_api
        if partido_api.get("stage") == STAGE_Dieciseisavos
    ]
    sin_emparejar: list[str] = []

    for indice in range(INICIO_INDICE, FIN_INDICE):
        partido = partidos[indice]
        candidatos = [
            partido_api
            for partido_api in last32
            if equipos_coinciden(partido, partido_api, alias)
        ]
        if not candidatos:
            sin_emparejar.append(
                f"id {partido.get('id')} · {partido.get('local')} vs {partido.get('visitante')}"
            )
            continue
        if len(candidatos) > 1:
            raise ValueError(
                f"Emparejamiento ambiguo para {partido.get('local')} vs "
                f"{partido.get('visitante')}: {len(candidatos)} coincidencias en la API."
            )
        utc_date = candidatos[0].get("utcDate")
        if not utc_date:
            raise ValueError(
                f"La API no devolvió utcDate para {partido.get('local')} vs "
                f"{partido.get('visitante')}."
            )
        partido["fecha"], partido["hora"] = utc_a_fecha_hora_cest(utc_date)

    if sin_emparejar:
        raise ValueError(
            "No se pudo emparejar con la API:\n  "
            + "\n  ".join(sin_emparejar)
        )
    return FIN_INDICE - INICIO_INDICE


def actualizar_partidos(
    partidos_csv: list[dict[str, str]],
    partidos_api: list[dict[str, Any]] | None,
    alias: dict[str, str | list[str]],
) -> list[dict[str, Any]]:
    partidos = cargar_json(PARTIDOS_FILE)
    if not isinstance(partidos, list) or len(partidos) < FIN_INDICE:
        raise ValueError("partidos.json incompleto.")

    for offset, datos_csv in enumerate(partidos_csv):
        indice = INICIO_INDICE + offset
        partido = partidos[indice]
        if partido.get("fase") != "dieciseisavos":
            raise ValueError(
                f"Partido id {partido.get('id')} en índice {indice} "
                f"no es dieciseisavos ({partido.get('fase')})."
            )
        partido["local"] = datos_csv["local"]
        partido["visitante"] = datos_csv["visitante"]

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
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else buscar_csv_dieciseisavos(INPUT_DIR)
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    partidos_api: list[dict[str, Any]] | None = None

    try:
        alias = cargar_json(ALIAS_FILE)
        if not isinstance(alias, dict):
            raise ValueError("equipos_alias.json debe ser un objeto JSON.")
        partidos_csv = leer_partidos_csv(csv_path)
        if api_key:
            partidos_api = consultar_api(api_key)
        actualizados = actualizar_partidos(partidos_csv, partidos_api, alias)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"✓ {len(actualizados)} dieciseisavos cargados desde {csv_path.name}\n")
    for partido in actualizados:
        print(
            f"  id {partido['id']:>2} · {partido['fecha']} {partido['hora']} · "
            f"{partido['local']} vs {partido['visitante']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
