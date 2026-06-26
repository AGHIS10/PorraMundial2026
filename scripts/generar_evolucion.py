"""Genera evolucion.json: la narrativa completa de la porra para el frontend.

Reutiliza los loaders de calcular_clasificacion (no duplica lógica) y delega
todo el cálculo en el módulo evolucion.py. Se ejecuta en el workflow después de
calcular_clasificacion.py.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))
sys.path.insert(0, str(PROYECTO_DIR / "scripts"))

from calcular_clasificacion import (  # noqa: E402
    PARTIDOS_FILE,
    RESULTADOS_FILE,
    PARTICIPANTES_DIR,
    cargar_participante,
    cargar_partidos,
    cargar_resultados,
    listar_participantes,
)
from evolucion import construir_evolucion  # noqa: E402

MARCADORES_FILE = PROYECTO_DIR / "marcadores.json"
EVOLUCION_FILE = PROYECTO_DIR / "evolucion.json"
DOCS_DIR = PROYECTO_DIR / "docs"
DOCS_EVOLUCION_FILE = DOCS_DIR / "evolucion.json"
DOCS_EVOLUCION_JS_FILE = DOCS_DIR / "evolucion.js"


def guardar_json(contenido, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def guardar_modulo_js(variable: str, contenido, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        archivo.write(f"window.{variable} = ")
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write(";\n")


def partido_a_dict(partido) -> dict:
    return {
        "id": partido.id,
        "fecha": partido.fecha,
        "hora": partido.hora,
        "local": partido.local,
        "visitante": partido.visitante,
        "fase": partido.fase,
        "peso": partido.peso,
    }


def cargar_marcadores(total: int) -> list:
    if not MARCADORES_FILE.exists():
        return [None] * total
    datos = json.loads(MARCADORES_FILE.read_text(encoding="utf-8"))
    if not isinstance(datos, list):
        return [None] * total
    return datos


def main() -> int:
    try:
        partidos, _ = cargar_partidos(PARTIDOS_FILE)
        resultados = cargar_resultados(RESULTADOS_FILE)
        marcadores = cargar_marcadores(len(partidos))

        participantes = []
        for ruta in listar_participantes(PARTICIPANTES_DIR):
            try:
                p = cargar_participante(ruta)
                participantes.append({"nombre": p.nombre, "pronosticos": p.pronosticos})
            except ValueError as exc:
                print(f"⚠ Participante {ruta.stem} ignorado: {exc}", file=sys.stderr)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    generado = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )

    evolucion = construir_evolucion(
        [partido_a_dict(p) for p in partidos],
        resultados,
        marcadores,
        participantes,
        generado,
    )

    guardar_json(evolucion, EVOLUCION_FILE)
    if DOCS_DIR.exists():
        guardar_json(evolucion, DOCS_EVOLUCION_FILE)
        guardar_modulo_js("__EVOLUCION__", evolucion, DOCS_EVOLUCION_JS_FILE)

    print(
        f"✓ evolucion.json → {evolucion['partidos_jugados']} partidos jugados, "
        f"{len(evolucion['participantes'])} participantes, "
        f"{len(evolucion['eventos'])} eventos detectados"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
