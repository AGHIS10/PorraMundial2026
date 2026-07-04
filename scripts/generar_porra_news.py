"""Genera porra_news.json y actualiza humor_state.json tras cada jornada."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))
sys.path.insert(0, str(PROYECTO_DIR / "scripts"))

from calcular_clasificacion import (  # noqa: E402
    DOCS_DIR,
    PARTICIPANTES_DIR,
    PARTIDOS_FILE,
    RESULTADOS_FILE,
    cargar_participante,
    listar_participantes,
)
from porra_news import cargar_frases, generar_noticias  # noqa: E402

FRASES_DIR = PROYECTO_DIR / "frases"
HUMOR_STATE_FILE = PROYECTO_DIR / "humor_state.json"
PORRA_NEWS_FILE = PROYECTO_DIR / "porra_news.json"
EVOLUCION_FILE = PROYECTO_DIR / "evolucion.json"
PROYECCION_FILE = PROYECTO_DIR / "proyeccion.json"
CLASIFICACION_FILE = PROYECTO_DIR / "clasificacion.json"
DOCS_PORRA_NEWS = DOCS_DIR / "porra_news.json"
DOCS_PORRA_NEWS_JS = DOCS_DIR / "porra_news.js"


def guardar_json(contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def guardar_modulo_js(variable: str, contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        archivo.write(f"window.{variable} = ")
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write(";\n")


def cargar_json(ruta: Path) -> Any | None:
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def cargar_participantes_dict() -> dict[str, Any]:
    participantes: dict[str, Any] = {}
    for ruta in listar_participantes(PARTICIPANTES_DIR):
        try:
            p = cargar_participante(ruta)
            participantes[p.nombre] = {"nombre": p.nombre, "pronosticos": p.pronosticos}
        except ValueError:
            continue
    return participantes


def main() -> int:
    clasificacion = cargar_json(CLASIFICACION_FILE)
    if not isinstance(clasificacion, list) or not clasificacion:
        print(f"Error: {CLASIFICACION_FILE.as_posix()} vacío o inválido.", file=sys.stderr)
        return 1

    partidos_raw = cargar_json(PARTIDOS_FILE)
    resultados = cargar_json(RESULTADOS_FILE)
    if not isinstance(partidos_raw, list) or not isinstance(resultados, list):
        print("Error: partidos o resultados inválidos.", file=sys.stderr)
        return 1

    partidos = partidos_raw
    evolucion = cargar_json(EVOLUCION_FILE)
    proyeccion = cargar_json(PROYECCION_FILE)
    participantes = cargar_participantes_dict()
    frases = cargar_frases(FRASES_DIR)
    estado_previo = cargar_json(HUMOR_STATE_FILE)

    if not frases:
        print(f"Error: no hay plantillas en {FRASES_DIR.as_posix()}/", file=sys.stderr)
        return 1

    rng = random.Random(2026 + len(resultados))
    paquete, nuevo_estado = generar_noticias(
        clasificacion,
        evolucion if isinstance(evolucion, dict) else None,
        proyeccion if isinstance(proyeccion, dict) else None,
        participantes,
        partidos,
        resultados,
        frases,
        estado_previo if isinstance(estado_previo, dict) else None,
        rng,
    )

    guardar_json(nuevo_estado, HUMOR_STATE_FILE)
    guardar_json(paquete, PORRA_NEWS_FILE)

    if DOCS_DIR.exists():
        guardar_json(paquete, DOCS_PORRA_NEWS)
        guardar_modulo_js("__PORRA_NEWS__", paquete, DOCS_PORRA_NEWS_JS)

    n = len(paquete.get("noticias", []))
    primera = paquete["noticias"][0]["titulo"] if n else "—"
    print(f"✓ El Chiringuito de la Porra → {n} noticias · {primera[:55]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
