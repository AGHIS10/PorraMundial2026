"""Motor de clasificación de la porra del Mundial 2026."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

PROYECTO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_DIR))

from puntuacion_fases import (  # noqa: E402
    PUNTOS_MAXIMOS,
    TOTAL_PARTIDOS,
    asignar_fase_y_peso,
    validar_cantidad_partidos,
    validar_fase_y_peso,
    validar_integridad_partidos,
)
from reparto_premios import (  # noqa: E402
    FilaPremio,
    calcular_reparto_economico,
    premios_a_dict,
)

PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
RESULTADOS_FILE = PROYECTO_DIR / "resultados.json"
PARTICIPANTES_DIR = PROYECTO_DIR / "participantes"
CLASIFICACION_FILE = PROYECTO_DIR / "clasificacion.json"
PREMIOS_FILE = PROYECTO_DIR / "premios.json"
DOCS_DIR = PROYECTO_DIR / "docs"
DOCS_CLASIFICACION_FILE = DOCS_DIR / "clasificacion.json"
DOCS_CLASIFICACION_JS_FILE = DOCS_DIR / "clasificacion.js"
DOCS_PREMIOS_FILE = DOCS_DIR / "premios.json"
DOCS_PREMIOS_JS_FILE = DOCS_DIR / "premios.js"
DOCS_PARTIDOS_FILE = DOCS_DIR / "partidos.json"
DOCS_PARTIDOS_JS_FILE = DOCS_DIR / "partidos.js"
DOCS_INDEX_FILE = DOCS_DIR / "index.html"

CAMPOS_PARTIDO = ("id", "fecha", "hora", "local", "visitante", "fase", "peso")


@dataclass(frozen=True)
class Partido:
    id: int
    fecha: str
    hora: str
    local: str
    visitante: str
    fase: str
    peso: int


@dataclass(frozen=True)
class Participante:
    nombre: str
    pronosticos: list[str | None]


@dataclass(frozen=True)
class EntradaClasificacion:
    nombre: str
    aciertos: int
    puntos: int


@dataclass(frozen=True)
class FilaClasificacion:
    posicion: int
    nombre: str
    aciertos: int
    puntos: int


@dataclass(frozen=True)
class ContextoPorra:
    partidos: list[Partido]
    resultados: list[str | None]


class EstrategiaPuntuacion(Protocol):
    """Contrato para distintos sistemas de puntuación."""

    def puntos_por_partido(self, indice_partido: int) -> int:
        """Devuelve los puntos otorgados por acertar un partido concreto."""


class PuntuacionPorPeso:
    """Otorga los puntos definidos en el peso de cada partido."""

    def __init__(self, partidos: list[Partido]) -> None:
        self._partidos = partidos

    def puntos_por_partido(self, indice_partido: int) -> int:
        return self._partidos[indice_partido].peso


def cargar_json(ruta: Path) -> Any:
    """Carga un fichero JSON."""
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró {ruta.as_posix()}.")

    try:
        with ruta.open(encoding="utf-8") as archivo:
            return json.load(archivo)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {ruta.as_posix()}: {exc}") from exc


def cargar_partidos(ruta: Path) -> tuple[list[Partido], list[str]]:
    """Carga, valida y normaliza el fichero de partidos."""
    datos = cargar_json(ruta)

    if not isinstance(datos, list) or not datos:
        raise ValueError(f"{ruta.as_posix()} debe ser un array de partidos.")

    advertencias = validar_cantidad_partidos(len(datos))
    partidos: list[Partido] = []
    ids: list[int] = []

    for indice, entrada in enumerate(datos, start=1):
        if not isinstance(entrada, dict):
            raise ValueError(f"Partido {indice} no es un objeto JSON válido.")

        faltantes = [campo for campo in CAMPOS_PARTIDO if campo not in entrada]
        if faltantes:
            raise ValueError(
                f"Partido {indice} incompleto: faltan {', '.join(faltantes)}."
            )

        partido_id = int(entrada["id"])
        ids.append(partido_id)
        fase_archivo = str(entrada["fase"])
        peso_archivo = int(entrada["peso"])

        advertencias.extend(validar_fase_y_peso(partido_id, fase_archivo, peso_archivo))

        fase, peso = asignar_fase_y_peso(partido_id)
        partidos.append(
            Partido(
                id=partido_id,
                fecha=str(entrada["fecha"]),
                hora=str(entrada["hora"]),
                local=str(entrada["local"]),
                visitante=str(entrada["visitante"]),
                fase=fase,
                peso=peso,
            )
        )

    advertencias.extend(validar_integridad_partidos(ids))
    return partidos, advertencias


def cargar_resultados(ruta: Path) -> list[str | None]:
    """Carga y valida el fichero de resultados."""
    datos = cargar_json(ruta)

    if not isinstance(datos, list):
        raise ValueError(f"{ruta.as_posix()} debe ser un array de resultados.")

    return datos


def cargar_participante(ruta: Path) -> Participante:
    """Carga y valida un fichero de participante."""
    datos = cargar_json(ruta)

    if not isinstance(datos, dict):
        raise ValueError("El fichero debe ser un objeto JSON.")

    nombre = datos.get("nombre")
    pronosticos = datos.get("pronosticos")

    if not isinstance(nombre, str) or not nombre.strip():
        raise ValueError("Falta el campo 'nombre' o no es válido.")

    if not isinstance(pronosticos, list):
        raise ValueError("Falta el campo 'pronosticos' o no es un array.")

    return Participante(nombre=nombre, pronosticos=pronosticos)


def validar_coherencia_longitudes(
    total_partidos: int,
    total_resultados: int,
    total_pronosticos: int,
    nombre_participante: str | None = None,
) -> None:
    """Comprueba que partidos, resultados y pronósticos tengan la misma longitud."""
    if total_partidos == total_resultados == total_pronosticos:
        return

    detalle = (
        f"partidos: {total_partidos}, "
        f"resultados: {total_resultados}, "
        f"pronosticos: {total_pronosticos}"
    )
    if nombre_participante:
        raise ValueError(
            f"ERROR: longitud inconsistente para {nombre_participante} ({detalle})"
        )

    raise ValueError(f"ERROR: longitud inconsistente ({detalle})")


def contar_aciertos(
    pronosticos: list[str | None],
    resultados: list[str | None],
) -> int:
    """Cuenta aciertos solo en partidos con resultado conocido."""
    aciertos = 0
    for pronostico, resultado in zip(pronosticos, resultados):
        if resultado is None:
            continue
        if pronostico == resultado:
            aciertos += 1
    return aciertos


def calcular_puntos(
    pronosticos: list[str | None],
    resultados: list[str | None],
    estrategia: EstrategiaPuntuacion,
) -> int:
    """Calcula puntos partido a partido para facilitar pesos por ronda."""
    puntos = 0
    for indice, (pronostico, resultado) in enumerate(zip(pronosticos, resultados)):
        if resultado is None:
            continue
        if pronostico == resultado:
            puntos += estrategia.puntos_por_partido(indice)
    return puntos


def evaluar_participante(
    participante: Participante,
    contexto: ContextoPorra,
    estrategia: EstrategiaPuntuacion,
) -> EntradaClasificacion:
    """Calcula aciertos y puntos de un participante."""
    validar_coherencia_longitudes(
        len(contexto.partidos),
        len(contexto.resultados),
        len(participante.pronosticos),
        participante.nombre,
    )
    aciertos = contar_aciertos(participante.pronosticos, contexto.resultados)
    puntos = calcular_puntos(
        participante.pronosticos,
        contexto.resultados,
        estrategia,
    )
    return EntradaClasificacion(
        nombre=participante.nombre,
        aciertos=aciertos,
        puntos=puntos,
    )


def ordenar_clasificacion(
    entradas: list[EntradaClasificacion],
) -> list[EntradaClasificacion]:
    """Ordena por puntos, aciertos y nombre. Sin posiciones compartidas."""
    return sorted(
        entradas,
        key=lambda entrada: (-entrada.puntos, -entrada.aciertos, entrada.nombre),
    )


def asignar_posiciones(
    entradas_ordenadas: list[EntradaClasificacion],
) -> list[FilaClasificacion]:
    """Enumera posiciones de forma secuencial."""
    return [
        FilaClasificacion(
            posicion=indice,
            nombre=entrada.nombre,
            aciertos=entrada.aciertos,
            puntos=entrada.puntos,
        )
        for indice, entrada in enumerate(entradas_ordenadas, start=1)
    ]


def filas_a_dict(filas: list[FilaClasificacion]) -> list[dict[str, Any]]:
    """Convierte filas de clasificación a diccionarios serializables."""
    return [
        {
            "posicion": fila.posicion,
            "nombre": fila.nombre,
            "aciertos": fila.aciertos,
            "puntos": fila.puntos,
        }
        for fila in filas
    ]


def partidos_a_dict(partidos: list[Partido]) -> list[dict[str, Any]]:
    """Convierte partidos a diccionarios serializables."""
    return [
        {
            "id": partido.id,
            "fecha": partido.fecha,
            "hora": partido.hora,
            "local": partido.local,
            "visitante": partido.visitante,
            "fase": partido.fase,
            "peso": partido.peso,
        }
        for partido in partidos
    ]


def guardar_json(contenido: Any, ruta: Path) -> None:
    """Escribe contenido en un fichero JSON."""
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def guardar_modulo_js(
    variable: str,
    contenido: Any,
    ruta: Path,
) -> None:
    """Escribe datos como módulo JS global."""
    with ruta.open("w", encoding="utf-8") as archivo:
        archivo.write(f"window.{variable} = ")
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write(";\n")


def generar_build_id() -> str:
    """Genera un identificador de build para invalidar caché del frontend."""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def actualizar_cache_bust(html: str, build_id: str) -> str:
    """Actualiza meta app-build y parámetros ?v= de los assets estáticos."""
    html = re.sub(
        r'(<meta name="app-build" content=")[^"]*(")',
        rf"\g<1>{build_id}\2",
        html,
        count=1,
    )
    return re.sub(r"\?v=\d+", f"?v={build_id}", html)


def actualizar_script_embebido(
    html: str,
    script_id: str,
    contenido: Any,
) -> str | None:
    """Actualiza un bloque JSON embebido en index.html."""
    marcador_inicio = f'<script type="application/json" id="{script_id}">'
    marcador_fin = "</script>"

    inicio = html.find(marcador_inicio)
    fin = html.find(marcador_fin, inicio)
    if inicio == -1 or fin == -1:
        return None

    json_embebido = json.dumps(contenido, ensure_ascii=False, indent=2)
    bloque = f"{marcador_inicio}\n{json_embebido}\n  {marcador_fin}"
    return html[:inicio] + bloque + html[fin + len(marcador_fin):]


def actualizar_index_html(
    clasificacion: list[dict[str, Any]],
    premios: list[dict[str, Any]],
    ruta: Path,
) -> None:
    """Actualiza los datos embebidos de clasificación y premios en index.html."""
    html = ruta.read_text(encoding="utf-8")
    html_clasificacion = actualizar_script_embebido(html, "clasificacion-data", clasificacion)
    if html_clasificacion is not None:
        html = html_clasificacion

    html_premios = actualizar_script_embebido(html, "premios-data", premios)
    if html_premios is not None:
        html = html_premios

    html = actualizar_cache_bust(html, generar_build_id())
    ruta.write_text(html, encoding="utf-8")


def sincronizar_docs(
    filas: list[FilaClasificacion],
    premios: list[FilaPremio],
    partidos: list[Partido],
) -> None:
    """Sincroniza clasificación, premios y partidos con el frontend en docs/."""
    if not DOCS_DIR.exists():
        return

    clasificacion = filas_a_dict(filas)
    premios_dict = premios_a_dict(premios)
    partidos_dict = partidos_a_dict(partidos)

    guardar_json(clasificacion, DOCS_CLASIFICACION_FILE)
    guardar_modulo_js("__CLASIFICACION__", clasificacion, DOCS_CLASIFICACION_JS_FILE)
    guardar_json(premios_dict, DOCS_PREMIOS_FILE)
    guardar_modulo_js("__PREMIOS__", premios_dict, DOCS_PREMIOS_JS_FILE)
    guardar_json(partidos_dict, DOCS_PARTIDOS_FILE)
    guardar_modulo_js("__PARTIDOS__", partidos_dict, DOCS_PARTIDOS_JS_FILE)

    if DOCS_INDEX_FILE.exists():
        actualizar_index_html(clasificacion, premios_dict, DOCS_INDEX_FILE)


def listar_participantes(directorio: Path) -> list[Path]:
    """Devuelve todos los JSON de participantes ordenados alfabéticamente."""
    return sorted(directorio.glob("*.json"))


def procesar_participantes(
    directorio: Path,
    contexto: ContextoPorra,
    estrategia: EstrategiaPuntuacion,
) -> tuple[list[EntradaClasificacion], list[tuple[str, str]]]:
    """Carga participantes válidos e ignora los corruptos con advertencia."""
    if not directorio.exists():
        raise FileNotFoundError(f"No se encontró la carpeta {directorio.as_posix()}/.")

    validar_coherencia_longitudes(
        len(contexto.partidos),
        len(contexto.resultados),
        len(contexto.resultados),
    )

    entradas: list[EntradaClasificacion] = []
    advertencias: list[tuple[str, str]] = []

    for ruta in listar_participantes(directorio):
        try:
            participante = cargar_participante(ruta)
            entradas.append(evaluar_participante(participante, contexto, estrategia))
        except ValueError as exc:
            advertencias.append((ruta.stem, str(exc)))

    return entradas, advertencias


def mostrar_advertencias_participantes(advertencias: list[tuple[str, str]]) -> None:
    """Muestra participantes ignorados."""
    for nombre, motivo in advertencias:
        print(f"⚠ Participante {nombre} ignorado: {motivo}", file=sys.stderr)


def mostrar_advertencias_partidos(advertencias: list[str]) -> None:
    """Muestra advertencias de validación de partidos."""
    for mensaje in advertencias:
        print(f"⚠ {mensaje}", file=sys.stderr)


def mostrar_resumen(
    contexto: ContextoPorra,
    total_participantes: int,
    filas: list[FilaClasificacion],
    ruta_salida: Path,
) -> None:
    """Imprime el resumen final en consola."""
    print(f"Partidos cargados: {len(contexto.partidos)}/{TOTAL_PARTIDOS}")
    print(f"Puntos máximos posibles: {PUNTOS_MAXIMOS}")
    print(f"Resultados cargados: {len(contexto.resultados)} partidos")
    print(f"Participantes procesados: {total_participantes}\n")

    for fila in filas:
        print(
            f"{fila.posicion}. {fila.nombre} - "
            f"{fila.puntos} puntos ({fila.aciertos} aciertos)"
        )

    print(f"\nClasificación guardada en {ruta_salida.as_posix()}")


def main() -> int:
    """Punto de entrada del script."""
    try:
        partidos, advertencias_partidos = cargar_partidos(PARTIDOS_FILE)
        resultados = cargar_resultados(RESULTADOS_FILE)
        contexto = ContextoPorra(partidos=partidos, resultados=resultados)
        estrategia = PuntuacionPorPeso(partidos)
        entradas, advertencias_participantes = procesar_participantes(
            PARTICIPANTES_DIR,
            contexto,
            estrategia,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    guardar_json(partidos_a_dict(partidos), PARTIDOS_FILE)
    mostrar_advertencias_partidos(advertencias_partidos)
    mostrar_advertencias_participantes(advertencias_participantes)

    if not entradas:
        print("No hay participantes válidos para clasificar.", file=sys.stderr)
        return 1

    filas = asignar_posiciones(ordenar_clasificacion(entradas))
    premios = calcular_reparto_economico(filas)
    guardar_json(filas_a_dict(filas), CLASIFICACION_FILE)
    guardar_json(premios_a_dict(premios), PREMIOS_FILE)
    sincronizar_docs(filas, premios, partidos)
    mostrar_resumen(contexto, len(entradas), filas, CLASIFICACION_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
