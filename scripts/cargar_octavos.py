"""Actualiza partidos.json con los octavos reales.

Resuelve W73–W88 desde resultados.json (clasifica) o, si hay CSV en input/,
toma equipos desde el CSV y sincroniza fecha/hora CEST con football-data.org.
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
)

PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
INPUT_DIR = PROYECTO_DIR.parent / "mundial-json-converter" / "input"
CLASIFICA_HEADER = "CLASIFICA"
INICIO_INDICE = 88  # partido id 89
FIN_INDICE = 96  # exclusivo, partido id 96
STAGE_OCTAVOS = "LAST_16"
ZONA_CEST = ZoneInfo("Europe/Madrid")

TEAM_NAME_PATTERN = re.compile(r"[A-Za-zÀ-ÿ]")
NOMBRES_CANONICOS = {
    "Bosnia": "Bosnia y Herzegovina",
}

CRUCE_OCTAVOS: list[tuple[str, str]] = [
    ("W75", "W77"),  # id 89
    ("W73", "W76"),  # id 90
    ("W74", "W78"),  # id 91
    ("W79", "W80"),  # id 92
    ("W83", "W84"),  # id 93
    ("W81", "W82"),  # id 94
    ("W86", "W88"),  # id 95
    ("W85", "W87"),  # id 96
]

# Horarios oficiales octavos en CEST (emparejamiento por equipos, no por id).
FIXTURES_OCTAVOS_CEST: list[dict[str, str]] = [
    {"local": "Paraguay", "visitante": "Noruega", "fecha": "2026-07-04", "hora": "23:00"},
    {"local": "Canadá", "visitante": "Marruecos", "fecha": "2026-07-04", "hora": "19:00"},
    {"local": "Brasil", "visitante": "Francia", "fecha": "2026-07-05", "hora": "22:00"},
    {"local": "México", "visitante": "Inglaterra", "fecha": "2026-07-06", "hora": "02:00"},
    {"local": "España", "visitante": "Portugal", "fecha": "2026-07-06", "hora": "21:00"},
    {"local": "Bélgica", "visitante": "Estados Unidos", "fecha": "2026-07-07", "hora": "02:00"},
    {"local": "Egipto", "visitante": "Colombia", "fecha": "2026-07-07", "hora": "18:00"},
    {"local": "Suiza", "visitante": "Argentina", "fecha": "2026-07-07", "hora": "22:00"},
]

# Compatibilidad con asignación legacy por id (cuadro FIFA W73–W88).
HORARIOS_OCTAVOS_CEST: dict[int, tuple[str, str]] = {
    89: ("2026-07-04", "23:00"),
    90: ("2026-07-04", "19:00"),
    91: ("2026-07-05", "22:00"),
    92: ("2026-07-06", "02:00"),
    93: ("2026-07-06", "21:00"),
    94: ("2026-07-07", "02:00"),
    95: ("2026-07-07", "18:00"),
    96: ("2026-07-07", "22:00"),
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


def ganadores_dieciseisavos(
    partidos: list[dict[str, Any]],
    resultados: list[Any],
) -> dict[str, str]:
    """Mapa W{id} → nombre del equipo clasificado."""
    ganadores: dict[str, str] = {}
    pendientes: list[str] = []

    for indice, partido in enumerate(partidos):
        if partido.get("fase") != "dieciseisavos":
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
            "Faltan resultados de dieciseisavos para resolver octavos:\n  "
            + "\n  ".join(pendientes)
        )
    return ganadores


def resolver_octavos_desde_ganadores(
    ganadores: dict[str, str],
) -> list[dict[str, str]]:
    """Genera local/visitante para los 8 octavos a partir del cuadro FIFA."""
    partidos: list[dict[str, str]] = []
    for local_ph, visitante_ph in CRUCE_OCTAVOS:
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


def _pareja_equipos(a: str, b: str) -> frozenset[str]:
    return frozenset({a.strip(), b.strip()})


def asignar_horario_octavo(local: str, visitante: str) -> tuple[str, str] | None:
    """Busca fecha/hora CEST por cruce exacto o por equipo local en calendario FIFA."""
    par = _pareja_equipos(local, visitante)
    for fixture in FIXTURES_OCTAVOS_CEST:
        if _pareja_equipos(fixture["local"], fixture["visitante"]) == par:
            return fixture["fecha"], fixture["hora"]

    por_local = [
        fixture
        for fixture in FIXTURES_OCTAVOS_CEST
        if fixture["local"] == local or fixture["visitante"] == local
    ]
    if len(por_local) == 1:
        fixture = por_local[0]
        return fixture["fecha"], fixture["hora"]

    por_visitante = [
        fixture
        for fixture in FIXTURES_OCTAVOS_CEST
        if fixture["local"] == visitante or fixture["visitante"] == visitante
    ]
    if len(por_visitante) == 1:
        fixture = por_visitante[0]
        return fixture["fecha"], fixture["hora"]

    return None


def normalizar_fecha_csv(value: Any) -> str | None:
    if pd.isna(value):
        return None
    texto = str(value).strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def leer_partidos_csv(csv_path: Path) -> list[dict[str, str]]:
    df = pd.read_csv(csv_path, encoding="utf-8", header=None)
    if df.shape[1] < 4:
        raise ValueError(f"{csv_path.name} no tiene columnas suficientes.")

    partidos: list[dict[str, str]] = []
    for _, fila in df.iloc[1:].iterrows():
        if pd.isna(fila[0]) and pd.isna(fila[1]):
            continue
        entrada: dict[str, str] = {
            "local": normalizar_equipo(fila[1]),
            "visitante": normalizar_equipo(fila[3]),
        }
        fecha = normalizar_fecha_csv(fila[0])
        if fecha:
            entrada["fecha"] = fecha
        partidos.append(entrada)

    esperados = FIN_INDICE - INICIO_INDICE
    if len(partidos) != esperados:
        raise ValueError(
            f"Se esperaban {esperados} partidos en {csv_path.name}, hay {len(partidos)}."
        )
    return partidos


def buscar_csv_octavos(directorio: Path) -> Path | None:
    candidatos = sorted(directorio.glob("*- 8.csv")) + sorted(directorio.glob("*-8.csv"))
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


def sincronizar_horarios_api(
    partidos: list[dict[str, Any]],
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
) -> int:
    """Actualiza fecha/hora CEST de octavos emparejando equipos con la API."""
    last16 = [
        partido_api
        for partido_api in partidos_api
        if partido_api.get("stage") == STAGE_OCTAVOS
    ]
    sin_emparejar: list[str] = []

    for indice in range(INICIO_INDICE, FIN_INDICE):
        partido = partidos[indice]
        candidatos = [
            partido_api
            for partido_api in last16
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
    partidos_octavos: list[dict[str, str]],
    partidos_api: list[dict[str, Any]] | None,
    alias: dict[str, str | list[str]],
) -> list[dict[str, Any]]:
    partidos = cargar_json(PARTIDOS_FILE)
    if not isinstance(partidos, list) or len(partidos) < FIN_INDICE:
        raise ValueError("partidos.json incompleto.")

    for offset, datos in enumerate(partidos_octavos):
        indice = INICIO_INDICE + offset
        partido = partidos[indice]
        if partido.get("fase") != "octavos":
            raise ValueError(
                f"Partido id {partido.get('id')} en índice {indice} "
                f"no es octavos ({partido.get('fase')})."
            )
        partido["local"] = datos["local"]
        partido["visitante"] = datos["visitante"]

    if partidos_api is not None:
        sincronizar_horarios_api(partidos, partidos_api, alias)
    else:
        print(
            "Aviso: sin FOOTBALL_DATA_API_KEY; se usan horarios oficiales FIFA en CEST.",
            file=sys.stderr,
        )
        for offset in range(FIN_INDICE - INICIO_INDICE):
            indice = INICIO_INDICE + offset
            partido = partidos[indice]
            datos = partidos_octavos[offset]
            horario = asignar_horario_octavo(partido["local"], partido["visitante"])
            if horario:
                partido["fecha"], partido["hora"] = horario
            elif datos.get("fecha"):
                partido["fecha"] = datos["fecha"]
                match_id = partido.get("id")
                if isinstance(match_id, int) and match_id in HORARIOS_OCTAVOS_CEST:
                    _, partido["hora"] = HORARIOS_OCTAVOS_CEST[match_id]
            elif isinstance(partido.get("id"), int) and partido["id"] in HORARIOS_OCTAVOS_CEST:
                partido["fecha"], partido["hora"] = HORARIOS_OCTAVOS_CEST[partido["id"]]

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
            else buscar_csv_octavos(INPUT_DIR)
        )

        if csv_path is not None:
            partidos_octavos = leer_partidos_csv(csv_path)
            origen = csv_path.name
        else:
            ganadores = ganadores_dieciseisavos(partidos, resultados)
            partidos_octavos = resolver_octavos_desde_ganadores(ganadores)
            origen = "ganadores de dieciseisavos"

        if api_key:
            partidos_api = consultar_api(api_key)

        actualizados = actualizar_partidos(partidos_octavos, partidos_api, alias)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"✓ {len(actualizados)} octavos cargados desde {origen}\n")
    for partido in actualizados:
        print(
            f"  id {partido['id']:>2} · {partido['fecha']} {partido['hora']} · "
            f"{partido['local']} vs {partido['visitante']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
