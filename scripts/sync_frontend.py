"""Sincroniza participantes y resultados con el frontend en docs/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROYECTO_DIR = Path(__file__).resolve().parent.parent
PARTICIPANTES_DIR = PROYECTO_DIR / "participantes"
RESULTADOS_FILE = PROYECTO_DIR / "resultados.json"
DOCS_DIR = PROYECTO_DIR / "docs"
DOCS_PARTICIPANTES_FILE = DOCS_DIR / "participantes.json"
DOCS_PARTICIPANTES_JS_FILE = DOCS_DIR / "participantes.js"
DOCS_RESULTADOS_FILE = DOCS_DIR / "resultados.json"
DOCS_RESULTADOS_JS_FILE = DOCS_DIR / "resultados.js"


def guardar_json(contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def guardar_modulo_js(variable: str, contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        archivo.write(f"window.{variable} = ")
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write(";\n")


def cargar_participantes() -> dict[str, Any]:
    participantes: dict[str, Any] = {}
    for ruta in sorted(PARTICIPANTES_DIR.glob("*.json")):
        with ruta.open(encoding="utf-8") as archivo:
            datos = json.load(archivo)
        participantes[datos["nombre"]] = datos
    return participantes


def main() -> int:
    if not PARTICIPANTES_DIR.exists():
        print(f"Error: no se encontró {PARTICIPANTES_DIR.as_posix()}/")
        return 1
    if not RESULTADOS_FILE.exists():
        print(f"Error: no se encontró {RESULTADOS_FILE.as_posix()}")
        return 1

    participantes = cargar_participantes()
    resultados = json.loads(RESULTADOS_FILE.read_text(encoding="utf-8"))

    DOCS_DIR.mkdir(exist_ok=True)
    guardar_json(participantes, DOCS_PARTICIPANTES_FILE)
    guardar_modulo_js("__PARTICIPANTES__", participantes, DOCS_PARTICIPANTES_JS_FILE)
    guardar_json(resultados, DOCS_RESULTADOS_FILE)
    guardar_modulo_js("__RESULTADOS__", resultados, DOCS_RESULTADOS_JS_FILE)

    print(f"✓ {len(participantes)} participantes → docs/participantes.js")
    print(f"✓ {len(resultados)} resultados → docs/resultados.js")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
