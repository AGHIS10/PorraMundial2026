"""Importa JSON de mundial-json-converter/output/ a participantes/."""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

PROYECTO_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROYECTO_DIR.parent / "mundial-json-converter" / "output"
PARTICIPANTES_DIR = PROYECTO_DIR / "participantes"

# Nombres del CSV de IA → clave normalizada del participante en participantes/
ALIAS_ORIGEN: dict[str, str] = {
    "ia gpt porra mundial 2026": "gpt",
    "ia gemini porra mundial 2026": "gemini",
}


def normalizar_nombre(nombre: str) -> str:
    texto = unicodedata.normalize("NFKD", nombre)
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return texto.strip().lower()


def main() -> int:
    if not OUTPUT_DIR.exists():
        print(f"Error: no existe {OUTPUT_DIR}", file=sys.stderr)
        return 1

    destinos = {
        normalizar_nombre(str(datos.get("nombre", ""))): ruta
        for ruta in PARTICIPANTES_DIR.glob("*.json")
        for datos in [json.loads(ruta.read_text(encoding="utf-8"))]
    }

    importados = 0
    for origen in sorted(OUTPUT_DIR.glob("*.json")):
        if origen.name == "partidos.json":
            continue
        datos = json.loads(origen.read_text(encoding="utf-8"))
        clave = normalizar_nombre(str(datos.get("nombre", "")))
        clave = ALIAS_ORIGEN.get(clave, clave)
        destino = destinos.get(clave)
        if destino is None:
            print(f"Aviso: sin destino para {origen.name} ({datos.get('nombre')})", file=sys.stderr)
            continue
        canonical = json.loads(destino.read_text(encoding="utf-8"))
        canonical["pronosticos"] = datos["pronosticos"]
        destino.write_text(
            json.dumps(canonical, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"✓ {origen.name} → {destino.name}")
        importados += 1

    if importados == 0:
        print("No se importó ningún participante.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
