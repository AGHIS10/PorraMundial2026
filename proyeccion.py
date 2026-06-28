"""Motor de proyección Monte Carlo de la porra (lógica pura, sin I/O).

Simula miles de veces el resto del Mundial y mide:

  🏆  Probabilidad de GANAR la porra (participan todos, incluidas las IA).
  🥉  Probabilidad de terminar en el TOP 3 (solo participantes reales; las IA
      se eliminan de cada clasificación simulada ANTES de recortar el Top 3).

Principios de diseño:

- **No duplica reglas.** La puntuación de cada partido se calcula con las mismas
  funciones que la clasificación real (`apuestas.puntos_apuesta` y
  `apuestas.contar_aciertos_apuesta`). El desempate replica el de
  `calcular_clasificacion.ordenar_clasificacion` (puntos ↓, aciertos ↓, nombre ↑).
- **Reproducible.** Semilla fija configurable: mismos datos → mismos porcentajes.
- **Eficiente.** Todo lo constante se precalcula una sola vez; las simulaciones
  se vectorizan con NumPy (sin bucles Python por simulación).
- **Escalable.** El simulador devuelve la matriz de resultados; añadir nuevas
  métricas (posición exacta, valor esperado del premio, etc.) no exige rehacer
  el motor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import numpy as np

from apuestas import (
    contar_aciertos_apuesta,
    es_eliminatoria,
    partido_tiene_resultado,
    puntos_apuesta,
    puntos_por_tipo_apuesta,
)
from reparto_premios import es_participante_virtual

SIMULACIONES = 20000
RANDOM_SEED = 2026

_RESULTADOS = ("1", "X", "2")
_CLASIFICA = ("1", "2")

# ── Modelo de acierto para participantes SIN pronóstico ─────────────────────
#
# Partidos pendientes sin pronóstico (rondas aún no abiertas) se modelan como
# una apuesta futura con dos componentes:
#
#   p_adj[k, i] = α_i * tasa_historica[i] + (1 − α_i) * p_mercado[k]
#
# • α_i es dinámico: crece con el avance del torneo y las apuestas evaluadas
#   del jugador (véase ``_alpha_habilidad``). Al inicio del Mundial α ≈ 0;
#   con fase de grupos completa y torneo avanzado, α_i → ALPHA_MAX (0.20).
#
# Resultado: los participantes históricaamente precisos tienen una ligera ventaja
# en rondas futuras; los demás no quedan en 0. La varianza sigue siendo alta
# mientras queden puntos en disputa, preservando remontadas.

# Peso máximo del historial propio cuando hay confianza plena [0, 1].
# 0 = puro mercado; 1 = puro historial. El valor efectivo crece con el avance
# del torneo y el volumen de apuestas evaluadas de cada jugador.
ALPHA_MAX: float = 0.20

# Apuestas evaluadas necesarias para confianza plena en el historial de un
# jugador (~48 partidos de grupos × 1 apuesta). Con menos datos, α baja.
UMBRAL_APUESTAS_CONFIANZA: float = 48.0

# Tasa de acierto sin historial: tasa esperada de un apostador sin información.
# 1/3 ≈ E[aciertos resultado] con distribución uniforme 1/X/2.
TASA_NEUTRAL: float = 1.0 / 3

# Cota superior de aciertos por participante; separa puntos de aciertos al
# codificar la clave de ordenación en un único entero. Holgada de sobra.
_ESCALA_ACIERTOS = 1000


class _ParticipanteLike(Protocol):
    nombre: str
    pronosticos: Sequence[Any]


class _PartidoLike(Protocol):
    id: int
    fase: str


@dataclass(frozen=True)
class ResultadoProyeccion:
    """Salida del motor, lista para serializar.

    ``campeon`` y ``top3`` son vistas derivadas de ``distribucion`` (la
    distribución completa de posiciones), que es el artefacto central reutilizable
    para métricas futuras (prob. por puesto, valor esperado del premio, etc.).

    Los campos ``stats`` y ``frecuencia_empate_liderato`` son métricas internas
    preparadas para análisis futuro; el frontend actual no las consume.
    """

    simulaciones: int
    seed: int
    partidos_pendientes: int
    # Puntos máximos aún en disputa (suma de los pesos de todos los partidos
    # pendientes). Útil para contextualizar las probabilidades: si este valor es
    # alto y las probabilidades ya son extremas, el modelo debería revisarse.
    puntos_max_restantes: int
    # (nombre, probabilidad %) ordenado de mayor a menor.
    campeon: list[tuple[str, float]]
    top3: list[tuple[str, float]]
    # nombre → [P(puesto 1), P(puesto 2), …] en % sobre el ranking global.
    distribucion: dict[str, list[float]]
    # Métricas internas por participante: media y desviación típica de puntos finales.
    stats: dict[str, dict[str, float]]
    # Fracción de simulaciones donde el liderato se decide por desempate (puntos igualados).
    frecuencia_empate_liderato: float


@dataclass(frozen=True)
class _TablaPartido:
    """Tabla precalculada de un partido pendiente.

    Para cada uno de los ``n`` desenlaces posibles guarda la probabilidad y el
    vector de puntos/aciertos de los participantes que YA tienen pronóstico (son
    deterministas dado el desenlace). Los participantes SIN pronóstico se modelan
    aparte con una probabilidad de acierto ajustada por historial:

        acierto[k, i] = α * tasa_historica[i] + (1−α) * p_mercado[k]

    Así la simulación solo muestrea un índice y suma vectores ya calculados,
    y los Bernoulli de los sin-pronóstico reflejan diferencias reales de habilidad.
    """

    probs: np.ndarray      # (n,)
    puntos: np.ndarray     # (n, P) int32 — participantes con pronóstico
    aciertos: np.ndarray   # (n, P) int32 — participantes con pronóstico
    sin_pronostico: np.ndarray  # (m,) índices de participantes sin pronóstico
    acierto_res: np.ndarray     # (n, m) P(acertar resultado) ajustada por historial
    acierto_cls: np.ndarray     # (n, m) P(acertar clasifica) ajustada por historial
    peso_res: int
    peso_cls: int


def _es_pendiente(resultado: Any, fase: str) -> bool:
    """Un partido está pendiente si aún no tiene resultado oficial puntuable."""
    return not partido_tiene_resultado(resultado, fase)


def _desenlaces(
    fase: str, dist: dict[str, dict[str, float]]
) -> list[tuple[Any, float, str, str | None]]:
    """Espacio de desenlaces de un partido: (entrada, prob, resultado, clasifica).

    - Grupos: 3 desenlaces (1/X/2), clasifica = None.
    - Eliminatoria con distribución conjunta (``dist["conjunta"]``): los
      desenlaces son exactamente los provistos; las combinaciones imposibles
      (e.g., victoria local + clasificado visitante) simplemente no aparecen.
    - Eliminatoria sin distribución conjunta: 6 desenlaces = resultado(3) ×
      clasifica(2), probabilidad producto (modelo de independencia original).
    """
    if "conjunta" in dist and es_eliminatoria(fase):
        return [
            (
                {"resultado": item["resultado"], "clasifica": item["clasifica"]},
                item["prob"],
                item["resultado"],
                item["clasifica"],
            )
            for item in dist["conjunta"]
        ]

    res = dist["resultado"]
    if not es_eliminatoria(fase):
        return [(marca, res[marca], marca, None) for marca in _RESULTADOS]

    cls = dist["clasifica"]
    return [
        ({"resultado": r, "clasifica": c}, res[r] * cls[c], r, c)
        for r in _RESULTADOS
        for c in _CLASIFICA
    ]


def _pron_vacio(pronostico: Any, fase: str) -> bool:
    """True si el participante no tiene una apuesta utilizable en este partido."""
    if pronostico is None:
        return True
    if es_eliminatoria(fase) and isinstance(pronostico, dict):
        return pronostico.get("resultado") is None and pronostico.get("clasifica") is None
    return False


def _alpha_habilidad(
    oportunidades: float,
    partidos_jugados: int,
    partidos_total: int,
) -> float:
    """Peso dinámico del historial para un participante, en [0, ALPHA_MAX].

    α = ALPHA_MAX × progreso_torneo × confianza_historial

    - progreso_torneo = partidos_jugados / partidos_total
    - confianza_historial = min(1, apuestas_evaluadas / UMBRAL_APUESTAS_CONFIANZA)

    Con pocos partidos disputados o poco historial individual, α ≈ 0 (mercado
    puro). A medida que avanza el Mundial y crece el historial, α se acerca a
    ALPHA_MAX sin superarlo nunca.
    """
    if partidos_total <= 0 or oportunidades <= 0:
        return 0.0
    progreso = min(1.0, partidos_jugados / partidos_total)
    confianza = min(1.0, oportunidades / UMBRAL_APUESTAS_CONFIANZA)
    return ALPHA_MAX * progreso * confianza


def _calcular_tasas_historicas(
    participantes: Sequence[_ParticipanteLike],
    partidos: Sequence[_PartidoLike],
    resultados: Sequence[Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Tasa de acierto y apuestas evaluadas por participante.

    Devuelve (tasas, oportunidades): arrays de forma (P,). La tasa se usa para
    el blend de acierto; las oportunidades alimentan ``_alpha_habilidad``.
    """
    p = len(participantes)
    aciertos_hist = np.zeros(p, dtype=np.float64)
    oportunidades = np.zeros(p, dtype=np.float64)

    for j, (resultado, partido) in enumerate(zip(resultados, partidos)):
        if _es_pendiente(resultado, partido.fase):
            continue
        bets_posibles = 2 if es_eliminatoria(partido.fase) else 1
        for i, participante in enumerate(participantes):
            pron = participante.pronosticos[j]
            if _pron_vacio(pron, partido.fase):
                continue
            aciertos_hist[i] += contar_aciertos_apuesta(pron, resultado, partido.fase)
            oportunidades[i] += bets_posibles

    tasas = np.where(oportunidades > 0, aciertos_hist / oportunidades, TASA_NEUTRAL)
    return tasas, oportunidades


def _tabla_partido(
    indice_pronostico: int,
    fase: str,
    participantes: Sequence[_ParticipanteLike],
    dist: dict[str, dict[str, float]],
    tasas_historicas: np.ndarray,
    alphas: np.ndarray,
) -> _TablaPartido:
    """Precalcula puntos/aciertos por desenlace para todos los participantes."""
    desenlaces = _desenlaces(fase, dist)
    n = len(desenlaces)
    p = len(participantes)
    eliminatoria = es_eliminatoria(fase)

    probs = np.fromiter((prob for _, prob, _, _ in desenlaces), dtype=np.float64, count=n)
    suma = probs.sum()
    if suma <= 0:
        raise ValueError(f"Distribución sin masa positiva en fase '{fase}'.")
    probs /= suma  # defensivo: garantiza que sume 1

    puntos = np.zeros((n, p), dtype=np.int32)
    aciertos = np.zeros((n, p), dtype=np.int32)
    sin_pronostico: list[int] = [
        i
        for i, participante in enumerate(participantes)
        if _pron_vacio(participante.pronosticos[indice_pronostico], fase)
    ]

    for k, (entrada, _, _, _) in enumerate(desenlaces):
        for i, participante in enumerate(participantes):
            pron = participante.pronosticos[indice_pronostico]
            if _pron_vacio(pron, fase):
                continue  # se modela aparte (predicción futura aleatoria)
            puntos[k, i] = puntos_apuesta(pron, entrada, fase)
            aciertos[k, i] = contar_aciertos_apuesta(pron, entrada, fase)

    # ── Probabilidades base de acierto del mercado (1 valor por desenlace) ──
    #
    # P(acierto resultado | desenlace k) = P(predicción aleatoria = r_k)
    #   = marginal P(resultado = r_k) de la distribución del partido.
    #
    # Con distribución conjunta las marginales se derivan de las probabilidades
    # normalizadas ya en ``probs``; con distribución separada, los dicts
    # ``resultado`` y ``clasifica`` ya son marginales normalizadas.

    if "conjunta" in dist and eliminatoria:
        # Marginar la distribución conjunta usando las probs ya normalizadas.
        marginal_r: dict[str, float] = {}
        marginal_c: dict[str, float] = {}
        for k_idx, (_, _, r, c) in enumerate(desenlaces):
            marginal_r[r] = marginal_r.get(r, 0.0) + float(probs[k_idx])
            if c is not None:
                marginal_c[c] = marginal_c.get(c, 0.0) + float(probs[k_idx])
        base_acierto_res = np.fromiter(
            (marginal_r.get(r, 0.0) for _, _, r, _ in desenlaces), dtype=np.float64, count=n
        )
        base_acierto_cls = np.fromiter(
            (marginal_c.get(c, 0.0) if c is not None else 0.0 for _, _, _, c in desenlaces),
            dtype=np.float64, count=n,
        )
    else:
        res_dist = dist["resultado"]
        base_acierto_res = np.fromiter(
            (res_dist[r] for _, _, r, _ in desenlaces), dtype=np.float64, count=n
        )
        if eliminatoria:
            cls_dist = dist["clasifica"]
            base_acierto_cls = np.fromiter(
                (cls_dist[c] for _, _, _, c in desenlaces), dtype=np.float64, count=n
            )
        else:
            base_acierto_cls = np.zeros(n, dtype=np.float64)

    peso_cls = puntos_por_tipo_apuesta(fase, "clasifica") if eliminatoria else 0

    # ── Ajuste histórico: (n, m) por desenlace × participante sin pronóstico ──
    #
    # acierto_adj[k, i] = α_i * tasa[i] + (1−α_i) * base_mercado[k]
    m = len(sin_pronostico)
    if m > 0:
        idx_sin = np.array(sin_pronostico, dtype=np.int64)
        tasa_sin = tasas_historicas[idx_sin]   # (m,)
        alpha_sin = alphas[idx_sin]            # (m,) — distinto por jugador
        acierto_res = (
            (1.0 - alpha_sin[np.newaxis, :]) * base_acierto_res[:, np.newaxis]
            + alpha_sin[np.newaxis, :] * tasa_sin[np.newaxis, :]
        )  # (n, m)
        acierto_cls = (
            (1.0 - alpha_sin[np.newaxis, :]) * base_acierto_cls[:, np.newaxis]
            + alpha_sin[np.newaxis, :] * tasa_sin[np.newaxis, :]
        )  # (n, m)
    else:
        idx_sin = np.empty(0, dtype=np.int64)
        acierto_res = np.empty((n, 0), dtype=np.float64)
        acierto_cls = np.empty((n, 0), dtype=np.float64)

    return _TablaPartido(
        probs=probs,
        puntos=puntos,
        aciertos=aciertos,
        sin_pronostico=idx_sin,
        acierto_res=acierto_res,
        acierto_cls=acierto_cls,
        peso_res=puntos_por_tipo_apuesta(fase, "resultado"),
        peso_cls=peso_cls,
    )


def _puntuacion_base(
    participantes: Sequence[_ParticipanteLike],
    partidos: Sequence[_PartidoLike],
    resultados: Sequence[Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Puntos y aciertos ya consolidados (partidos con resultado oficial).

    Constante en todas las simulaciones: se calcula una sola vez con el mismo
    motor que la clasificación real.
    """
    p = len(participantes)
    base_puntos = np.zeros(p, dtype=np.int64)
    base_aciertos = np.zeros(p, dtype=np.int64)

    for j, (resultado, partido) in enumerate(zip(resultados, partidos)):
        if _es_pendiente(resultado, partido.fase):
            continue
        for i, participante in enumerate(participantes):
            pron = participante.pronosticos[j]
            base_puntos[i] += puntos_apuesta(pron, resultado, partido.fase)
            base_aciertos[i] += contar_aciertos_apuesta(pron, resultado, partido.fase)

    return base_puntos, base_aciertos


def _ranking_alfabetico(nombres: Sequence[str]) -> np.ndarray:
    """Rango alfabético de cada nombre (0 = primero). Desempate final estable."""
    orden = sorted(range(len(nombres)), key=lambda i: nombres[i])
    rango = np.empty(len(nombres), dtype=np.int64)
    for posicion, indice in enumerate(orden):
        rango[indice] = posicion
    return rango


def _clave_orden(
    total_puntos: np.ndarray,
    total_aciertos: np.ndarray,
    rango_nombre: np.ndarray,
) -> np.ndarray:
    """Clave entera por participante que replica el desempate oficial.

    Orden: puntos ↓, aciertos ↓, nombre ↑. Se codifica de forma que la clave sea
    ÚNICA dentro de cada simulación, de modo que un ``argsort`` produzca un
    ranking total sin empates (puestos 1..P bien definidos).
    """
    p = rango_nombre.shape[0]
    clave = (total_puntos * _ESCALA_ACIERTOS + total_aciertos) * p
    # Nombre ascendente gana el empate: menor rango ⇒ mayor contribución.
    return clave + (p - 1 - rango_nombre)


def _rango_por_simulacion(clave: np.ndarray) -> np.ndarray:
    """Ranking 1..K por simulación (1 = mejor) a partir de la clave (N, K)."""
    # argsort(argsort(-clave)) da la posición de cada elemento en orden descendente.
    return np.argsort(np.argsort(-clave, axis=1), axis=1) + 1


def _distribucion_posiciones(rangos: np.ndarray, k: int) -> np.ndarray:
    """Cuenta, por participante, en cuántas simulaciones ocupó cada puesto.

    Devuelve (K, K): fila = participante, columna = puesto (0-based).
    """
    n = rangos.shape[0]
    cuentas = np.zeros((k, k), dtype=np.int64)
    for puesto in range(1, k + 1):
        cuentas[:, puesto - 1] = (rangos == puesto).sum(axis=0)
    return cuentas


def _agregar(
    total_puntos: np.ndarray,
    total_aciertos: np.ndarray,
    nombres: Sequence[str],
    es_ia: np.ndarray,
    simulaciones: int,
) -> tuple[
    list[tuple[str, float]],      # campeon
    list[tuple[str, float]],      # top3
    dict[str, list[float]],       # distribucion completa
    dict[str, dict[str, float]],  # stats internas
    float,                         # frecuencia_empate_liderato
]:
    """Probabilidades de campeón, Top 3, distribución de posiciones y métricas."""
    p = len(nombres)
    rango_nombre = _ranking_alfabetico(nombres)
    clave = _clave_orden(total_puntos, total_aciertos, rango_nombre)  # (N, P)

    def porcentaje(cuenta: int) -> float:
        return round(100.0 * cuenta / simulaciones, 2)

    # Ranking global (todos compiten por el título, incluidas las IA).
    rangos_global = _rango_por_simulacion(clave)  # (N, P)
    dist_global = _distribucion_posiciones(rangos_global, p)  # (P, P)

    distribucion = {
        nombres[i]: [porcentaje(int(dist_global[i, r])) for r in range(p)]
        for i in range(p)
    }

    # 🏆 Campeón = probabilidad de puesto 1 en el ranking global.
    campeon_cuentas = dist_global[:, 0]

    # 🥉 Top 3: se eliminan las IA ANTES de rankear, sobre cada simulación.
    cols_humanas = np.flatnonzero(~es_ia)
    h = cols_humanas.shape[0]
    if h == 0:
        top3_cuentas_humanas = np.zeros(0, dtype=np.int64)
    elif h <= 3:
        top3_cuentas_humanas = np.full(h, simulaciones, dtype=np.int64)
    else:
        rangos_humanos = _rango_por_simulacion(clave[:, cols_humanas])  # (N, H)
        top3_cuentas_humanas = (rangos_humanos <= 3).sum(axis=0)

    campeon = sorted(
        ((nombres[i], porcentaje(int(campeon_cuentas[i]))) for i in range(p)),
        key=lambda par: (-par[1], par[0]),
    )
    top3 = sorted(
        (
            (nombres[int(cols_humanas[k])], porcentaje(int(top3_cuentas_humanas[k])))
            for k in range(h)
        ),
        key=lambda par: (-par[1], par[0]),
    )

    # ── Métricas internas (no mostradas en frontend; para análisis futuro) ────
    media_arr = total_puntos.mean(axis=0)   # (P,)
    std_arr = total_puntos.std(axis=0)      # (P,)
    stats = {
        nombres[i]: {
            "media_puntos": round(float(media_arr[i]), 1),
            "std_puntos": round(float(std_arr[i]), 1),
        }
        for i in range(p)
    }

    # Fracción de simulaciones donde el liderato se decide por desempate:
    # 2+ participantes comparten el máximo de puntos → el nombre/aciertos
    # determina quién gana, no los puntos en sí.
    max_pts = total_puntos.max(axis=1, keepdims=True)  # (N, 1)
    empate_en_lider = (total_puntos == max_pts).sum(axis=1) > 1  # (N,)
    frecuencia_empate_liderato = round(float(empate_en_lider.mean()), 4)

    return campeon, top3, distribucion, stats, frecuencia_empate_liderato


def simular(
    participantes: Sequence[_ParticipanteLike],
    partidos: Sequence[_PartidoLike],
    resultados: Sequence[Any],
    proveedor: Any,
    *,
    simulaciones: int = SIMULACIONES,
    seed: int = RANDOM_SEED,
) -> ResultadoProyeccion:
    """Ejecuta la simulación Monte Carlo y devuelve las probabilidades."""
    if not participantes:
        return ResultadoProyeccion(
            simulaciones, seed, 0, 0, [], [], {}, {}, 0.0
        )

    nombres = [p.nombre for p in participantes]
    es_ia = np.array([es_participante_virtual(n) for n in nombres], dtype=bool)

    base_puntos, base_aciertos = _puntuacion_base(participantes, partidos, resultados)
    tasas, oportunidades = _calcular_tasas_historicas(participantes, partidos, resultados)

    partidos_total = len(partidos)
    partidos_jugados = partidos_total - sum(
        1 for r, p in zip(resultados, partidos) if _es_pendiente(r, p.fase)
    )
    alphas = np.array(
        [
            _alpha_habilidad(oportunidades[i], partidos_jugados, partidos_total)
            for i in range(len(participantes))
        ],
        dtype=np.float64,
    )

    pendientes = [
        (j, partido)
        for j, (resultado, partido) in enumerate(zip(resultados, partidos))
        if _es_pendiente(resultado, partido.fase)
    ]
    tablas = [
        _tabla_partido(
            j, partido.fase, participantes, proveedor.distribucion(partido), tasas, alphas
        )
        for j, partido in pendientes
    ]

    # Puntos máximos aún en disputa (meta-dato para contextualizar las prob.).
    puntos_max_restantes = sum(
        puntos_por_tipo_apuesta(partido.fase, "resultado")
        + (puntos_por_tipo_apuesta(partido.fase, "clasifica") if es_eliminatoria(partido.fase) else 0)
        for _, partido in pendientes
    )

    rng = np.random.default_rng(seed)
    total_puntos = np.tile(base_puntos, (simulaciones, 1))  # (N, P)
    total_aciertos = np.tile(base_aciertos, (simulaciones, 1))

    for tabla in tablas:
        elegidos = rng.choice(tabla.probs.shape[0], size=simulaciones, p=tabla.probs)
        # Participantes con pronóstico: contribución determinista por desenlace.
        total_puntos += tabla.puntos[elegidos]
        total_aciertos += tabla.aciertos[elegidos]

        # Participantes sin pronóstico: Bernoulli independiente por participante.
        # ``acierto_res`` y ``acierto_cls`` son (n, m) — indexar con (N,) da (N, m).
        cols = tabla.sin_pronostico
        if cols.size == 0:
            continue

        p_res = tabla.acierto_res[elegidos]   # (N, m) — ya ajustado por historial
        hit_res = rng.random((simulaciones, cols.size)) < p_res
        total_puntos[:, cols] += tabla.peso_res * hit_res
        total_aciertos[:, cols] += hit_res

        if tabla.peso_cls:
            p_cls = tabla.acierto_cls[elegidos]  # (N, m)
            hit_cls = rng.random((simulaciones, cols.size)) < p_cls
            total_puntos[:, cols] += tabla.peso_cls * hit_cls
            total_aciertos[:, cols] += hit_cls

    campeon, top3, distribucion, stats, frecuencia_empate_liderato = _agregar(
        total_puntos, total_aciertos, nombres, es_ia, simulaciones
    )
    return ResultadoProyeccion(
        simulaciones=simulaciones,
        seed=seed,
        partidos_pendientes=len(pendientes),
        puntos_max_restantes=puntos_max_restantes,
        campeon=campeon,
        top3=top3,
        distribucion=distribucion,
        stats=stats,
        frecuencia_empate_liderato=frecuencia_empate_liderato,
    )
