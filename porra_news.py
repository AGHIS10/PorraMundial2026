"""Motor de Teleporra News: genera una lista ordenada de noticias listas para pintar."""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apuestas import apuesta_completa, partido_tiene_resultado
from evolucion import _posiciones as posiciones_por_puntos
from reparto_premios import es_participante_virtual

# Puntuación de prioridad (mayor = más importante, aparece antes en el informativo)
PRIORIDAD_SCORE: dict[str, int] = {
    "CAMBIO_LIDER": 100,
    "ENTRA_TOP3": 95,
    "SALE_TOP3": 94,
    "SUBIDA_4_MAS": 88,
    "BAJADA_4_MAS": 87,
    "REMONTADA_HISTORICA": 85,
    "HUNDIMIENTO_HISTORICO": 84,
    "SUBIDA_2_3_POSICIONES": 78,
    "BAJADA_2_3_POSICIONES": 77,
    "SUBIDA_1_POSICION": 72,
    "BAJADA_1_POSICION": 71,
    "NADIE_ACIERTA": 68,
    "SOLO_UNO_ACIERTA": 67,
    "RACHA_ACIERTOS": 62,
    "RACHA_FALLOS": 61,
    "CAMBIO_SIMULACIONES": 58,
    "LIDER_HUMANO": 57,
    "FAVORITO_SIMULADOR": 55,
    "PODIO_HUMANO": 53,
    "FAVORITO_NO_LIDER": 52,
    "ZONA_MEDIA": 35,
    "ZONA_BAJA": 33,
    "GPT_LIDER": 50,
    "GEMINI_LIDER": 50,
    "GPT_ULTIMO": 48,
    "GEMINI_ULTIMO": 48,
    "MUNDIAL_ABIERTO": 45,
    "MUNDIAL_DECIDIDO": 44,
    "EMPATE_LIDER": 43,
    "ULTIMO_CLASIFICADO": 40,
    "LIDER_RESISTE": 38,
    "JUGADOR_SPOT": 25,
}

TIPO_ETIQUETA: dict[str, str] = {
    "ULTIMA_HORA": "🔴 ÚLTIMA HORA",
    "EXCLUSIVA": "⭐ EXCLUSIVA",
    "TITULAR": "📰 TITULAR",
    "DECLARACIONES": "🎙️ DECLARACIONES",
    "RUMOR": "🟡 RUMOR",
    "INVESTIGACION": "🕵 INVESTIGACIÓN",
    "EL_BAR": "🍺 DESDE EL BAR",
    "COMUNICADO": "📢 COMUNICADO",
    "EDITORIAL": "📝 EDITORIAL",
}

RACHA_MINIMA = 3
RACHA_INDIVIDUAL = 2


@dataclass(frozen=True)
class ContextoNoticias:
    """Estado real de la porra para validar coherencia de noticias."""

    lider_global: str
    lider_humano: str
    favorito_sim_humano: str | None
    ultimo_h: str
    posiciones: dict[str, int]
    pos_humana: dict[str, int]   # posición dentro del ranking solo humanos (1-based)


@dataclass
class Candidato:
    categoria: str
    variables: dict[str, str]
    peso: int = 0
    jugador: str | None = None
    incluir_partido: bool = False
    prioridad: int = field(default=0)

    def __post_init__(self) -> None:
        if not self.prioridad:
            self.prioridad = PRIORIDAD_SCORE.get(self.categoria, 25)
        if not self.jugador:
            self.jugador = (
                self.variables.get("JUGADOR")
                or self.variables.get("FAVORITO")
                or self.variables.get("NUEVO_LIDER")
                or self.variables.get("LIDER")
                or self.variables.get("ULTIMO")
                or self.variables.get("IA")
            )


def _construir_contexto(
    clasificacion: list[dict[str, Any]],
    proyeccion: dict[str, Any] | None,
) -> ContextoNoticias:
    humanos = _humanos(clasificacion)
    favorito: str | None = None
    if proyeccion:
        for fila in proyeccion.get("campeon") or []:
            if not fila.get("es_ia"):
                favorito = fila["nombre"]
                break
    # posición 1-based dentro del ranking exclusivo de humanos
    pos_humana = {f["nombre"]: i + 1 for i, f in enumerate(humanos)}
    return ContextoNoticias(
        lider_global=clasificacion[0]["nombre"] if clasificacion else "",
        lider_humano=humanos[0]["nombre"] if humanos else "",
        favorito_sim_humano=favorito,
        ultimo_h=humanos[-1]["nombre"] if humanos else "",
        posiciones=_posiciones(clasificacion),
        pos_humana=pos_humana,
    )


def _rival_inmediato_superior(nombre: str, ctx: ContextoNoticias) -> str:
    pos = ctx.posiciones.get(nombre, 99)
    candidatos = [n for n, p in ctx.posiciones.items() if p == pos - 1]
    return candidatos[0] if candidatos else ctx.lider_humano


def _candidato_coherente(c: Candidato, ctx: ContextoNoticias) -> bool:
    cat = c.categoria
    jugador = c.jugador

    if cat == "FAVORITO_NO_LIDER":
        fav = c.variables.get("FAVORITO") or jugador or ""
        if fav == ctx.lider_global or fav == ctx.lider_humano:
            return False
        if jugador in (ctx.lider_humano, ctx.favorito_sim_humano):
            return False
        return True

    if cat == "LIDER_RESISTE":
        return c.variables.get("LIDER") == ctx.lider_global

    if cat == "GPT_LIDER":
        return ctx.lider_global == "GPT"
    if cat == "GEMINI_LIDER":
        return ctx.lider_global == "GEMINI"

    if cat == "ULTIMO_CLASIFICADO":
        return (c.variables.get("ULTIMO") or jugador) == ctx.ultimo_h

    if cat == "LIDER_HUMANO":
        return jugador == ctx.lider_humano

    if cat == "PODIO_HUMANO":
        return (
            jugador is not None
            and jugador != ctx.lider_humano
            and ctx.posiciones.get(jugador, 99) <= 3
        )

    if cat == "FAVORITO_SIMULADOR":
        fav = c.variables.get("FAVORITO") or jugador or ""
        return fav == ctx.favorito_sim_humano and fav != ctx.lider_humano

    return True


def _plantilla_valida(categoria: str, texto: str) -> bool:
    t = texto.lower()
    if categoria == "RACHA_FALLOS":
        if "no falla" in t or "aciert" in t or "acert" in t or "colecciona" in t:
            return False
    if categoria == "RACHA_ACIERTOS":
        if "fallo" in t and "no falla" not in t:
            return False
    return True


def _plantilla_coherente(categoria: str, texto: str, candidato: Candidato) -> bool:
    if not _plantilla_valida(categoria, texto):
        return False
    jugador = candidato.jugador
    if not jugador:
        return True
    if categoria.startswith(("BAJADA_", "SUBIDA_", "HUNDIMIENTO", "REMONTADA")):
        primera = texto.strip().split(".")[0]
        if "{JUGADOR}" not in primera:
            return False
        if "{RIVAL}" in texto and not (candidato.variables.get("RIVAL") or "").strip():
            return False
    return True


def _suprimir_contradicciones(
    candidatos: list[Candidato],
    ctx: ContextoNoticias,
) -> list[Candidato]:
    por_jugador: dict[str, list[Candidato]] = {}
    for c in candidatos:
        if c.jugador:
            por_jugador.setdefault(c.jugador, []).append(c)

    descartar: set[int] = set()
    for jugador, lista in por_jugador.items():
        cats = {c.categoria for c in lista}
        if "FAVORITO_SIMULADOR" in cats and "FAVORITO_NO_LIDER" in cats:
            for c in lista:
                if c.categoria == "FAVORITO_NO_LIDER":
                    descartar.add(id(c))
        if "LIDER_HUMANO" in cats and "FAVORITO_SIMULADOR" in cats:
            for c in lista:
                if c.categoria == "FAVORITO_SIMULADOR":
                    descartar.add(id(c))
        if jugador in (ctx.lider_humano, ctx.favorito_sim_humano):
            for c in lista:
                if c.categoria == "FAVORITO_NO_LIDER":
                    descartar.add(id(c))

    return [c for c in candidatos if id(c) not in descartar]


def cargar_frases(directorio: Path) -> dict[str, list[dict[str, str]]]:
    fusion: dict[str, list[dict[str, str]]] = {}
    vistos: set[tuple[str, str, str]] = set()
    for ruta in sorted(directorio.glob("frases*.json")):
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            continue
        fuente = ruta.stem
        for categoria, plantillas in datos.items():
            if not isinstance(plantillas, list):
                continue
            for idx_local, plantilla in enumerate(plantillas):
                if not isinstance(plantilla, dict):
                    continue
                clave = (
                    categoria,
                    str(plantilla.get("tipo", "")),
                    str(plantilla.get("texto", "")),
                )
                if clave in vistos:
                    continue
                vistos.add(clave)
                enriquecida = {**plantilla, "_fuente": fuente, "_idx_local": str(idx_local)}
                fusion.setdefault(categoria, []).append(enriquecida)
    return fusion


def _frase_id(categoria: str, plantilla: dict[str, str], idx_fallback: int) -> str:
    fuente = plantilla.get("_fuente")
    idx_local = plantilla.get("_idx_local")
    if fuente is not None and idx_local is not None:
        return f"{categoria}:{fuente}:{idx_local}"
    return f"{categoria}:{idx_fallback}"


def _posiciones_en_paso(
    evolucion: dict[str, Any] | None,
    paso: int,
) -> dict[str, int] | None:
    """Posiciones con empates compartidos (solo puntos) en un paso de la evolución."""
    if not evolucion or paso < 0:
        return None
    acumulado: dict[str, int] = {}
    for participante in evolucion.get("participantes", []):
        if not isinstance(participante, dict):
            continue
        serie = participante.get("serie", [])
        nombre = participante.get("nombre")
        if nombre and paso < len(serie):
            acumulado[nombre] = int(serie[paso])
    if not acumulado:
        return None
    return posiciones_por_puntos(acumulado, list(acumulado.keys()))


def _posiciones_previas_evolucion(
    evolucion: dict[str, Any] | None,
    partidos_jugados: int,
) -> dict[str, int] | None:
    if not evolucion or partidos_jugados < 1:
        return None
    return _posiciones_en_paso(evolucion, partidos_jugados - 1)


def _posiciones_actuales_evolucion(
    evolucion: dict[str, Any] | None,
    partidos_jugados: int,
) -> dict[str, int] | None:
    """Posiciones tras el último partido jugado (misma lógica de empates que la evolución)."""
    if not evolucion or partidos_jugados < 1:
        return None
    return _posiciones_en_paso(evolucion, partidos_jugados)


def _posiciones(clasificacion: list[dict[str, Any]]) -> dict[str, int]:
    return {fila["nombre"]: int(fila["posicion"]) for fila in clasificacion}


def _lideres(posiciones: dict[str, int]) -> list[str]:
    if not posiciones:
        return []
    mejor = min(posiciones.values())
    return sorted(n for n, p in posiciones.items() if p == mejor)


def _humanos(clasificacion: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in clasificacion if not es_participante_virtual(f["nombre"])]


def _puntos_en_paso(evolucion: dict[str, Any] | None, paso: int) -> dict[str, int]:
    if not evolucion or paso < 0:
        return {}
    puntos: dict[str, int] = {}
    for participante in evolucion.get("participantes", []):
        if not isinstance(participante, dict):
            continue
        serie = participante.get("serie", [])
        nombre = participante.get("nombre")
        if nombre and paso < len(serie):
            puntos[nombre] = int(serie[paso])
    return puntos


def _rival_por_puntos_superados(
    jugador: str,
    evolucion: dict[str, Any] | None,
    paso_prev: int,
    paso_curr: int,
) -> str:
    """Quién tenía más puntos antes y ahora queda igual o por debajo (humano preferido)."""
    pts_prev = _puntos_en_paso(evolucion, paso_prev)
    pts_curr = _puntos_en_paso(evolucion, paso_curr)
    if jugador not in pts_prev or jugador not in pts_curr:
        return ""
    antes_j = pts_prev[jugador]
    ahora_j = pts_curr[jugador]
    superados: list[str] = []
    for nombre, pb in pts_prev.items():
        if nombre == jugador:
            continue
        if pb > antes_j and pts_curr.get(nombre, 0) <= ahora_j:
            superados.append(nombre)
    humanos = sorted(n for n in superados if not es_participante_virtual(n))
    if humanos:
        return humanos[0]
    return sorted(superados)[0] if superados else ""


def _rival_tras_movimiento(
    jugador: str,
    pos_prev: dict[str, int],
    pos_curr: dict[str, int],
    evolucion: dict[str, Any] | None = None,
    paso_prev: int | None = None,
    paso_curr: int | None = None,
) -> str:
    antes = pos_prev.get(jugador)
    if antes is None:
        return ""
    for nombre, pos in pos_curr.items():
        if pos == antes and nombre != jugador:
            return nombre
    ahora = pos_curr.get(jugador)
    if ahora is not None and ahora > 1:
        candidatos = sorted(
            n for n, p in pos_curr.items() if p == ahora - 1 and n != jugador
        )
        if candidatos:
            return candidatos[0]
    if evolucion is not None and paso_prev is not None and paso_curr is not None:
        return _rival_por_puntos_superados(jugador, evolucion, paso_prev, paso_curr)
    return ""


def _formato_partido(partido: dict[str, Any] | None) -> str | None:
    if not partido:
        return None
    local = partido.get("local", "")
    visitante = partido.get("visitante", "")
    marcador = partido.get("marcador")
    if marcador:
        return f"{local} {marcador} {visitante}"
    if local and visitante:
        return f"{local} – {visitante}"
    return None


def _contar_partidos_jugados(partidos: list[dict], resultados: list[Any]) -> int:
    total = 0
    for i, partido in enumerate(partidos):
        if i < len(resultados) and partido_tiene_resultado(
            resultados[i], partido.get("fase", "grupos")
        ):
            total += 1
    return total


def _indice_ultimo_partido(partidos: list[dict], resultados: list[Any]) -> int | None:
    ultimo: int | None = None
    for i, partido in enumerate(partidos):
        if i < len(resultados) and partido_tiene_resultado(
            resultados[i], partido.get("fase", "grupos")
        ):
            ultimo = i
    return ultimo


def _racha_participante(
    nombre: str,
    participantes: dict[str, Any],
    partidos: list[dict],
    resultados: list[Any],
    acierto: bool,
) -> int:
    pronosticos = participantes.get(nombre, {}).get("pronosticos", [])
    racha = 0
    for i in range(len(partidos) - 1, -1, -1):
        if i >= len(resultados) or i >= len(pronosticos):
            break
        fase = partidos[i].get("fase", "grupos")
        if not partido_tiene_resultado(resultados[i], fase):
            continue
        acerto = apuesta_completa(pronosticos[i], resultados[i], fase)
        if acerto == acierto:
            racha += 1
        else:
            break
    return racha


def _eventos_ultimo_partido(
    evolucion: dict[str, Any] | None,
    match_id: int | None,
) -> list[dict[str, Any]]:
    if not evolucion or match_id is None:
        return []
    return [
        e
        for e in evolucion.get("eventos", [])
        if isinstance(e, dict) and e.get("match_id") == match_id
    ]


def _prob_campeon(proyeccion: dict[str, Any] | None, nombre: str) -> float:
    if not proyeccion:
        return 0.0
    for fila in proyeccion.get("campeon") or []:
        if fila.get("nombre") == nombre:
            return float(fila.get("probabilidad") or 0)
    return 0.0


def _detectar_eventos(
    clasificacion: list[dict[str, Any]],
    pos_prev: dict[str, int] | None,
    pos_curr_mov: dict[str, int] | None,
    evolucion: dict[str, Any] | None,
    proyeccion: dict[str, Any] | None,
    participantes: dict[str, Any],
    partidos: list[dict],
    resultados: list[Any],
    ultimo_idx: int | None,
    partidos_jugados: int = 0,
) -> list[Candidato]:
    candidatos: list[Candidato] = []
    pos_curr = _posiciones(clasificacion)
    pos_mov = pos_curr_mov or pos_curr
    humanos = _humanos(clasificacion)
    pos_h_prev = (
        {n: pos_prev[n] for n in pos_prev if not es_participante_virtual(n)}
        if pos_prev
        else {}
    )
    pos_h_curr = {n: pos_mov[n] for n in pos_mov if not es_participante_virtual(n)}

    ultimo_partido = None
    match_id = None
    if ultimo_idx is not None and ultimo_idx < len(partidos):
        ultimo_partido = partidos[ultimo_idx]
        match_id = ultimo_partido.get("id")
        if proyeccion and proyeccion.get("ultimo_movimiento", {}).get("ultimo_partido"):
            ultimo_partido = proyeccion["ultimo_movimiento"]["ultimo_partido"]
            match_id = ultimo_partido.get("id")

    partido_txt = _formato_partido(ultimo_partido) or ""
    _lider_global = _lideres(pos_curr)[0] if _lideres(pos_curr) else ""
    _lider_humano = humanos[0]["nombre"] if humanos else ""
    vars_base: dict[str, str] = {
        "PARTIDO": partido_txt or "el último partido",
        "MARCADOR": str((ultimo_partido or {}).get("marcador", "")),
        "LIDER": _lider_global,
        "LIDER_HUMANO": _lider_humano,
    }

    if pos_prev:
        lider_prev = _lideres(pos_prev)
        lider_curr = _lideres(pos_curr)
        if lider_prev != lider_curr and len(lider_curr) == 1:
            nuevo = lider_curr[0]
            anterior = lider_prev[0] if len(lider_prev) == 1 else lider_prev[0]
            v = {**vars_base, "NUEVO_LIDER": nuevo, "ANTERIOR_LIDER": anterior, "LIDER": nuevo}
            if nuevo == "GPT":
                candidatos.append(Candidato("GPT_LIDER", {**v, "IA": "GPT"}, 100, incluir_partido=True))
            elif nuevo == "GEMINI":
                candidatos.append(Candidato("GEMINI_LIDER", {**v, "IA": "GEMINI"}, 100, incluir_partido=True))
            elif not es_participante_virtual(nuevo):
                candidatos.append(Candidato("CAMBIO_LIDER", v, 100, incluir_partido=True))
        elif len(lider_curr) > 1:
            candidatos.append(
                Candidato("EMPATE_LIDER", {**vars_base, "JUGADOR": lider_curr[0]}, 10, incluir_partido=True)
            )

    if pos_prev:
        top3_prev = {n for n, p in pos_h_prev.items() if p <= 3}
        top3_curr = {n for n, p in pos_h_curr.items() if p <= 3}
        for n in top3_curr - top3_prev:
            candidatos.append(Candidato("ENTRA_TOP3", {**vars_base, "JUGADOR": n}, 50, incluir_partido=True))
        for n in top3_prev - top3_curr:
            candidatos.append(Candidato("SALE_TOP3", {**vars_base, "JUGADOR": n}, 50, incluir_partido=True))

    if pos_prev:
        movimientos: list[tuple[str, int]] = []
        for fila in humanos:
            n = fila["nombre"]
            if n not in pos_prev:
                continue
            delta = pos_prev[n] - pos_mov[n]
            if delta != 0:
                movimientos.append((n, delta))
        movimientos.sort(key=lambda t: abs(t[1]), reverse=True)

        for jugador, delta in movimientos:
            paso_prev = partidos_jugados - 1 if partidos_jugados > 0 else 0
            paso_curr = partidos_jugados
            rival = _rival_tras_movimiento(
                jugador, pos_prev, pos_mov, evolucion, paso_prev, paso_curr
            )
            v = {**vars_base, "JUGADOR": jugador, "RIVAL": rival}
            if delta >= 4:
                v["POSICIONES_GANADAS"] = str(delta)
                candidatos.append(Candidato("SUBIDA_4_MAS", v, delta, incluir_partido=True))
            elif delta >= 2:
                v["POSICIONES_GANADAS"] = str(delta)
                candidatos.append(Candidato("SUBIDA_2_3_POSICIONES", v, delta, incluir_partido=True))
            elif delta == 1:
                candidatos.append(Candidato("SUBIDA_1_POSICION", v, 1, incluir_partido=True))
            elif delta <= -4:
                v["POSICIONES_PERDIDAS"] = str(-delta)
                candidatos.append(Candidato("HUNDIMIENTO_HISTORICO", v, -delta, incluir_partido=True))
                candidatos.append(Candidato("BAJADA_4_MAS", v, -delta, incluir_partido=True))
            elif delta <= -2:
                v["POSICIONES_PERDIDAS"] = str(-delta)
                candidatos.append(Candidato("BAJADA_2_3_POSICIONES", v, -delta, incluir_partido=True))
            elif delta == -1:
                candidatos.append(Candidato("BAJADA_1_POSICION", v, 1, incluir_partido=True))

    for evento in _eventos_ultimo_partido(evolucion, match_id):
        tipo = evento.get("tipo")
        prot = evento.get("protagonista", "")
        if tipo == "mayor_remontada" and prot and not es_participante_virtual(prot):
            posiciones = evento.get("datos", {}).get("posiciones", 3)
            candidatos.append(
                Candidato(
                    "REMONTADA_HISTORICA",
                    {**vars_base, "JUGADOR": prot, "POSICIONES_GANADAS": str(posiciones)},
                    int(posiciones),
                    incluir_partido=True,
                )
            )

    for fila in humanos:
        n = fila["nombre"]
        racha_ok = _racha_participante(n, participantes, partidos, resultados, True)
        if racha_ok >= RACHA_MINIMA:
            candidatos.append(
                Candidato(
                    "RACHA_ACIERTOS",
                    {**vars_base, "JUGADOR": n, "RACHA": str(racha_ok)},
                    racha_ok,
                    incluir_partido=True,
                )
            )
        racha_ko = _racha_participante(n, participantes, partidos, resultados, False)
        if racha_ko >= RACHA_MINIMA:
            candidatos.append(
                Candidato(
                    "RACHA_FALLOS",
                    {**vars_base, "JUGADOR": n, "RACHA": str(racha_ko)},
                    racha_ko,
                    incluir_partido=True,
                )
            )

    if ultimo_idx is not None and ultimo_idx < len(partidos):
        fase = partidos[ultimo_idx].get("fase", "grupos")
        acertantes: list[str] = []
        for fila in humanos:
            n = fila["nombre"]
            pron = participantes.get(n, {}).get("pronosticos", [])
            if ultimo_idx < len(pron) and apuesta_completa(pron[ultimo_idx], resultados[ultimo_idx], fase):
                acertantes.append(n)
        if len(acertantes) == 0 and humanos:
            candidatos.append(Candidato("NADIE_ACIERTA", vars_base, 30, incluir_partido=True))
        elif len(acertantes) == 1:
            candidatos.append(
                Candidato(
                    "SOLO_UNO_ACIERTA",
                    {**vars_base, "JUGADOR": acertantes[0]},
                    40,
                    incluir_partido=True,
                )
            )

    if proyeccion:
        mov = proyeccion.get("ultimo_movimiento") or proyeccion.get("movimiento") or {}
        for rol, clave in (("beneficiado", "beneficiado"), ("perjudicado", "perjudicado")):
            jug = mov.get(clave)
            if (
                isinstance(jug, dict)
                and jug.get("nombre")
                and not es_participante_virtual(jug["nombre"])
                and abs(float(jug.get("delta") or 0)) >= 0.5
            ):
                delta_sim = float(jug["delta"])
                prob_sim = float(jug.get("probabilidad") or 0)
                tendencia = "sube" if delta_sim > 0 else "baja"
                candidatos.append(
                    Candidato(
                        "CAMBIO_SIMULACIONES",
                        {
                            **vars_base,
                            "JUGADOR": jug["nombre"],
                            "FAVORITO": jug["nombre"],
                            "TENDENCIA": tendencia,
                            "PROB_SIM": f"{prob_sim:.1f}",
                            "DELTA_SIM": f"{abs(delta_sim):.1f}",
                        },
                        int(abs(delta_sim) * 10),
                        incluir_partido=True,
                    )
                )

        campeon = proyeccion.get("campeon") or []
        favorito_sim = next((c for c in campeon if not c.get("es_ia")), None)
        if favorito_sim:
            fav_nombre = favorito_sim["nombre"]
            lider_puntos = clasificacion[0]["nombre"] if clasificacion else ""
            lider_humano = humanos[0]["nombre"] if humanos else ""
            v_fav = {
                **vars_base,
                "FAVORITO": fav_nombre,
                "LIDER": lider_puntos,
                "LIDER_HUMANO": lider_humano,
                "JUGADOR": fav_nombre,
            }
            if fav_nombre == lider_humano:
                candidatos.append(
                    Candidato(
                        "LIDER_HUMANO",
                        v_fav,
                        int(favorito_sim.get("probabilidad", 0)),
                        jugador=fav_nombre,
                    )
                )
            else:
                candidatos.append(
                    Candidato(
                        "FAVORITO_SIMULADOR",
                        v_fav,
                        int(favorito_sim.get("probabilidad", 0)),
                        jugador=fav_nombre,
                    )
                )
            if (
                fav_nombre != lider_puntos
                and fav_nombre != lider_humano
                and not es_participante_virtual(fav_nombre)
            ):
                candidatos.append(
                    Candidato("FAVORITO_NO_LIDER", v_fav, 20, jugador=fav_nombre)
                )

        indice = proyeccion.get("indice_emocion") or {}
        nivel = indice.get("nivel", "")
        if nivel in ("muy_abierto", "abierto"):
            candidatos.append(Candidato("MUNDIAL_ABIERTO", vars_base, 5))
        elif nivel == "decidido":
            fav = favorito_sim["nombre"] if favorito_sim else vars_base["LIDER"]
            candidatos.append(Candidato("MUNDIAL_DECIDIDO", {**vars_base, "FAVORITO": fav}, 30))

    if clasificacion:
        ultimo_nombre = clasificacion[-1]["nombre"]
        lider_nombre = clasificacion[0]["nombre"]
        if lider_nombre == "GPT":
            candidatos.append(Candidato("GPT_LIDER", {**vars_base, "IA": "GPT", "LIDER": "GPT"}, 80))
        elif lider_nombre == "GEMINI":
            candidatos.append(Candidato("GEMINI_LIDER", {**vars_base, "IA": "GEMINI", "LIDER": "GEMINI"}, 80))
        if ultimo_nombre == "GPT":
            candidatos.append(Candidato("GPT_ULTIMO", {**vars_base, "IA": "GPT", "ULTIMO": "GPT"}, 50))
        elif ultimo_nombre == "GEMINI":
            candidatos.append(Candidato("GEMINI_ULTIMO", {**vars_base, "IA": "GEMINI", "ULTIMO": "GEMINI"}, 50))
        if humanos:
            ultimo_h = humanos[-1]["nombre"]
            candidatos.append(
                Candidato(
                    "ULTIMO_CLASIFICADO",
                    {**vars_base, "ULTIMO": ultimo_h},
                    5,
                    jugador=ultimo_h,
                )
            )

    if pos_prev and _lideres(pos_prev) == _lideres(pos_curr) and len(_lideres(pos_curr)) == 1:
        lider = _lideres(pos_curr)[0]
        candidatos.append(
            Candidato("LIDER_RESISTE", {**vars_base, "LIDER": lider}, 1, jugador=lider)
        )

    return candidatos


def _categoria_individual(
    nombre: str,
    ctx: ContextoNoticias,
    pos_prev: dict[str, int] | None,
    pos_mov: dict[str, int] | None,
    proyeccion: dict[str, Any] | None,
    participantes: dict[str, Any],
    partidos: list[dict],
    resultados: list[Any],
    vars_base: dict[str, str],
) -> Candidato:
    posiciones_ref = pos_mov or ctx.posiciones
    pos = posiciones_ref.get(nombre, ctx.posiciones.get(nombre, 99))
    delta = (pos_prev.get(nombre, pos) - pos) if pos_prev else 0
    v = {
        **vars_base,
        "JUGADOR": nombre,
        "LIDER": ctx.lider_global,
        "LIDER_HUMANO": ctx.lider_humano,
        "FAVORITO": nombre,
    }

    if nombre == "GPT":
        cat = (
            "GPT_LIDER"
            if pos == 1
            else ("GPT_ULTIMO" if pos == max(ctx.posiciones.values(), default=pos) else "GPT_LIDER")
        )
        return Candidato(cat, {**v, "IA": "GPT"}, jugador=nombre)
    if nombre == "GEMINI":
        max_pos = max(ctx.posiciones.values(), default=pos)
        cat = (
            "GEMINI_LIDER" if pos == 1
            else "GEMINI_ULTIMO" if pos == max_pos
            else "GEMINI_LIDER"  # posición intermedia: comentario genérico IA
        )
        return Candidato(cat, {**v, "IA": "GEMINI"}, jugador=nombre)

    if delta >= 4:
        v["POSICIONES_GANADAS"] = str(delta)
        v["RIVAL"] = _rival_inmediato_superior(nombre, ctx)
        return Candidato("SUBIDA_4_MAS", v, delta, jugador=nombre, incluir_partido=True)
    if delta >= 2:
        v["POSICIONES_GANADAS"] = str(delta)
        v["RIVAL"] = _rival_inmediato_superior(nombre, ctx)
        return Candidato("SUBIDA_2_3_POSICIONES", v, delta, jugador=nombre, incluir_partido=True)
    if delta == 1:
        v["RIVAL"] = _rival_inmediato_superior(nombre, ctx)
        return Candidato("SUBIDA_1_POSICION", v, jugador=nombre, incluir_partido=True)
    if delta <= -4:
        v["POSICIONES_PERDIDAS"] = str(-delta)
        return Candidato("BAJADA_4_MAS", v, -delta, jugador=nombre, incluir_partido=True)
    if delta <= -2:
        v["POSICIONES_PERDIDAS"] = str(-delta)
        return Candidato("BAJADA_2_3_POSICIONES", v, -delta, jugador=nombre, incluir_partido=True)
    if delta == -1:
        v["RIVAL"] = _rival_inmediato_superior(nombre, ctx)
        return Candidato("BAJADA_1_POSICION", v, jugador=nombre, incluir_partido=True)

    racha_ok = _racha_participante(nombre, participantes, partidos, resultados, True)
    if racha_ok >= RACHA_INDIVIDUAL:
        return Candidato(
            "RACHA_ACIERTOS",
            {**v, "RACHA": str(racha_ok)},
            racha_ok,
            jugador=nombre,
            incluir_partido=True,
        )
    racha_ko = _racha_participante(nombre, participantes, partidos, resultados, False)
    if racha_ko >= RACHA_INDIVIDUAL:
        return Candidato(
            "RACHA_FALLOS",
            {**v, "RACHA": str(racha_ko)},
            racha_ko,
            jugador=nombre,
            incluir_partido=True,
        )

    if nombre == ctx.lider_global:
        return Candidato("LIDER_RESISTE", {**v, "LIDER": nombre}, jugador=nombre)

    if nombre == ctx.lider_humano:
        return Candidato("LIDER_HUMANO", v, jugador=nombre)

    if nombre == ctx.favorito_sim_humano and nombre != ctx.lider_humano:
        return Candidato(
            "FAVORITO_SIMULADOR",
            {**v, "FAVORITO": nombre},
            jugador=nombre,
        )

    if nombre == ctx.ultimo_h:
        return Candidato("ULTIMO_CLASIFICADO", {**v, "ULTIMO": nombre}, jugador=nombre)

    if pos <= 3:
        v["RIVAL"] = ctx.lider_humano
        return Candidato("PODIO_HUMANO", v, jugador=nombre)

    # Usar posición humana para distinguir zona media de zona baja
    n_humanos = len(ctx.pos_humana)
    pos_h = ctx.pos_humana.get(nombre, n_humanos)
    v["RIVAL"] = _rival_inmediato_superior(nombre, ctx)

    # Zona media: primera mitad sin contar el podio (posición 4 a mitad+1 entre humanos)
    # Zona baja: segunda mitad (pero no último, que ya lo tiene ULTIMO_CLASIFICADO)
    punto_corte = max(4, (n_humanos + 1) // 2 + 1)  # ejemplo: 7 humanos → corte en 5
    if pos_h < punto_corte:
        return Candidato("ZONA_MEDIA", v, jugador=nombre)
    return Candidato("ZONA_BAJA", v, jugador=nombre)


def _sustituir(texto: str, variables: dict[str, str]) -> str:
    resultado = texto
    for clave, valor in variables.items():
        resultado = resultado.replace(f"{{{clave}}}", valor)
    return resultado


def _split_titular(texto: str) -> tuple[str, str | None]:
    texto = texto.strip()
    match = re.match(r"^(.+?[.!?])(\s+)(.+)$", texto, re.DOTALL)
    if match and len(match.group(1)) <= 120:
        return match.group(1).strip(), match.group(3).strip()
    if len(texto) > 90 and ". " in texto:
        idx = texto.index(". ")
        return texto[: idx + 1].strip(), texto[idx + 2 :].strip()
    return texto, None


def _parse_declaraciones(texto: str) -> tuple[str, str | None]:
    match = re.search(r"\s—\s*(.+?)\s*$", texto)
    if match:
        cuerpo = texto[: match.start()].strip()
        atrib = match.group(1).strip()
        if cuerpo.startswith('"') and cuerpo.endswith('"'):
            cuerpo = cuerpo[1:-1]
        return cuerpo, atrib
    return texto, None


def _capitalizar_titulo(texto: str) -> str:
    if not texto:
        return texto
    if texto.isupper() and len(texto) > 4:
        return texto
    return texto[0].upper() + texto[1:] if len(texto) == 1 else texto[0].upper() + texto[1:]


def _seleccionar_plantilla(
    frases: dict[str, list[dict[str, str]]],
    categoria: str,
    historial: dict[str, int],
    usadas_en_lote: set[str],
    rng: random.Random,
    candidato: Candidato | None = None,
) -> tuple[dict[str, str], str] | None:
    pool = frases.get(categoria)
    if not pool:
        return None

    candidatas: list[tuple[int, int, dict[str, str], str]] = []
    for idx, plantilla in enumerate(pool):
        frase_id = _frase_id(categoria, plantilla, idx)
        texto = str(plantilla.get("texto", ""))
        if candidato and not _plantilla_coherente(categoria, texto, candidato):
            continue
        elif not _plantilla_valida(categoria, texto):
            continue
        if frase_id in usadas_en_lote:
            continue
        candidatas.append((historial.get(frase_id, 0), idx, plantilla, frase_id))

    if not candidatas:
        for idx, plantilla in enumerate(pool):
            frase_id = _frase_id(categoria, plantilla, idx)
            texto = str(plantilla.get("texto", ""))
            if candidato and not _plantilla_coherente(categoria, texto, candidato):
                continue
            candidatas.append((historial.get(frase_id, 0), idx, plantilla, frase_id))

    candidatas.sort(key=lambda t: (t[0], t[1]))
    min_uso = candidatas[0][0]
    mejores = [c for c in candidatas if c[0] == min_uso]
    _, _, plantilla, frase_id = rng.choice(mejores)
    return plantilla, frase_id


def _formatear_item(
    candidato: Candidato,
    plantilla: dict[str, str],
    frase_id: str,
    partido_global: str | None,
) -> dict[str, Any]:
    tipo = str(plantilla.get("tipo", "EDITORIAL")).upper()
    texto_full = _sustituir(str(plantilla.get("texto", "")), candidato.variables)

    if tipo == "DECLARACIONES":
        titulo, atrib = _parse_declaraciones(texto_full)
        cuerpo = f"— {atrib}" if atrib else None
    else:
        titulo, cuerpo = _split_titular(texto_full)

    partido = partido_global if candidato.incluir_partido and partido_global else None

    return {
        "id": frase_id,
        "tipo": tipo,
        "categoria": candidato.categoria,
        "frase_id": frase_id,
        "jugador": candidato.jugador,
        "titulo": _capitalizar_titulo(titulo),
        "texto": cuerpo,
        "partido": partido,
        "prioridad": candidato.prioridad + min(candidato.peso, 10),
        "etiqueta": TIPO_ETIQUETA.get(tipo, tipo.replace("_", " ")),
    }


def _deduplicar_candidatos(candidatos: list[Candidato]) -> list[Candidato]:
    """Conserva el candidato de mayor prioridad por (jugador, categoría)."""
    mejor: dict[tuple[str | None, str], Candidato] = {}
    for c in candidatos:
        clave = (c.jugador, c.categoria)
        if clave not in mejor or (c.prioridad, c.peso) > (mejor[clave].prioridad, mejor[clave].peso):
            mejor[clave] = c
    return list(mejor.values())


def _limitar_una_por_jugador(candidatos: list[Candidato]) -> list[Candidato]:
    """Como máximo una noticia por jugador (la de mayor prioridad)."""
    ordenados = sorted(candidatos, key=lambda c: (c.prioridad, c.peso), reverse=True)
    vistos: set[str] = set()
    globales: list[Candidato] = []
    filtrados: list[Candidato] = []
    for candidato in ordenados:
        if not candidato.jugador:
            globales.append(candidato)
            continue
        if candidato.jugador in vistos:
            continue
        vistos.add(candidato.jugador)
        filtrados.append(candidato)
    resultado = filtrados
    if globales:
        resultado = [globales[0]] + filtrados
        resultado.sort(key=lambda c: (c.prioridad, c.peso), reverse=True)
    return resultado


def _jugadores_cubiertos(candidatos: list[Candidato]) -> set[str]:
    return {c.jugador for c in candidatos if c.jugador}


def generar_noticias(
    clasificacion: list[dict[str, Any]],
    evolucion: dict[str, Any] | None,
    proyeccion: dict[str, Any] | None,
    participantes: dict[str, Any],
    partidos: list[dict],
    resultados: list[Any],
    frases: dict[str, list[dict[str, str]]],
    estado_previo: dict[str, Any] | None,
    rng: random.Random | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Genera el paquete de noticias ordenadas y el nuevo estado de humor."""
    rng = rng or random.Random()
    partidos_jugados = _contar_partidos_jugados(partidos, resultados)
    ultimo_idx = _indice_ultimo_partido(partidos, resultados)

    pos_prev_raw = (estado_previo or {}).get("posiciones")
    pos_prev_estado = pos_prev_raw if isinstance(pos_prev_raw, dict) else None
    pos_prev_evolucion = _posiciones_previas_evolucion(evolucion, partidos_jugados)
    pos_curr_evolucion = _posiciones_actuales_evolucion(evolucion, partidos_jugados)
    # Para detectar movimientos del último partido, priorizar evolución sobre estado
    pos_prev = pos_prev_evolucion or pos_prev_estado
    pos_mov = pos_curr_evolucion or _posiciones(clasificacion)

    historial: dict[str, int] = {}
    if estado_previo and isinstance(estado_previo.get("frases_usadas"), dict):
        historial = {k: int(v) for k, v in estado_previo["frases_usadas"].items()}

    pos_curr = _posiciones(clasificacion)
    humanos = _humanos(clasificacion)
    ctx = _construir_contexto(clasificacion, proyeccion)

    ultimo_partido = None
    if proyeccion and proyeccion.get("ultimo_movimiento", {}).get("ultimo_partido"):
        ultimo_partido = proyeccion["ultimo_movimiento"]["ultimo_partido"]
    elif ultimo_idx is not None and ultimo_idx < len(partidos):
        ultimo_partido = partidos[ultimo_idx]
    partido_txt = _formato_partido(ultimo_partido)

    vars_base: dict[str, str] = {
        "PARTIDO": partido_txt or "el último partido",
        "MARCADOR": str((ultimo_partido or {}).get("marcador", "")),
        "LIDER": ctx.lider_global,
        "LIDER_HUMANO": ctx.lider_humano,
        "FAVORITO": ctx.favorito_sim_humano or ctx.lider_humano,
    }

    eventos = _detectar_eventos(
        clasificacion,
        pos_prev,
        pos_mov,
        evolucion,
        proyeccion,
        participantes,
        partidos,
        resultados,
        ultimo_idx,
        partidos_jugados,
    )

    cubiertos = _jugadores_cubiertos(eventos)
    for fila in clasificacion:
        nombre = fila["nombre"]
        if nombre in cubiertos:
            continue
        # Las IAs solo necesitan cobertura individual si son líderes o últimas
        if es_participante_virtual(nombre):
            pos = ctx.posiciones.get(nombre, 99)
            max_pos = max(ctx.posiciones.values(), default=1)
            if pos != 1 and pos != max_pos:
                continue
        eventos.append(
            _categoria_individual(
                nombre,
                ctx,
                pos_prev_evolucion or pos_prev_estado,
                pos_mov,
                proyeccion,
                participantes,
                partidos,
                resultados,
                vars_base,
            )
        )

    eventos = [c for c in eventos if _candidato_coherente(c, ctx)]
    eventos = _suprimir_contradicciones(eventos, ctx)
    eventos = _deduplicar_candidatos(eventos)
    eventos.sort(key=lambda c: (c.prioridad, c.peso), reverse=True)
    eventos = _limitar_una_por_jugador(eventos)

    usadas_en_lote: set[str] = set()
    noticias: list[dict[str, Any]] = []
    nuevas_frases: dict[str, int] = dict(historial)

    for candidato in eventos:
        seleccion = _seleccionar_plantilla(
            frases, candidato.categoria, historial, usadas_en_lote, rng, candidato
        )
        if not seleccion:
            alternativas = {
                "CAMBIO_SIMULACIONES": "FAVORITO_SIMULADOR",
                "PODIO_HUMANO": "ZONA_MEDIA",
                "LIDER_HUMANO": "PODIO_HUMANO",
                "ZONA_BAJA": "ZONA_MEDIA",
            }
            cat_alt = alternativas.get(candidato.categoria, candidato.categoria)
            seleccion = _seleccionar_plantilla(
                frases, cat_alt, historial, usadas_en_lote, rng, candidato
            )
        if not seleccion:
            for cat_alt in ("ZONA_MEDIA", "LIDER_RESISTE", "MUNDIAL_ABIERTO", "ULTIMO_CLASIFICADO"):
                seleccion = _seleccionar_plantilla(
                    frases, cat_alt, historial, usadas_en_lote, rng, candidato
                )
                if seleccion:
                    break
        if not seleccion:
            continue

        plantilla, frase_id = seleccion
        usadas_en_lote.add(frase_id)
        nuevas_frases[frase_id] = partidos_jugados
        noticias.append(_formatear_item(candidato, plantilla, frase_id, partido_txt))

    generado = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )

    paquete = {
        "generado": generado,
        "partidos_jugados": partidos_jugados,
        "noticias": noticias,
    }

    nuevo_estado = {
        "partidos_jugados": partidos_jugados,
        "posiciones": pos_curr,
        "lider": _lideres(pos_curr)[0] if clasificacion else None,
        "frases_usadas": nuevas_frases,
        "actualizado": generado,
    }

    return paquete, nuevo_estado


# Alias retrocompatible
generar_noticia = generar_noticias
