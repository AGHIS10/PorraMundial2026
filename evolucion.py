"""Construye la narrativa de la competición (evolución de puntos acumulados).

Lógica pura, sin I/O: recibe los datos ya cargados y devuelve una estructura
serializable que el frontend representa directamente. Toda la detección de
acontecimientos relevantes se hace aquí, en Python.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

PARTICIPANTES_IA = frozenset({"GPT", "GEMINI"})

# Colores fijos para todo el torneo. Asignados por nombre para que NUNCA cambien
# independientemente de la clasificación. Humanos con tonos vivos y distintos;
# las IA con tonos neutros (van ocultas por defecto).
COLORES_FIJOS: dict[str, str] = {
    "AGUSTIN": "#2ee6d6",
    "SERGIO": "#f5c518",
    "GABRIEL": "#9b8cff",
    "JORGE": "#ef6f6c",
    "MARIO": "#5aa9ff",
    "PEDRO": "#58d68d",
    "CRISTIAN": "#f0883e",
    "GPT": "#8c99b0",
    "GEMINI": "#c0b3e0",
}

# Paleta de reserva determinista para participantes no previstos.
PALETA_RESERVA: tuple[str, ...] = (
    "#e879a6", "#4dd0c1", "#b6d957", "#ffa94d", "#74c0fc",
    "#da77f2", "#63e6be", "#ffd43b", "#ff8787", "#a9e34b",
)


def es_ia(nombre: str) -> bool:
    """Indica si un participante es una IA (oculta por defecto)."""
    return nombre.strip().upper() in PARTICIPANTES_IA


def inicial(nombre: str) -> str:
    """Misma inicial circular que usa la clasificación (2 letras)."""
    partes = [parte for parte in nombre.split() if parte]
    letras = "".join(parte[0] for parte in partes)[:2]
    return letras.upper() if letras else nombre[:2].upper()


def color_para(nombre: str, indice_reserva: int) -> str:
    """Devuelve el color fijo del participante."""
    clave = nombre.strip().upper()
    if clave in COLORES_FIJOS:
        return COLORES_FIJOS[clave]
    return PALETA_RESERVA[indice_reserva % len(PALETA_RESERVA)]


def _instante(partido: dict[str, Any]) -> datetime:
    """Convierte fecha + hora del partido en un datetime ordenable."""
    fecha = partido.get("fecha") or "9999-12-31"
    hora = partido.get("hora") or "00:00"
    try:
        return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.max


def _marcador_str(marcador: Any) -> str | None:
    """Convierte {home, away} en 'h-a'."""
    if not isinstance(marcador, dict):
        return None
    home = marcador.get("home")
    away = marcador.get("away")
    if home is None or away is None:
        return None
    return f"{home}-{away}"


def _posiciones(acumulado: dict[str, int], nombres: list[str]) -> dict[str, int]:
    """Asigna posiciones con empates compartidos (1,1,3,…) entre los nombres dados."""
    ordenados = sorted(nombres, key=lambda n: -acumulado[n])
    posiciones: dict[str, int] = {}
    posicion_actual = 0
    puntos_previos: int | None = None
    for indice, nombre in enumerate(ordenados, start=1):
        puntos = acumulado[nombre]
        if puntos != puntos_previos:
            posicion_actual = indice
            puntos_previos = puntos
        posiciones[nombre] = posicion_actual
    return posiciones


def _orden_partidos_jugados(
    partidos: list[dict[str, Any]],
    resultados: list[Any],
) -> list[int]:
    """Índices de partidos ya disputados, en orden cronológico real."""
    jugados = [
        i for i, partido in enumerate(partidos)
        if i < len(resultados) and resultados[i] not in (None, "")
    ]
    jugados.sort(key=lambda i: (_instante(partidos[i]), partidos[i].get("id", i)))
    return jugados


def construir_evolucion(
    partidos: list[dict[str, Any]],
    resultados: list[Any],
    marcadores: list[Any],
    participantes: list[dict[str, Any]],
    generado_iso: str,
) -> dict[str, Any]:
    """Genera la estructura completa de la evolución del torneo."""
    nombres = [p["nombre"] for p in participantes]
    nombres_humanos = [n for n in nombres if not es_ia(n)]
    pronos = {p["nombre"]: p.get("pronosticos", []) for p in participantes}

    orden = _orden_partidos_jugados(partidos, resultados)

    meta_participantes: list[dict[str, Any]] = []
    indice_reserva = 0
    for nombre in nombres:
        meta_participantes.append({
            "nombre": nombre,
            "inicial": inicial(nombre),
            "color": color_para(nombre, indice_reserva),
            "es_ia": es_ia(nombre),
        })
        if nombre.strip().upper() not in COLORES_FIJOS:
            indice_reserva += 1

    acumulado = {n: 0 for n in nombres}
    series = {n: [0] for n in nombres}
    detalle = {n: [] for n in nombres}
    snapshots: list[dict[str, dict[str, int]]] = []

    partidos_serie: list[dict[str, Any]] = []

    for paso, idx in enumerate(orden, start=1):
        partido = partidos[idx]
        resultado = resultados[idx]
        peso = int(partido.get("peso", 1))
        marcador = _marcador_str(marcadores[idx] if idx < len(marcadores) else None)

        partidos_serie.append({
            "orden": paso,
            "match_id": partido.get("id", idx + 1),
            "fecha": partido.get("fecha"),
            "hora": partido.get("hora"),
            "fase": partido.get("fase"),
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "marcador": marcador,
            "resultado": resultado,
            "peso": peso,
        })

        for nombre in nombres:
            pron = pronos[nombre][idx] if idx < len(pronos[nombre]) else None
            acierto = pron is not None and pron == resultado
            obtenidos = peso if acierto else 0
            acumulado[nombre] += obtenidos
            series[nombre].append(acumulado[nombre])

        pos_global = _posiciones(acumulado, nombres)
        pos_humanos = _posiciones(acumulado, nombres_humanos)
        snapshots.append({
            "global": dict(pos_global),
            "humanos": dict(pos_humanos),
            "acumulado": dict(acumulado),
        })

        for nombre in nombres:
            pron = pronos[nombre][idx] if idx < len(pronos[nombre]) else None
            acierto = pron is not None and pron == resultado
            detalle[nombre].append({
                "orden": paso,
                "match_id": partido.get("id", idx + 1),
                "puntos": peso if acierto else 0,
                "acumulado": acumulado[nombre],
                "pronostico": pron,
                "acierto": acierto,
                "posicion": pos_global[nombre],
                "posicion_humanos": pos_humanos.get(nombre),
            })

    eventos = _detectar_eventos(
        partidos_serie, snapshots, nombres_humanos
    )

    fases = _segmentos_fase(partidos_serie)

    participantes_out = []
    for meta in meta_participantes:
        nombre = meta["nombre"]
        participantes_out.append({
            **meta,
            "puntos_final": acumulado[nombre],
            "serie": series[nombre],
            "detalle": detalle[nombre],
        })

    narrativa = _construir_narrativa(partidos_serie, snapshots, nombres, nombres_humanos)

    return {
        "generado": generado_iso,
        "total_partidos": len(partidos),
        "partidos_jugados": len(orden),
        "participantes": participantes_out,
        "partidos": partidos_serie,
        "fases": fases,
        "eventos": eventos,
        "narrativa": narrativa,
    }


def _segmentos_fase(partidos_serie: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tramos contiguos de cada fase a lo largo del eje X."""
    segmentos: list[dict[str, Any]] = []
    for p in partidos_serie:
        fase = p["fase"]
        if segmentos and segmentos[-1]["fase"] == fase:
            segmentos[-1]["hasta"] = p["orden"]
        else:
            segmentos.append({"fase": fase, "desde": p["orden"], "hasta": p["orden"]})
    return segmentos


def _fines_de_fase(partidos_serie: list[dict[str, Any]]) -> set[int]:
    """Órdenes del último partido disputado de cada fase."""
    fines: dict[str, int] = {}
    for p in partidos_serie:
        fines[p["fase"]] = p["orden"]
    return set(fines.values())


def _grupos_empate(acumulado: dict[str, int], nombres: list[str]) -> frozenset[frozenset[str]]:
    """Conjuntos de jugadores empatados a puntos (2 o más)."""
    por_puntos: dict[int, list[str]] = {}
    for nombre in nombres:
        por_puntos.setdefault(acumulado[nombre], []).append(nombre)
    return frozenset(
        frozenset(sorted(grupo))
        for grupo in por_puntos.values()
        if len(grupo) >= 2
    )


def _top3_jugadores(posiciones: dict[str, int], nombres: list[str]) -> frozenset[str]:
    """Jugadores en el Top 3."""
    return frozenset(n for n in nombres if posiciones[n] <= 3)


def _motivos_snapshot(
    paso: int,
    snap_prev: dict[str, Any] | None,
    snap_curr: dict[str, Any],
    nombres: list[str],
    clave_pos: str,
    fines_fase: set[int],
) -> list[str]:
    """Devuelve los motivos por los que este partido merece un snapshot."""
    motivos: list[str] = []

    if paso in fines_fase:
        motivos.append("fase_fin")

    if snap_prev is None:
        return ["inicio"] if not motivos else ["inicio", *motivos]

    pos_prev = {n: snap_prev[clave_pos][n] for n in nombres}
    pos_curr = {n: snap_curr[clave_pos][n] for n in nombres}
    acc_prev = {n: snap_prev["acumulado"][n] for n in nombres}
    acc_curr = {n: snap_curr["acumulado"][n] for n in nombres}

    if _lideres(pos_prev) != _lideres(pos_curr):
        motivos.append("cambio_lider")

    if any(pos_prev[n] != pos_curr[n] for n in nombres):
        motivos.append("cambio_posicion")

    if _grupos_empate(acc_prev, nombres) != _grupos_empate(acc_curr, nombres):
        motivos.append("cambio_empate")

    if _top3_jugadores(pos_prev, nombres) != _top3_jugadores(pos_curr, nombres):
        motivos.append("top3")

    return motivos


def _construir_narrativa_scope(
    partidos_serie: list[dict[str, Any]],
    snapshots: list[dict[str, dict[str, int]]],
    nombres: list[str],
    clave_pos: str,
) -> dict[str, Any]:
    """Timeline resumida: solo momentos donde cambia la competición."""
    if not snapshots:
        return {"columnas": [], "snapshots_total": 0, "partidos_total": 0}

    fines_fase = _fines_de_fase(partidos_serie)
    significativos: list[tuple[int, list[str]]] = []

    for paso in range(1, len(snapshots) + 1):
        snap_prev = snapshots[paso - 2] if paso >= 2 else None
        snap_curr = snapshots[paso - 1]
        motivos = _motivos_snapshot(
            paso, snap_prev, snap_curr, nombres, clave_pos, fines_fase
        )
        if motivos:
            significativos.append((paso, motivos))

    columnas: list[dict[str, Any]] = []
    prev_orden: int | None = None

    for paso, motivos in significativos:
        if prev_orden is not None and paso - prev_orden > 1:
            columnas.append({
                "tipo": "pausa",
                "partidos": paso - prev_orden - 1,
                "desde_orden": prev_orden + 1,
                "hasta_orden": paso - 1,
            })
        partido = partidos_serie[paso - 1]
        columnas.append({
            "tipo": "snapshot",
            "orden": paso,
            "motivos": motivos,
            "fase": partido["fase"],
            "match_id": partido["match_id"],
        })
        prev_orden = paso

    return {
        "columnas": columnas,
        "snapshots_total": len(significativos),
        "partidos_total": len(partidos_serie),
    }


def _construir_narrativa(
    partidos_serie: list[dict[str, Any]],
    snapshots: list[dict[str, dict[str, int]]],
    nombres: list[str],
    nombres_humanos: list[str],
) -> dict[str, Any]:
    """Genera la vista resumida para el bump chart (humanos + global con IA)."""
    return {
        "humanos": _construir_narrativa_scope(
            partidos_serie, snapshots, nombres_humanos, "humanos"
        ),
        "global": _construir_narrativa_scope(
            partidos_serie, snapshots, nombres, "global"
        ),
    }


def _lideres(posiciones: dict[str, int]) -> list[str]:
    """Nombres en posición 1 (puede haber empate)."""
    return sorted(n for n, pos in posiciones.items() if pos == 1)


def _join_nombres(nombres: list[str]) -> str:
    """Une nombres con comas y una 'y' final: 'A, B y C'."""
    if not nombres:
        return ""
    if len(nombres) == 1:
        return nombres[0]
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _detectar_eventos(
    partidos_serie: list[dict[str, Any]],
    snapshots: list[dict[str, dict[str, int]]],
    nombres_humanos: list[str],
) -> list[dict[str, Any]]:
    """Descubre automáticamente los acontecimientos narrativos del torneo.

    Solo sobre la competición real (humanos), que es la vista por defecto.
    """
    eventos: list[dict[str, Any]] = []
    if not snapshots:
        return eventos

    lider_previo: list[str] = []
    mejor_pos: dict[str, int] = {n: len(nombres_humanos) for n in nombres_humanos}
    peor_pos_tras_buena: dict[str, int] = {n: 1 for n in nombres_humanos}
    max_ventaja = {"valor": 0}
    max_remontada = {"valor": 0}

    def partido_ref(paso: int) -> dict[str, Any]:
        p = partidos_serie[paso - 1]
        marcador = p.get("marcador")
        equipos = f"{p['local']} vs {p['visitante']}"
        if marcador:
            h, a = marcador.split("-")
            equipos = f"{p['local']} {h} – {a} {p['visitante']}"
        return {
            "match_id": p["match_id"],
            "orden": paso,
            "fase": p["fase"],
            "equipos": equipos,
            "fecha": p["fecha"],
        }

    for paso, snap in enumerate(snapshots, start=1):
        pos_h = {n: snap["humanos"][n] for n in nombres_humanos}
        acc = {n: snap["acumulado"][n] for n in nombres_humanos}
        pos_prev = (
            {n: snapshots[paso - 2]["humanos"][n] for n in nombres_humanos}
            if paso >= 2 else {n: len(nombres_humanos) for n in nombres_humanos}
        )
        acc_prev = (
            {n: snapshots[paso - 2]["acumulado"][n] for n in nombres_humanos}
            if paso >= 2 else {n: 0 for n in nombres_humanos}
        )

        ref = partido_ref(paso)
        eventos_paso: list[dict[str, Any]] = []

        lideres_actuales = _lideres(pos_h)

        # ── Primer líder / cambio de líder / empate en cabeza ──
        if not lider_previo:
            if any(acc[n] > 0 for n in nombres_humanos):
                if len(lideres_actuales) == 1:
                    n = lideres_actuales[0]
                    eventos_paso.append({
                        "tipo": "primer_lider", "nivel": 1,
                        "titulo": "Primer líder del Mundial",
                        "protagonista": n,
                        "detalle": f"{n} se coloca en cabeza con {acc[n]} puntos.",
                        "datos": {"puntos": acc[n]},
                    })
                    lider_previo = lideres_actuales
        else:
            cambio = set(lideres_actuales) != set(lider_previo)
            era_unico = len(lider_previo) == 1
            if cambio and len(lideres_actuales) == 1:
                nuevo = lideres_actuales[0]
                if nuevo in lider_previo:
                    # Ya era colíder y se queda solo al frente.
                    otros = [n for n in lider_previo if n != nuevo]
                    eventos_paso.append({
                        "tipo": "cambio_lider", "nivel": 1,
                        "titulo": "Líder en solitario",
                        "protagonista": nuevo,
                        "detalle": f"{nuevo} se desmarca de {_join_nombres(otros)} y lidera en solitario.",
                        "datos": {"puntos": acc[nuevo], "supera_a": otros},
                    })
                else:
                    superados = [n for n in lider_previo if n != nuevo]
                    txt = (
                        f"{nuevo} supera a {_join_nombres(superados)} y pasa a liderar."
                        if superados else f"{nuevo} pasa a liderar en solitario."
                    )
                    eventos_paso.append({
                        "tipo": "cambio_lider", "nivel": 1,
                        "titulo": "Cambio de líder",
                        "protagonista": nuevo,
                        "detalle": txt,
                        "datos": {"puntos": acc[nuevo], "supera_a": superados},
                    })
                lider_previo = lideres_actuales
            elif cambio and len(lideres_actuales) >= 2 and era_unico:
                # Solo destacamos cuando se rompe un liderato en solitario.
                nuevos = [n for n in lideres_actuales if n not in lider_previo]
                lider_solo = lider_previo[0]
                eventos_paso.append({
                    "tipo": "empate_lider", "nivel": 2,
                    "titulo": "Empate en cabeza",
                    "protagonista": nuevos[0] if nuevos else lideres_actuales[0],
                    "detalle": (
                        f"{_join_nombres(nuevos)} "
                        f"{'alcanzan' if len(nuevos) > 1 else 'alcanza'} a {lider_solo} "
                        f"en lo más alto ({acc[lideres_actuales[0]]} pts)."
                        if nuevos else
                        f"{_join_nombres(lideres_actuales)} comparten liderato "
                        f"({acc[lideres_actuales[0]]} pts)."
                    ),
                    "datos": {"empatados": lideres_actuales, "puntos": acc[lideres_actuales[0]]},
                })
                lider_previo = lideres_actuales
            elif cambio:
                # Cambia la composición del empate sin un hecho destacable: actualizamos
                # el estado pero no generamos marcador para no saturar.
                lider_previo = lideres_actuales

        # ── Adelantamientos (agregados por protagonista) ──
        for n in nombres_humanos:
            superados = [
                m for m in nombres_humanos
                if m != n and acc_prev[n] < acc_prev[m] and acc[n] > acc[m]
            ]
            if not superados:
                continue
            ganadas = pos_prev[n] - pos_h[n]
            ya_evento_lider = any(
                e.get("protagonista") == n and e["tipo"] in ("cambio_lider", "primer_lider")
                for e in eventos_paso
            )
            if ya_evento_lider:
                continue
            if ganadas >= 2 or len(superados) >= 2:
                eventos_paso.append({
                    "tipo": "adelantamiento_multiple", "nivel": 2,
                    "titulo": "Gran remontada",
                    "protagonista": n,
                    "detalle": (
                        f"{n} gana {ganadas} posicion{'es' if ganadas != 1 else ''}. "
                        f"Pasa del {pos_prev[n]}.º al {pos_h[n]}.º puesto."
                        if ganadas >= 1 else
                        f"{n} supera a {_join_nombres(superados)}."
                    ),
                    "datos": {"posiciones_ganadas": ganadas, "supera_a": superados,
                              "desde": pos_prev[n], "hasta": pos_h[n]},
                })
            elif len(superados) == 1:
                eventos_paso.append({
                    "tipo": "adelantamiento", "nivel": 3,
                    "titulo": "Adelantamiento",
                    "protagonista": n,
                    "detalle": f"{n} supera a {superados[0]}.",
                    "datos": {"supera_a": superados},
                })

        # ── Mayor ventaja del líder (un único evento, el récord) ──
        if len(lideres_actuales) == 1:
            lider = lideres_actuales[0]
            resto = [acc[n] for n in nombres_humanos if n != lider]
            if resto:
                ventaja = acc[lider] - max(resto)
                if ventaja > max_ventaja["valor"] and ventaja >= 3:
                    max_ventaja["valor"] = ventaja
                    eventos_paso.append({
                        "tipo": "mayor_ventaja", "nivel": 2,
                        "titulo": "Mayor ventaja del torneo",
                        "protagonista": lider,
                        "detalle": f"{lider} abre {ventaja} puntos de ventaja sobre el 2.º.",
                        "datos": {"ventaja": ventaja, "puntos": acc[lider]},
                    })

        # ── Mayor remontada acumulada (récord global, una vez) ──
        for n in nombres_humanos:
            mejor_pos[n] = min(mejor_pos[n], pos_h[n])
            if pos_h[n] > peor_pos_tras_buena[n]:
                peor_pos_tras_buena[n] = pos_h[n]
            remontada = peor_pos_tras_buena[n] - pos_h[n]
            if remontada > max_remontada["valor"] and remontada >= 3:
                max_remontada["valor"] = remontada
                eventos_paso.append({
                    "tipo": "mayor_remontada", "nivel": 2,
                    "titulo": "Mayor remontada hasta ahora",
                    "protagonista": n,
                    "detalle": f"{n} recupera {remontada} posiciones desde su peor momento.",
                    "datos": {"posiciones": remontada, "hasta": pos_h[n]},
                })

        # Deduplicar por protagonista priorizando nivel más alto (menor número)
        eventos_paso = _dedup_por_protagonista(eventos_paso)
        for e in eventos_paso:
            e.update(ref)
            e["id"] = f"{e['tipo']}-{paso}-{e.get('protagonista','')}"
            eventos.append(e)

    # ── Partido(s) clave: mayor impacto en la clasificación ──
    eventos.extend(_partidos_clave(partidos_serie, snapshots, nombres_humanos))

    return eventos


def _dedup_por_protagonista(eventos_paso: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Conserva, por protagonista, solo el evento de mayor importancia (nivel menor)."""
    mejor: dict[str, dict[str, Any]] = {}
    sueltos: list[dict[str, Any]] = []
    for e in eventos_paso:
        prot = e.get("protagonista")
        if prot is None:
            sueltos.append(e)
            continue
        if prot not in mejor or e["nivel"] < mejor[prot]["nivel"]:
            mejor[prot] = e
    return list(mejor.values()) + sueltos


def _partidos_clave(
    partidos_serie: list[dict[str, Any]],
    snapshots: list[dict[str, dict[str, int]]],
    nombres_humanos: list[str],
) -> list[dict[str, Any]]:
    """Detecta el/los partido(s) con mayor reordenación de la clasificación."""
    impactos: list[tuple[int, int]] = []
    for paso in range(1, len(snapshots) + 1):
        pos = {n: snapshots[paso - 1]["humanos"][n] for n in nombres_humanos}
        prev = (
            {n: snapshots[paso - 2]["humanos"][n] for n in nombres_humanos}
            if paso >= 2 else {n: pos[n] for n in nombres_humanos}
        )
        impacto = sum(abs(pos[n] - prev[n]) for n in nombres_humanos)
        if impacto > 0:
            impactos.append((impacto, paso))

    if not impactos:
        return []

    impactos.sort(reverse=True)
    mejor_impacto = impactos[0][0]
    if mejor_impacto < 4:
        return []

    eventos: list[dict[str, Any]] = []
    for impacto, paso in impactos[:1]:
        p = partidos_serie[paso - 1]
        marcador = p.get("marcador")
        equipos = f"{p['local']} vs {p['visitante']}"
        if marcador:
            h, a = marcador.split("-")
            equipos = f"{p['local']} {h} – {a} {p['visitante']}"
        eventos.append({
            "tipo": "partido_clave", "nivel": 2,
            "titulo": "Partido que sacudió la clasificación",
            "protagonista": None,
            "detalle": "Este resultado provocó el mayor vuelco de toda la porra.",
            "datos": {"impacto": impacto},
            "match_id": p["match_id"], "orden": paso, "fase": p["fase"],
            "equipos": equipos, "fecha": p["fecha"],
            "id": f"partido_clave-{paso}",
        })
    return eventos
