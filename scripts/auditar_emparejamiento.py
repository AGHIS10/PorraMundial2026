"""Audita el emparejamiento entre partidos.json y football-data.org."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR / "scripts"))

from actualizar_resultados import (  # noqa: E402
    ALIAS_FILE,
    API_KEY_ENV,
    PARTIDOS_FILE,
    RESULTADOS_FILE,
    cargar_json,
    consultar_partidos_api,
    diagnosticar_partido,
    filtrar_partidos_grupos_api,
    formatear_partido,
    nombre_equipo_api,
    nombres_equipo_coinciden,
)


def listar_equipos_api(partidos_api: list[dict[str, Any]]) -> set[str]:
    """Devuelve todos los nombres de equipos presentes en la API."""
    equipos: set[str] = set()
    for partido in partidos_api:
        equipos.add(nombre_equipo_api(partido, "home"))
        equipos.add(nombre_equipo_api(partido, "away"))
    equipos.discard("")
    return equipos


def auditar_alias(
    partidos: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
    equipos_api: set[str],
) -> list[str]:
    """Detecta equipos locales sin cobertura clara en la API."""
    avisos: list[str] = []
    equipos_locales = sorted({nombre for p in partidos for nombre in (p["local"], p["visitante"])})

    for equipo in equipos_locales:
        coincidencias = sorted(
            nombre_api
            for nombre_api in equipos_api
            if nombres_equipo_coinciden(equipo, nombre_api, alias)
        )
        if not coincidencias:
            avisos.append(
                f"[ALIAS] '{equipo}' no tiene coincidencia en la API de fase de grupos"
            )
    return avisos


def main() -> int:
    """Ejecuta la auditoría completa."""
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        print(f"Error: falta la variable de entorno {API_KEY_ENV}.", file=sys.stderr)
        return 1

    partidos = cargar_json(PARTIDOS_FILE)
    alias = cargar_json(ALIAS_FILE)
    resultados = cargar_json(RESULTADOS_FILE) if RESULTADOS_FILE.exists() else []

    print("=" * 72)
    print("AUDITORÍA DE EMPAREJAMIENTO — PORRA MUNDIAL 2026")
    print("=" * 72)

    if len(resultados) != len(partidos):
        print(
            f"[ERROR] resultados.json ({len(resultados)}) y partidos.json "
            f"({len(partidos)}) no tienen la misma longitud."
        )
        return 1
    print(f"[OK] resultados.json y partidos.json tienen {len(partidos)} entradas alineadas")

    try:
        partidos_api_total = consultar_partidos_api(api_key)
    except requests.RequestException as exc:
        print(f"[ERROR] No se pudo consultar la API: {exc}", file=sys.stderr)
        return 1

    partidos_api = filtrar_partidos_grupos_api(partidos_api_total)
    equipos_api = listar_equipos_api(partidos_api)

    print(f"Partidos en partidos.json: {len(partidos)}")
    print(f"Partidos en API (total): {len(partidos_api_total)}")
    print(f"Partidos en API (fase de grupos): {len(partidos_api)}")
    print(f"Equipos distintos en API (grupos): {len(equipos_api)}")
    print()

    avisos_alias = auditar_alias(partidos, alias, equipos_api)
    if avisos_alias:
        print("--- REVISIÓN DE ALIAS ---")
        for aviso in avisos_alias:
            print(aviso)
        print()

    emparejados = 0
    no_emparejados: list[tuple[dict[str, Any], str]] = []
    api_usados: dict[int, int] = {}

    print("--- EMPAREJAMIENTO PARTIDO A PARTIDO ---")
    for indice, partido in enumerate(partidos, start=1):
        etiqueta = formatear_partido(partido)
        partido_api, motivo = diagnosticar_partido(partido, partidos_api, alias)

        if partido_api is None:
            print(f"\nNO EMPAREJADO #{indice}")
            print(f"Fecha: {partido['fecha']} {partido['hora']}")
            print(f"Partido: {etiqueta}")
            print(f"Motivo: {motivo}")
            no_emparejados.append((partido, motivo or "Desconocido"))
            continue

        emparejados += 1
        api_id = partido_api.get("id")
        if api_id is not None:
            api_usados[api_id] = api_usados.get(api_id, 0) + 1

        home_api = nombre_equipo_api(partido_api, "home") or "?"
        away_api = nombre_equipo_api(partido_api, "away") or "?"
        print(
            f"[OK] #{indice:02d} {partido['fecha']} {etiqueta} → "
            f"{home_api} vs {away_api} ({partido_api.get('utcDate', '?')})"
        )

    duplicados = {api_id: veces for api_id, veces in api_usados.items() if veces > 1}
    if duplicados:
        print("\n[WARN] Partidos API asignados más de una vez:")
        for api_id, veces in duplicados.items():
            print(f"  - API id {api_id}: {veces} veces")

    print()
    print("=" * 72)
    print("RESUMEN")
    print("=" * 72)
    print(f"Total partidos: {len(partidos)}")
    print(f"Emparejados: {emparejados}/{len(partidos)}")
    print(f"No emparejados: {len(no_emparejados)}")

    if no_emparejados:
        print("\nDetalle de no emparejados:")
        for partido, motivo in no_emparejados:
            print(f"  - {partido['fecha']} {formatear_partido(partido)}: {motivo}")
        return 2

    print(f"\nResultado: {len(partidos)}/{len(partidos)} emparejamiento válido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
