"""Actualiza partidos.json con los dieciseisavos reales desde un CSV de porra."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROYECTO_DIR = Path(__file__).resolve().parent.parent
PARTIDOS_FILE = PROYECTO_DIR / "partidos.json"
INPUT_DIR = PROYECTO_DIR.parent / "mundial-json-converter" / "input"
CLASIFICA_HEADER = "CLASIFICA"
INICIO_INDICE = 72  # partido id 73
FIN_INDICE = 88  # exclusivo, partido id 88

TEAM_NAME_PATTERN = re.compile(r"[A-Za-zÀ-ÿ]")
NOMBRES_CANONICOS = {
    "Bosnia": "Bosnia y Herzegovina",
}


def cargar_json(ruta: Path) -> Any:
    with ruta.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def guardar_json(contenido: Any, ruta: Path) -> None:
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(contenido, archivo, ensure_ascii=False, indent=2)
        archivo.write("\n")


def normalizar_equipo(value: Any) -> str:
    if pd.isna(value):
        raise ValueError("Nombre de equipo vacío en el CSV.")

    texto = str(value).strip()
    coincidencia = TEAM_NAME_PATTERN.search(texto)
    if coincidencia:
        texto = texto[coincidencia.start() :].strip()
    return NOMBRES_CANONICOS.get(texto, texto)


def normalizar_fecha(value: Any) -> str:
    if pd.isna(value):
        raise ValueError("Fecha vacía en el CSV.")
    texto = str(value).strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no reconocido: {texto}")


def leer_partidos_csv(csv_path: Path) -> list[dict[str, str]]:
    df = pd.read_csv(csv_path, encoding="utf-8", header=None)
    if df.shape[1] < 4:
        raise ValueError(f"{csv_path.name} no tiene columnas suficientes.")

    inicio = 1
    if str(df.iloc[0, 4 if df.shape[1] >= 5 else 0]).strip().upper() == CLASIFICA_HEADER:
        inicio = 1

    partidos: list[dict[str, str]] = []
    for _, fila in df.iloc[inicio:].iterrows():
        if pd.isna(fila[0]) and pd.isna(fila[1]):
            continue
        partidos.append(
            {
                "fecha": normalizar_fecha(fila[0]),
                "local": normalizar_equipo(fila[1]),
                "visitante": normalizar_equipo(fila[3]),
            }
        )

    esperados = FIN_INDICE - INICIO_INDICE
    if len(partidos) != esperados:
        raise ValueError(
            f"Se esperaban {esperados} partidos en {csv_path.name}, hay {len(partidos)}."
        )
    return partidos


def buscar_csv_dieciseisavos(directorio: Path) -> Path:
    candidatos = sorted(directorio.glob("*- 16.csv")) + sorted(directorio.glob("*-16.csv"))
    if not candidatos:
        raise FileNotFoundError(
            f"No se encontró ningún CSV de dieciseisavos en {directorio.as_posix()}/."
        )
    return candidatos[0]


def actualizar_partidos(partidos_csv: list[dict[str, str]]) -> list[dict[str, Any]]:
    partidos = cargar_json(PARTIDOS_FILE)
    if not isinstance(partidos, list) or len(partidos) < FIN_INDICE:
        raise ValueError("partidos.json incompleto.")

    for offset, datos_csv in enumerate(partidos_csv):
        indice = INICIO_INDICE + offset
        partido = partidos[indice]
        if partido.get("fase") != "dieciseisavos":
            raise ValueError(
                f"Partido id {partido.get('id')} en índice {indice} "
                f"no es dieciseisavos ({partido.get('fase')})."
            )
        partido["fecha"] = datos_csv["fecha"]
        partido["local"] = datos_csv["local"]
        partido["visitante"] = datos_csv["visitante"]

    guardar_json(partidos, PARTIDOS_FILE)
    return partidos[INICIO_INDICE:FIN_INDICE]


def main() -> int:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else buscar_csv_dieciseisavos(INPUT_DIR)
    try:
        partidos_csv = leer_partidos_csv(csv_path)
        actualizados = actualizar_partidos(partidos_csv)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"✓ {len(actualizados)} dieciseisavos cargados desde {csv_path.name}\n")
    for partido in actualizados:
        print(
            f"  id {partido['id']:>2} · {partido['fecha']} {partido['hora']} · "
            f"{partido['local']} vs {partido['visitante']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
