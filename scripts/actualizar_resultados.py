"""Actualiza resultados.json consultando football-data.org."""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))

from apuestas import es_eliminatoria  # noqa: E402

PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
RESULTADOS_FILE = PROYECTO_DIR / "resultados.json"
MARCADORES_FILE = PROYECTO_DIR / "marcadores.json"
ALIAS_FILE = PROYECTO_DIR / "equipos_alias.json"
RUN_STATS_FILE = PROYECTO_DIR / ".run" / "actualizar_stats.json"
API_URL = "https://api.football-data.org/v4/competitions/WC/matches"
API_MATCHES_URL = "https://api.football-data.org/v4/matches"
API_SEASON = 2026
API_KEY_ENV = "FOOTBALL_DATA_API_KEY"
ESTADOS_FINALIZADOS = frozenset({"FINISHED", "AWARDED"})
MAX_DIFERENCIA_DIAS = 2
MAX_IDS_POR_PETICION = 50
STAGE_GRUPOS = "GROUP_STAGE"
ZONA_CEST = ZoneInfo("Europe/Madrid")
TOLERANCIA_SEGUNDOS_ELIMINATORIA = 5400
FASE_A_STAGE: dict[str, str] = {
    "dieciseisavos": "LAST_32",
    "octavos": "LAST_16",
    "cuartos": "QUARTER_FINALS",
    "semifinales": "SEMI_FINALS",
    "tercer_puesto": "THIRD_PLACE",
    "final": "FINAL",
}


def cargar_json(ruta: Path) -> Any:
    """Carga un fichero JSON."""
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def guardar_json(contenido: Any, ruta: Path) -> None:
    """Escribe un fichero JSON."""
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def instante_utc_iso() -> str:
    """Devuelve la hora actual en UTC con sufijo Z."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def guardar_estadisticas_ejecucion(
    last_api_check: str,
    estadisticas: dict[str, int],
    marcadores_enriquecidos: int,
) -> None:
    """Persiste métricas de la ejecución para generar status.json al final del workflow."""
    RUN_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    guardar_json(
        {
            "lastApiCheck": last_api_check,
            "matchesUpdated": estadisticas["actualizados"],
            "finishedMatches": estadisticas["finalizados"],
            "matchesPending": estadisticas["pendientes"],
            "matchesFound": estadisticas["encontrados"],
            "scoresEnriched": marcadores_enriquecidos,
        },
        RUN_STATS_FILE,
    )


def normalizar_nombre(nombre: str) -> str:
    """Normaliza un nombre de equipo para comparación flexible."""
    texto = unicodedata.normalize("NFKD", nombre)
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = re.sub(
        r"\b(and|the|of|y|de|del|republic|islands|herzegovina)\b",
        "",
        texto,
    )
    texto = re.sub(r"[^a-z0-9]+", "", texto)
    return texto


def variantes_alias(valor: str | list[str]) -> list[str]:
    """Convierte un valor de alias en una lista de variantes."""
    if isinstance(valor, list):
        return valor
    return [valor]


def nombres_api_esperados(nombre_local: str, alias: dict[str, str | list[str]]) -> set[str]:
    """Devuelve los nombres normalizados esperados en la API para un equipo local."""
    valor_alias = alias.get(nombre_local, nombre_local)
    candidatos = variantes_alias(valor_alias) if isinstance(valor_alias, list) else [valor_alias]
    candidatos.append(nombre_local)
    return {normalizar_nombre(nombre) for nombre in candidatos}


def nombres_equipo_coinciden(
    nombre_local: str,
    nombre_api: str,
    alias: dict[str, str | list[str]],
) -> bool:
    """Comprueba si un nombre local y otro de la API representan el mismo equipo."""
    candidatos_local = nombres_api_esperados(nombre_local, alias)
    nombre_api_normalizado = normalizar_nombre(nombre_api)
    if nombre_api_normalizado in candidatos_local:
        return True
    return any(
        candidato
        and (candidato in nombre_api_normalizado or nombre_api_normalizado in candidato)
        for candidato in candidatos_local
    )


def parsear_fecha_api(utc_date: str) -> date:
    """Convierte una fecha UTC de la API a date."""
    instante = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    return instante.astimezone(timezone.utc).date()


def fechas_compatibles(fecha_partido: str, utc_date: str) -> bool:
    """Permite pequeñas diferencias por husos horarios."""
    if not utc_date:
        return False
    fecha_local = date.fromisoformat(fecha_partido)
    fecha_api = parsear_fecha_api(utc_date)
    return abs((fecha_local - fecha_api).days) <= MAX_DIFERENCIA_DIAS


def nombre_equipo_api(partido_api: dict[str, Any], lado: str) -> str:
    """Devuelve el nombre de homeTeam o awayTeam de un partido API."""
    equipo = partido_api.get(f"{lado}Team") or {}
    if isinstance(equipo, dict):
        return equipo.get("name") or ""
    return ""


def equipos_coinciden(
    partido: dict[str, Any],
    partido_api: dict[str, Any],
    alias: dict[str, str | list[str]],
) -> bool:
    """Comprueba si local/visitante coinciden con home/away de la API."""
    home_api = nombre_equipo_api(partido_api, "home")
    away_api = nombre_equipo_api(partido_api, "away")
    return (
        nombres_equipo_coinciden(partido["local"], home_api, alias)
        and nombres_equipo_coinciden(partido["visitante"], away_api, alias)
    )


def instante_partido_local(partido: dict[str, Any]) -> datetime:
    """Convierte fecha/hora local (CEST) del partido a datetime."""
    hora = partido.get("hora") or "00:00"
    instante = datetime.strptime(
        f"{partido['fecha']} {hora}",
        "%Y-%m-%d %H:%M",
    )
    return instante.replace(tzinfo=ZONA_CEST)


def instante_partido_api(partido_api: dict[str, Any]) -> datetime | None:
    """Convierte utcDate de la API a datetime en CEST."""
    utc_date = partido_api.get("utcDate")
    if not utc_date:
        return None
    instante = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    return instante.astimezone(ZONA_CEST)


def eliminatoria_coincide(
    partido: dict[str, Any],
    partido_api: dict[str, Any],
) -> bool:
    """Empareja eliminatorias por fase (stage API) y fecha/hora en CEST."""
    stage_esperado = FASE_A_STAGE.get(partido.get("fase", ""))
    if not stage_esperado or partido_api.get("stage") != stage_esperado:
        return False

    instante_local = instante_partido_local(partido)
    instante_api = instante_partido_api(partido_api)
    if instante_api is None:
        return False

    diferencia = abs((instante_local - instante_api).total_seconds())
    return diferencia <= TOLERANCIA_SEGUNDOS_ELIMINATORIA


def contar_partidos_grupos_api(partidos_api: list[dict[str, Any]]) -> int:
    """Cuenta partidos de fase de grupos en la respuesta de la API."""
    return sum(1 for partido in partidos_api if partido.get("stage") == STAGE_GRUPOS)


def resultado_desde_marcador(goles_local: int, goles_visitante: int) -> str:
    """Convierte un marcador a 1, X o 2."""
    if goles_local > goles_visitante:
        return "1"
    if goles_local < goles_visitante:
        return "2"
    return "X"


def extraer_goles_marcador(marcador: dict[str, Any]) -> tuple[int | None, int | None]:
    """Lee goles de un nodo de marcador (v4: home/away, v2: homeTeam/awayTeam)."""
    if not isinstance(marcador, dict):
        return None, None
    goles_local = marcador.get("home")
    goles_visitante = marcador.get("away")
    if goles_local is None:
        goles_local = marcador.get("homeTeam")
    if goles_visitante is None:
        goles_visitante = marcador.get("awayTeam")
    return goles_local, goles_visitante


def extraer_marcador_desde_nodo(
    score: dict[str, Any],
    nodo: str,
) -> tuple[int, int] | None:
    """Lee un subnodo de score (fullTime, regularTime…) como marcador."""
    datos = score.get(nodo) or {}
    goles_local, goles_visitante = extraer_goles_marcador(datos)
    if goles_local is None or goles_visitante is None:
        return None
    return int(goles_local), int(goles_visitante)


def duracion_partido_api(partido_api: dict[str, Any]) -> str:
    """REGULAR, EXTRA_TIME o PENALTY_SHOOTOUT según la API."""
    score = partido_api.get("score") or {}
    return str(score.get("duration") or "REGULAR")


def extraer_marcador_90min(partido_api: dict[str, Any]) -> tuple[int, int] | None:
    """Marcador tras 90 minutos (1/X/2 de la porra).

    En eliminatorias con prórroga o penaltis, fullTime puede incluir la tanda
    o el marcador global; la API expone score.regularTime para los 90 minutos.
    Ver: https://docs.football-data.org/general/v4/overtime.html
    """
    score = partido_api.get("score") or {}
    duration = duracion_partido_api(partido_api)

    marcador_regular = extraer_marcador_desde_nodo(score, "regularTime")
    if marcador_regular is not None:
        return marcador_regular

    if duration == "REGULAR":
        return extraer_marcador_desde_nodo(score, "fullTime")

    return None


def extraer_marcador_final(partido_api: dict[str, Any]) -> tuple[int, int] | None:
    """Alias: marcador de apuesta (90 minutos)."""
    return extraer_marcador_90min(partido_api)


def marcador_final_incompleto(partido_api: dict[str, Any]) -> bool:
    """Indica si un partido finalizado no trae marcador en la respuesta."""
    return partido_finalizado(partido_api) and extraer_marcador_final(partido_api) is None


def fusionar_score(
    score_base: dict[str, Any] | None,
    score_nuevo: dict[str, Any] | None,
) -> dict[str, Any]:
    """Combina nodos score conservando valores ya conocidos."""
    resultado = dict(score_base or {})
    if not isinstance(score_nuevo, dict):
        return resultado

    nodos_marcador = ("fullTime", "halfTime", "regularTime", "extraTime", "penalties")
    for clave, valor in score_nuevo.items():
        if clave in nodos_marcador and isinstance(valor, dict):
            existente = resultado.get(clave) or {}
            fusionado = dict(existente) if isinstance(existente, dict) else {}
            for sub_clave, sub_valor in valor.items():
                if sub_valor is not None:
                    fusionado[sub_clave] = sub_valor
            resultado[clave] = fusionado
        elif valor is not None:
            resultado[clave] = valor
    return resultado


def fusionar_partido_api(
    partido_base: dict[str, Any],
    partido_nuevo: dict[str, Any],
) -> dict[str, Any]:
    """Fusiona dos representaciones del mismo partido priorizando datos completos."""
    fusionado = dict(partido_base)
    if partido_nuevo.get("status"):
        fusionado["status"] = partido_nuevo["status"]
    if partido_nuevo.get("lastUpdated"):
        fusionado["lastUpdated"] = partido_nuevo["lastUpdated"]
    fusionado["score"] = fusionar_score(
        partido_base.get("score"),
        partido_nuevo.get("score"),
    )
    return fusionado


def partido_finalizado(partido_api: dict[str, Any]) -> bool:
    """Indica si la API considera finalizado el partido."""
    return partido_api.get("status") in ESTADOS_FINALIZADOS


def resultado_desde_api(partido_api: dict[str, Any]) -> str | None:
    """Obtiene 1/X/2 si el partido terminó, o None si sigue pendiente."""
    if not partido_finalizado(partido_api):
        return None
    marcador = extraer_marcador_final(partido_api)
    if marcador is None:
        return None
    return resultado_desde_marcador(*marcador)


def marcador_desde_api(partido_api: dict[str, Any]) -> dict[str, int] | None:
    """Obtiene el marcador numérico final desde la API."""
    marcador = extraer_marcador_final(partido_api)
    if marcador is None:
        return None
    goles_local, goles_visitante = marcador
    return {"home": goles_local, "away": goles_visitante}


def buscar_partido_api(
    partido: dict[str, Any],
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
) -> dict[str, Any] | None:
    """Empareja un partido local con su equivalente en la API."""
    if partido.get("fase") == "grupos":
        candidatos = [
            candidato
            for candidato in partidos_api
            if equipos_coinciden(partido, candidato, alias)
            and fechas_compatibles(partido["fecha"], candidato.get("utcDate", ""))
        ]
        if not candidatos:
            return None
        if len(candidatos) == 1:
            return candidatos[0]

        fecha_objetivo = date.fromisoformat(partido["fecha"])
        return min(
            candidatos,
            key=lambda candidato: abs(
                (parsear_fecha_api(candidato.get("utcDate", "")) - fecha_objetivo).days
            ),
        )

    candidatos = [
        candidato
        for candidato in partidos_api
        if eliminatoria_coincide(partido, candidato)
    ]
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return candidatos[0]

    instante_local = instante_partido_local(partido)
    return min(
        candidatos,
        key=lambda candidato: abs(
            (instante_local - instante_partido_api(candidato)).total_seconds()
        ),
    )


def diagnosticar_partido(
    partido: dict[str, Any],
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
) -> tuple[dict[str, Any] | None, str | None]:
    """Diagnostica por qué un partido no empareja y devuelve motivo detallado."""
    emparejado = buscar_partido_api(partido, partidos_api, alias)
    if emparejado is not None:
        return emparejado, None

    if partido.get("fase") != "grupos":
        stage_esperado = FASE_A_STAGE.get(partido.get("fase", ""), "?")
        instante_local = instante_partido_local(partido)
        return None, (
            f"No hay partido en la API con stage {stage_esperado} "
            f"y hora {instante_local.strftime('%Y-%m-%d %H:%M')} CEST."
        )

    por_equipos = [
        candidato
        for candidato in partidos_api
        if equipos_coinciden(partido, candidato, alias)
    ]
    if por_equipos:
        fechas_api = sorted(
            {
                f"{candidato.get('utcDate', '?')} "
                f"({nombre_equipo_api(candidato, 'home') or '?'} vs "
                f"{nombre_equipo_api(candidato, 'away') or '?'})"
                for candidato in por_equipos
            }
        )
        return None, (
            f"Los equipos existen en la API pero la fecha {partido['fecha']} "
            f"no coincide (tolerancia ±{MAX_DIFERENCIA_DIAS} días). "
            f"Fechas API: {', '.join(fechas_api)}"
        )

    home_api = partido["local"]
    away_api = partido["visitante"]
    esperado_local = variantes_alias(alias.get(home_api, home_api))
    esperado_visitante = variantes_alias(alias.get(away_api, away_api))
    if not isinstance(esperado_local, list):
        esperado_local = [esperado_local]
    if not isinstance(esperado_visitante, list):
        esperado_visitante = [esperado_visitante]

    candidatos_home = sorted(
        {
            nombre_equipo_api(candidato, "home")
            for candidato in partidos_api
            if nombres_equipo_coinciden(
                partido["local"],
                nombre_equipo_api(candidato, "home"),
                alias,
            )
        }
    )
    candidatos_away = sorted(
        {
            nombre_equipo_api(candidato, "away")
            for candidato in partidos_api
            if nombres_equipo_coinciden(
                partido["visitante"],
                nombre_equipo_api(candidato, "away"),
                alias,
            )
        }
    )

    if not candidatos_home and not candidatos_away:
        return None, (
            f"No existe partido en la API con "
            f"{esperado_local[0]} vs {esperado_visitante[0]}. "
            f"Revisar alias de '{home_api}' y '{away_api}'."
        )

    detalles = []
    if not candidatos_home:
        detalles.append(
            f"El local '{home_api}' (alias: {esperado_local}) no aparece como homeTeam en la API"
        )
    else:
        detalles.append(f"homeTeam API coincidente: {', '.join(candidatos_home)}")

    if not candidatos_away:
        detalles.append(
            f"El visitante '{away_api}' (alias: {esperado_visitante}) "
            "no aparece como awayTeam en la API"
        )
    else:
        detalles.append(f"awayTeam API coincidente: {', '.join(candidatos_away)}")

    return None, ". ".join(detalles)


def clasifica_desde_api(partido_api: dict[str, Any]) -> str | None:
    """Devuelve 1 o 2 según quién clasifica (score.winner de la API)."""
    if not partido_finalizado(partido_api):
        return None

    score = partido_api.get("score") or {}
    ganador = score.get("winner")
    if ganador == "HOME_TEAM":
        return "1"
    if ganador == "AWAY_TEAM":
        return "2"
    if ganador == "DRAW":
        return None

    return None


def resultado_entrada_desde_api(
    partido: dict[str, Any],
    partido_api: dict[str, Any],
) -> str | dict[str, str | None] | None:
    """Genera entrada de resultados.json (simple o dual según fase)."""
    resultado = resultado_desde_api(partido_api)
    if resultado is None:
        return None
    fase = str(partido.get("fase", "grupos"))
    if not es_eliminatoria(fase):
        return resultado
    return {"resultado": resultado, "clasifica": clasifica_desde_api(partido_api)}


def cargar_resultados_actuales(total_partidos: int) -> list[Any]:
    """Carga resultados existentes o inicializa una lista vacía."""
    if not RESULTADOS_FILE.exists():
        return [None] * total_partidos
    datos = cargar_json(RESULTADOS_FILE)
    if not isinstance(datos, list):
        raise ValueError("resultados.json debe ser un array.")
    if len(datos) != total_partidos:
        raise ValueError(
            f"resultados.json tiene {len(datos)} entradas, "
            f"pero partidos.json tiene {total_partidos}."
        )
    return datos


def cargar_marcadores_actuales(total_partidos: int) -> list[dict[str, int] | None]:
    """Carga marcadores existentes o inicializa una lista vacía."""
    if not MARCADORES_FILE.exists():
        return [None] * total_partidos
    datos = cargar_json(MARCADORES_FILE)
    if not isinstance(datos, list):
        raise ValueError("marcadores.json debe ser un array.")
    if len(datos) != total_partidos:
        raise ValueError(
            f"marcadores.json tiene {len(datos)} entradas, "
            f"pero partidos.json tiene {total_partidos}."
        )
    return datos


def _consultar_api(
    api_key: str,
    url: str,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Ejecuta una petición GET y devuelve la lista de partidos."""
    respuesta = requests.get(
        url,
        headers={"X-Auth-Token": api_key},
        params=params or {},
        timeout=30,
    )
    respuesta.raise_for_status()
    datos = respuesta.json()
    if isinstance(datos, list):
        return datos
    partidos = datos.get("matches", [])
    if not isinstance(partidos, list):
        raise ValueError("La API no devolvió una lista de partidos.")
    return partidos


def consultar_lista_competicion(api_key: str) -> list[dict[str, Any]]:
    """Consulta todos los partidos del Mundial (calendario completo)."""
    return _consultar_api(api_key, API_URL, {"season": API_SEASON})


def consultar_partidos_finalizados(api_key: str) -> list[dict[str, Any]]:
    """Consulta partidos finalizados; suele traer marcadores completos."""
    return _consultar_api(
        api_key,
        API_URL,
        {"season": API_SEASON, "status": "FINISHED"},
    )


def consultar_partidos_por_ids(
    api_key: str,
    ids_partido: list[int],
) -> list[dict[str, Any]]:
    """Consulta partidos concretos por id (datos más frescos)."""
    if not ids_partido:
        return []

    partidos: list[dict[str, Any]] = []
    for inicio in range(0, len(ids_partido), MAX_IDS_POR_PETICION):
        lote = ids_partido[inicio : inicio + MAX_IDS_POR_PETICION]
        partidos.extend(
            _consultar_api(
                api_key,
                API_MATCHES_URL,
                {"ids": ",".join(str(partido_id) for partido_id in lote)},
            )
        )
    return partidos


def enriquecer_marcadores_partidos(
    api_key: str,
    partidos_api: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Completa marcadores ausentes en partidos finalizados."""
    por_id: dict[int, dict[str, Any]] = {
        partido["id"]: dict(partido)
        for partido in partidos_api
        if partido.get("id") is not None
    }
    incompletos = [
        partido_id
        for partido_id, partido in por_id.items()
        if marcador_final_incompleto(partido)
    ]
    if not incompletos:
        return partidos_api, 0

    enriquecidos_ids: set[int] = set()

    for partido in consultar_partidos_finalizados(api_key):
        partido_id = partido.get("id")
        if partido_id not in incompletos or not extraer_marcador_final(partido):
            continue
        por_id[partido_id] = fusionar_partido_api(por_id[partido_id], partido)
        enriquecidos_ids.add(partido_id)

    incompletos = [
        partido_id
        for partido_id in incompletos
        if marcador_final_incompleto(por_id[partido_id])
    ]
    if incompletos:
        for partido in consultar_partidos_por_ids(api_key, incompletos):
            partido_id = partido.get("id")
            if partido_id not in por_id or not extraer_marcador_final(partido):
                continue
            por_id[partido_id] = fusionar_partido_api(por_id[partido_id], partido)
            enriquecidos_ids.add(partido_id)

    partidos_enriquecidos = [
        por_id[partido["id"]] if partido.get("id") in por_id else partido
        for partido in partidos_api
    ]
    return partidos_enriquecidos, len(enriquecidos_ids)


def consultar_partidos_api(api_key: str) -> list[dict[str, Any]]:
    """Consulta el Mundial y completa marcadores si la lista base viene incompleta."""
    partidos = consultar_lista_competicion(api_key)
    partidos, _ = enriquecer_marcadores_partidos(api_key, partidos)
    return partidos


def formatear_partido(partido: dict[str, Any]) -> str:
    """Devuelve una etiqueta legible para logs."""
    return f"{partido['local']} vs {partido['visitante']}"


def actualizar_resultados(
    partidos: list[dict[str, Any]],
    partidos_api: list[dict[str, Any]],
    alias: dict[str, str | list[str]],
    resultados_actuales: list[Any],
    marcadores_actuales: list[dict[str, int] | None],
) -> tuple[list[Any], list[dict[str, int] | None], dict[str, int]]:
    """Genera resultados y marcadores conservando el orden de partidos.json."""
    nuevos_resultados = list(resultados_actuales)
    nuevos_marcadores = list(marcadores_actuales)
    estadisticas = {
        "encontrados": 0,
        "finalizados": 0,
        "pendientes": 0,
        "actualizados": 0,
        "sin_emparejar": 0,
    }
    api_usados: set[int] = set()

    for indice, partido in enumerate(partidos):
        etiqueta = formatear_partido(partido)
        partido_api, motivo = diagnosticar_partido(partido, partidos_api, alias)

        if partido_api is None:
            estadisticas["sin_emparejar"] += 1
            print(f"[ERROR] {etiqueta} → No encontrado", file=sys.stderr)
            print(f"        Motivo: {motivo}", file=sys.stderr)
            continue

        api_id = partido_api.get("id")
        if api_id in api_usados:
            print(
                f"[WARN] {etiqueta} → Emparejado con partido API duplicado (id={api_id})",
                file=sys.stderr,
            )
        if api_id is not None:
            api_usados.add(api_id)

        estadisticas["encontrados"] += 1
        resultado = resultado_entrada_desde_api(partido, partido_api)
        home_api = nombre_equipo_api(partido_api, "home") or "?"
        away_api = nombre_equipo_api(partido_api, "away") or "?"

        if resultado is None:
            estadisticas["pendientes"] += 1
            nuevos_resultados[indice] = None
            nuevos_marcadores[indice] = None
            print(
                f"[OK] {etiqueta} → Emparejado con {home_api} vs {away_api} (PENDIENTE)"
            )
            continue

        estadisticas["finalizados"] += 1
        if nuevos_resultados[indice] != resultado:
            estadisticas["actualizados"] += 1
        nuevos_resultados[indice] = resultado
        nuevos_marcadores[indice] = marcador_desde_api(partido_api)
        marcador_txt = nuevos_marcadores[indice]
        extra = (
            f" ({marcador_txt['home']}-{marcador_txt['away']})"
            if marcador_txt
            else ""
        )
        print(
            f"[OK] {etiqueta} → Emparejado con {home_api} vs {away_api} → "
            f"{resultado}{extra}{_etiqueta_clasifica(resultado)}"
        )

    return nuevos_resultados, nuevos_marcadores, estadisticas


def _etiqueta_clasifica(resultado: Any) -> str:
    """Texto auxiliar para logs de eliminatoria."""
    if isinstance(resultado, dict) and resultado.get("clasifica"):
        return f" (clasifica {resultado['clasifica']})"
    return ""


def mostrar_resumen(
    total_partidos: int,
    total_api: int,
    total_api_grupos: int,
    estadisticas: dict[str, int],
    marcadores_enriquecidos: int = 0,
) -> None:
    """Imprime el resumen final."""
    print()
    print(f"Partidos leídos: {total_partidos}")
    print(
        f"Partidos encontrados en API: "
        f"{estadisticas['encontrados']}/{total_partidos}"
    )
    print(f"Partidos finalizados: {estadisticas['finalizados']}")
    print(f"Partidos pendientes: {estadisticas['pendientes']}")
    print(f"Partidos actualizados: {estadisticas['actualizados']}")
    if marcadores_enriquecidos:
        print(f"Marcadores enriquecidos desde API: {marcadores_enriquecidos}")
    if estadisticas["sin_emparejar"]:
        print(f"Partidos sin emparejar: {estadisticas['sin_emparejar']}")
    print(f"Partidos en API (total): {total_api}")
    print(f"Partidos en API (fase de grupos): {total_api_grupos}")


def main() -> int:
    """Punto de entrada del script."""
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        print(
            f"Error: falta la variable de entorno {API_KEY_ENV}. "
            "No se actualizó resultados.json.",
            file=sys.stderr,
        )
        return 0

    try:
        partidos = cargar_json(PARTIDOS_FILE)
        alias = cargar_json(ALIAS_FILE)
        if not isinstance(partidos, list) or not partidos:
            raise ValueError("partidos.json debe contener un array de partidos.")
        if not isinstance(alias, dict):
            raise ValueError("equipos_alias.json debe ser un objeto JSON.")

        resultados_actuales = cargar_resultados_actuales(len(partidos))
        marcadores_actuales = cargar_marcadores_actuales(len(partidos))
        partidos_api_total = consultar_lista_competicion(api_key)
        last_api_check = instante_utc_iso()
        partidos_api_total, marcadores_enriquecidos = enriquecer_marcadores_partidos(
            api_key,
            partidos_api_total,
        )
        partidos_api = partidos_api_total
        nuevos_resultados, nuevos_marcadores, estadisticas = actualizar_resultados(
            partidos,
            partidos_api,
            alias,
            resultados_actuales,
            marcadores_actuales,
        )
        guardar_json(nuevos_resultados, RESULTADOS_FILE)
        guardar_json(nuevos_marcadores, MARCADORES_FILE)
        guardar_estadisticas_ejecucion(
            last_api_check,
            estadisticas,
            marcadores_enriquecidos,
        )
        mostrar_resumen(
            len(partidos),
            len(partidos_api_total),
            contar_partidos_grupos_api(partidos_api),
            estadisticas,
            marcadores_enriquecidos,
        )
        if estadisticas["sin_emparejar"]:
            print(
                f"Aviso: {estadisticas['sin_emparejar']} partidos sin emparejar. "
                "Ejecuta scripts/auditar_emparejamiento.py para más detalle.",
                file=sys.stderr,
            )
        return 0
    except requests.RequestException as exc:
        print(
            f"Error de API: no se actualizó resultados.json ({exc}).",
            file=sys.stderr,
        )
        return 0
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
