"""Genera docs/status.json tras una sincronización completa exitosa."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROYECTO_DIR = Path(__file__).resolve().parent.parent
RUN_STATS_FILE = PROYECTO_DIR / ".run" / "actualizar_stats.json"
DOCS_DIR = PROYECTO_DIR / "docs"
STATUS_FILE = DOCS_DIR / "status.json"


def cargar_json(ruta: Path) -> Any:
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def guardar_json(contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def instante_utc_iso(valor: datetime | None = None) -> str:
    instante = valor or datetime.now(timezone.utc)
    return instante.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalizar_iso8601(valor: str) -> str:
    texto = valor.strip()
    if texto.endswith("Z"):
        return texto
    if "+" in texto:
        return texto
    return f"{texto}Z"


def obtener_marca_workflow() -> str:
    """Usa la hora real del workflow en GitHub Actions si está disponible."""
    candidatos = (
        os.environ.get("GITHUB_RUN_STARTED_AT", "").strip(),
        os.environ.get("GITHUB_EVENT_HEAD_COMMIT_TIMESTAMP", "").strip(),
    )
    for candidato in candidatos:
        if candidato:
            return normalizar_iso8601(candidato)
    return instante_utc_iso()


def main() -> int:
    if not RUN_STATS_FILE.exists():
        print(
            "Error: no se encontró .run/actualizar_stats.json. "
            "Ejecuta actualizar_resultados.py antes de generar el estado.",
            file=sys.stderr,
        )
        return 1

    try:
        run_stats = cargar_json(RUN_STATS_FILE)
        if not isinstance(run_stats, dict):
            raise ValueError("actualizar_stats.json debe ser un objeto JSON.")
        if not run_stats.get("lastApiCheck"):
            raise ValueError("actualizar_stats.json no contiene lastApiCheck.")

        status = {
            "lastWorkflowRun": obtener_marca_workflow(),
            "lastApiCheck": run_stats["lastApiCheck"],
            "workflowStatus": "ok",
            "matchesUpdated": int(run_stats.get("matchesUpdated", 0)),
            "finishedMatches": int(run_stats.get("finishedMatches", 0)),
        }

        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        guardar_json(status, STATUS_FILE)
        RUN_STATS_FILE.unlink(missing_ok=True)

        print(f"✓ Estado del sistema → {STATUS_FILE.as_posix()}")
        print(f"  lastWorkflowRun: {status['lastWorkflowRun']}")
        print(f"  lastApiCheck: {status['lastApiCheck']}")
        print(f"  matchesUpdated: {status['matchesUpdated']}")
        print(f"  finishedMatches: {status['finishedMatches']}")
        return 0
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
