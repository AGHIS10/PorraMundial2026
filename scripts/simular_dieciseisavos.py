"""Simula resultados de dieciseisavos y verifica puntuación (dry-run o aplicar).

Uso:
  python3 scripts/simular_dieciseisavos.py              # escenario mixto + informe
  python3 scripts/simular_dieciseisavos.py --perfecto   # todos aciertos Agustín
  python3 scripts/simular_dieciseisavos.py --aplicar    # escribe resultados simulados
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))
sys.path.insert(0, str(PROYECTO_DIR / "scripts"))

from apuestas import contar_aciertos_apuesta, puntos_apuesta, puntos_por_tipo_apuesta  # noqa: E402
from calcular_clasificacion import (  # noqa: E402
    cargar_partidos,
    cargar_participante,
    cargar_resultados,
    calcular_puntos,
    contar_aciertos,
    evaluar_participante,
    ContextoPorra,
)

PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
RESULTADOS_FILE = PROYECTO_DIR / "resultados.json"
PARTICIPANTES_DIR = PROYECTO_DIR / "participantes"
INICIO = 72
FIN = 88


def cargar_json(ruta: Path) -> Any:
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def guardar_json(data: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def escenario_perfecto(pronosticos: list[Any]) -> list[dict[str, str]]:
    """Resultado oficial = pronóstico de Agustín en cada partido."""
    return [dict(p) for p in pronosticos[INICIO:FIN]]


def escenario_mixto(pronosticos: list[Any]) -> list[dict[str, str]]:
    """Casos variados: pleno, solo resultado, solo clasifica, penaltis, cero."""
    casos: list[dict[str, str]] = [
        {"resultado": "2", "clasifica": "2"},       # pleno (pred 2/2)
        {"resultado": "1", "clasifica": "1"},       # pleno (pred 1/1)
        {"resultado": "X", "clasifica": "1"},       # solo clasifica (pred 1/1, empate+local)
        {"resultado": "X", "clasifica": "2"},       # pleno (pred X/2)
        {"resultado": "1", "clasifica": "1"},       # cero (pred 2/2)
        {"resultado": "1", "clasifica": "1"},       # pleno
        {"resultado": "2", "clasifica": "2"},       # cero (pred 1/1)
        {"resultado": "X", "clasifica": "1"},       # pleno (pred X/1)
        {"resultado": "1", "clasifica": "2"},       # solo resultado (pred 1/1)
        {"resultado": "X", "clasifica": "2"},       # solo clasifica (pred 1/1)
        {"resultado": "2", "clasifica": "1"},       # cero (pred X/1)
        {"resultado": "1", "clasifica": "1"},       # pleno
        {"resultado": "X", "clasifica": "2"},       # cero (pred 1/1)
        {"resultado": "2", "clasifica": "2"},       # pleno (pred 2/2)
        {"resultado": "2", "clasifica": "2"},       # cero (pred 1/1)
        {"resultado": "1", "clasifica": "1"},       # pleno (pred 1/1)
    ]
    if len(casos) != FIN - INICIO:
        raise ValueError("Escenario mixto mal dimensionado.")
    return casos


def icono(ok: bool) -> str:
    return "✓" if ok else "✗"


def analizar_partido(
    partido: dict[str, Any],
    pronostico: Any,
    resultado: dict[str, str],
) -> dict[str, Any]:
    fase = partido.fase
    pts_res = puntos_por_tipo_apuesta(fase, "resultado")
    pts_cls = puntos_por_tipo_apuesta(fase, "clasifica")
    pron = pronostico if isinstance(pronostico, dict) else {"resultado": pronostico, "clasifica": None}
    acierto_res = pron.get("resultado") == resultado.get("resultado")
    acierto_cls = pron.get("clasifica") == resultado.get("clasifica")
    puntos = puntos_apuesta(pronostico, resultado, fase)
    return {
        "acierto_res": acierto_res,
        "acierto_cls": acierto_cls,
        "pts_res": pts_res if acierto_res else 0,
        "pts_cls": pts_cls if acierto_cls else 0,
        "puntos": puntos,
        "pronostico": pron,
        "resultado": resultado,
    }


def imprimir_informe(
    partidos: list[Any],
    pronosticos: list[Any],
    simulados: list[dict[str, str]],
    puntos_grupos_previos: int,
    aciertos_grupos_previos: int,
) -> tuple[int, int]:
    pts_fase = 0
    aciertos_fase = 0
    pt_unit = puntos_por_tipo_apuesta("dieciseisavos", "resultado")

    print(f"\n{'=' * 88}")
    print("SIMULACIÓN DIECISEISAVOS — AGUSTIN")
    print(f"Puntos por acierto (resultado o clasifica): {pt_unit} pt  |  Máx. por partido: {pt_unit * 2} pt")
    print(f"{'=' * 88}")
    print(f"{'ID':>3}  {'Partido':<36} {'Pred':^7} {'Real':^7} {'Res':^3} {'Cls':^3} {'Pts':>4}")
    print("-" * 88)

    for offset, resultado in enumerate(simulados):
        idx = INICIO + offset
        partido = partidos[idx]
        pron = pronosticos[idx]
        info = analizar_partido(partido, pron, resultado)
        pts_fase += info["puntos"]
        aciertos_fase += contar_aciertos_apuesta(pron, resultado, partido.fase)

        pred_s = f"{info['pronostico']['resultado']}/{info['pronostico']['clasifica']}"
        real_s = f"{resultado['resultado']}/{resultado['clasifica']}"
        partido_s = f"{partido.local} vs {partido.visitante}"[:36]
        print(
            f"{partido.id:>3}  {partido_s:<36} {pred_s:^7} {real_s:^7} "
            f"{icono(info['acierto_res']):^3} {icono(info['acierto_cls']):^3} {info['puntos']:>4}"
        )

    print("-" * 88)
    print(f"Subtotal dieciseisavos: {pts_fase} pts  |  {aciertos_fase} aciertos (apuestas)")
    print(f"Grupos (ya jugados):    {puntos_grupos_previos} pts  |  {aciertos_grupos_previos} aciertos")
    print(f"TOTAL simulado Agustín: {puntos_grupos_previos + pts_fase} pts  |  "
          f"{aciertos_grupos_previos + aciertos_fase} aciertos")
    print(f"{'=' * 88}\n")
    return pts_fase, aciertos_fase


def verificar_motor(
    partidos: list[Any],
    pronosticos: list[Any],
    resultados_completos: list[Any],
) -> None:
    participante = cargar_participante(PARTICIPANTES_DIR / "AGUSTIN.json")
    contexto = ContextoPorra(partidos=partidos, resultados=resultados_completos)
    entrada = evaluar_participante(participante, contexto)
    puntos_directo = calcular_puntos(participante.pronosticos, resultados_completos, partidos)
    aciertos_directo = contar_aciertos(participante.pronosticos, resultados_completos, partidos)
    ok_pts = entrada.puntos == puntos_directo
    ok_ac = entrada.aciertos == aciertos_directo
    print("Verificación calcular_clasificacion.py:")
    print(f"  evaluar_participante → {entrada.puntos} pts, {entrada.aciertos} aciertos")
    print(f"  funciones directas    → {puntos_directo} pts, {aciertos_directo} aciertos")
    print(f"  Coherencia: {'OK ✓' if ok_pts and ok_ac else 'ERROR ✗'}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simula dieciseisavos y verifica puntuación.")
    parser.add_argument("--perfecto", action="store_true", help="Agustín acierta las 16 enteras.")
    parser.add_argument("--aplicar", action="store_true", help="Escribe resultados simulados en resultados.json.")
    args = parser.parse_args()

    partidos, _ = cargar_partidos(PARTIDOS_FILE)
    agustin = cargar_json(PARTICIPANTES_DIR / "AGUSTIN.json")
    pronosticos = agustin["pronosticos"]
    resultados_actuales = cargar_resultados(RESULTADOS_FILE)

    # Puntos de grupos (índices 0-71)
    ctx_grupos = ContextoPorra(
        partidos=partidos,
        resultados=resultados_actuales[:INICIO] + [None] * (len(resultados_actuales) - INICIO),
    )
    # Solo contar grupos con resultados reales
    pts_grupos = 0
    ac_grupos = 0
    for i in range(INICIO):
        if resultados_actuales[i] is not None:
            pts_grupos += puntos_apuesta(pronosticos[i], resultados_actuales[i], partidos[i].fase)
            ac_grupos += contar_aciertos_apuesta(
                pronosticos[i], resultados_actuales[i], partidos[i].fase
            )

    escenario = escenario_perfecto(pronosticos) if args.perfecto else escenario_mixto(pronosticos)
    nombre_escenario = "PERFECTO (16/16 plenos)" if args.perfecto else "MIXTO (aciertos parciales y fallos)"
    print(f"\nEscenario: {nombre_escenario}")

    imprimir_informe(partidos, pronosticos, escenario, pts_grupos, ac_grupos)

    resultados_sim = list(resultados_actuales)
    for offset, res in enumerate(escenario):
        resultados_sim[INICIO + offset] = res

    verificar_motor(partidos, pronosticos, resultados_sim)

    if args.aplicar:
        guardar_json(resultados_sim, RESULTADOS_FILE)
        print(f"✓ resultados.json actualizado con simulación ({FIN - INICIO} dieciseisavos).")
        print("  Ejecuta: python3 scripts/calcular_clasificacion.py && python3 scripts/sync_frontend.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
