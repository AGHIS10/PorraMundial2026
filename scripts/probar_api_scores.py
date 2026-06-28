"""Diagnóstico de score/winner en football-data.org para la porra dual.

Uso:
  FOOTBALL_DATA_API_KEY=... python3 scripts/probar_api_scores.py

Documentación relevante:
  https://docs.football-data.org/general/v4/overtime.html
  https://docs.football-data.org/general/v4/match.html
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))
sys.path.insert(0, str(PROYECTO_DIR / "scripts"))

from actualizar_resultados import (  # noqa: E402
    API_SEASON,
    API_URL,
    clasifica_desde_api,
    duracion_partido_api,
    extraer_marcador_90min,
    extraer_marcador_desde_nodo,
    resultado_desde_api,
)

API_KEY_ENV = "FOOTBALL_DATA_API_KEY"


def consultar(api_key: str, **params: Any) -> list[dict[str, Any]]:
    respuesta = requests.get(
        API_URL,
        headers={"X-Auth-Token": api_key},
        params={"season": API_SEASON, **params},
        timeout=30,
    )
    respuesta.raise_for_status()
    return respuesta.json().get("matches", [])


def resumen_score(partido: dict[str, Any]) -> dict[str, Any]:
    score = partido.get("score") or {}
    marcador_90 = extraer_marcador_90min(partido)
    return {
        "id": partido.get("id"),
        "local": partido.get("homeTeam", {}).get("name"),
        "visitante": partido.get("awayTeam", {}).get("name"),
        "status": partido.get("status"),
        "stage": partido.get("stage"),
        "duration": duracion_partido_api(partido),
        "winner": score.get("winner"),
        "fullTime": score.get("fullTime"),
        "regularTime": score.get("regularTime"),
        "extraTime": score.get("extraTime"),
        "penalties": score.get("penalties"),
        "porra_resultado_90": resultado_desde_api(partido),
        "porra_clasifica": clasifica_desde_api(partido),
        "marcador_90_calculado": (
            {"home": marcador_90[0], "away": marcador_90[1]} if marcador_90 else None
        ),
    }


def analizar_lote(etiqueta: str, partidos: list[dict[str, Any]]) -> None:
    print(f"\n{'=' * 60}\n{etiqueta} ({len(partidos)} partidos)\n{'=' * 60}")
    if not partidos:
        print("  (ninguno)")
        return

    for partido in partidos[:5]:
        data = resumen_score(partido)
        print(json.dumps(data, ensure_ascii=False, indent=2))

    if len(partidos) > 5:
        print(f"  ... y {len(partidos) - 5} más")

    # Alertas
    for partido in partidos:
        score = partido.get("score") or {}
        duration = duracion_partido_api(partido)
        if duration in {"EXTRA_TIME", "PENALTY_SHOOTOUT"}:
            rt = extraer_marcador_desde_nodo(score, "regularTime")
            ft = extraer_marcador_desde_nodo(score, "fullTime")
            if rt and ft and rt != ft:
                print(
                    f"\n⚠ id {partido.get('id')}: duration={duration} — "
                    f"regularTime {rt} ≠ fullTime {ft} (usamos regularTime para 1/X/2)"
                )
            if rt is None:
                print(
                    f"\n⚠ id {partido.get('id')}: duration={duration} sin regularTime; "
                    "habrá que enriquecer con GET /v4/matches/{{id}}"
                )
        if partido.get("status") == "FINISHED" and not clasifica_desde_api(partido):
            if partido.get("stage") != "GROUP_STAGE":
                print(
                    f"\n⚠ id {partido.get('id')}: eliminatoria FINISHED sin clasifica "
                    f"(winner={score.get('winner')})"
                )


def main() -> int:
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        print(f"Error: define {API_KEY_ENV}", file=sys.stderr)
        return 1

    try:
        last32 = consultar(api_key, stage="LAST_32")
        last32_fin = [p for p in last32 if p.get("status") == "FINISHED"]
        grupos_fin = consultar(api_key, stage="GROUP_STAGE", status="FINISHED")

        analizar_lote("Mundial 2026 — dieciseisavos (todos)", last32)
        analizar_lote("Mundial 2026 — dieciseisavos FINISHED", last32_fin)
        analizar_lote("Mundial 2026 — grupos FINISHED (muestra)", grupos_fin[:3])

        # Histórico con penaltis (otra temporada, misma API)
        for season in (2018, 2022):
            try:
                hist = requests.get(
                    API_URL,
                    headers={"X-Auth-Token": api_key},
                    params={
                        "season": season,
                        "stage": "LAST_16",
                        "status": "FINISHED",
                    },
                    timeout=30,
                ).json().get("matches", [])
            except requests.RequestException:
                continue
            pen = [
                p for p in hist
                if duracion_partido_api(p) == "PENALTY_SHOOTOUT"
            ]
            if pen:
                analizar_lote(f"WC {season} — octavos con penaltis", pen[:2])

        print("\n--- Conclusión ---")
        print("• resultado (1/X/2): score.regularTime (90 min); si no existe y duration=REGULAR → fullTime")
        print("• clasifica (1/2): score.winner → HOME_TEAM=1, AWAY_TEAM=2")
        print("• NO usar fullTime en penaltis/prórroga: puede ser marcador global, no 90 min")
        print("• Si falta regularTime: GET /v4/matches/{id} (enriquecimiento ya implementado)")
        return 0
    except requests.RequestException as exc:
        print(f"Error de API: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
