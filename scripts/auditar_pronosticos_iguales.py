"""Detecta partidos jugados donde dos jugadores tienen el mismo pronóstico pero puntos distintos."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))

from apuestas import puntos_apuesta  # noqa: E402
from scripts.calcular_clasificacion import (  # noqa: E402
    PARTICIPANTES_DIR,
    PARTIDOS_FILE,
    RESULTADOS_FILE,
    cargar_participante,
    listar_participantes,
)


def main() -> int:
    partidos = json.loads(PARTIDOS_FILE.read_text(encoding="utf-8"))
    resultados = json.loads(RESULTADOS_FILE.read_text(encoding="utf-8"))
    participantes = [
        cargar_participante(ruta) for ruta in listar_participantes(PARTICIPANTES_DIR)
    ]

    inconsistencias: list[str] = []
    for i, partido in enumerate(partidos):
        resultado = resultados[i] if i < len(resultados) else None
        if resultado is None:
            continue
        fase = partido.get("fase", "grupos")
        por_pronostico: dict[str, list[tuple[str, int]]] = {}
        for p in participantes:
            if i >= len(p.pronosticos):
                continue
            pron = p.pronosticos[i]
            clave = json.dumps(pron, sort_keys=True, ensure_ascii=False)
            pts = puntos_apuesta(pron, resultado, fase)
            por_pronostico.setdefault(clave, []).append((p.nombre, pts))

        for clave, filas in por_pronostico.items():
            puntos_distintos = {pts for _, pts in filas}
            if len(puntos_distintos) > 1:
                nombres = ", ".join(f"{n}={pts}" for n, pts in filas)
                inconsistencias.append(
                    f"id {partido.get('id')} · {partido.get('local')} vs "
                    f"{partido.get('visitante')} [{fase}] pron={clave} → {nombres}"
                )

    if inconsistencias:
        print("INCONSISTENCIAS (mismo pronóstico, puntos distintos):\n")
        for linea in inconsistencias:
            print(f"  {linea}")
        return 1

    print("OK: ningún par con pronóstico idéntico recibe puntos distintos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
