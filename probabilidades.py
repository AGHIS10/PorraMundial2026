"""Proveedor de probabilidades de partidos para la proyección Monte Carlo.

El simulador NUNCA conoce el origen de las probabilidades: solo consume un
contrato (``ProveedorProbabilidades``). Hoy las probabilidades son manuales
(fichero JSON + valores por defecto). Mañana podrán venir de ELO, casas de
apuestas, Football-Data, una IA o cualquier otra fuente, sin tocar el motor.

Contrato de salida (por partido):

    # Distribución separada (resultado y clasifica independientes):
    {
      "resultado": {"1": 0.47, "X": 0.28, "2": 0.25},
      "clasifica": {"1": 0.59, "2": 0.41}
    }

    # Distribución conjunta (dependencia explícita, recomendado para eliminatorias):
    {
      "resultado": {"1": 0.47, "X": 0.44, "2": 0.09},   # marginal derivada
      "clasifica": {"1": 0.59, "2": 0.41},               # marginal derivada
      "conjunta": [
        {"resultado": "1", "clasifica": "1", "prob": 0.47},
        {"resultado": "X", "clasifica": "1", "prob": 0.12},
        {"resultado": "X", "clasifica": "2", "prob": 0.32},
        {"resultado": "2", "clasifica": "2", "prob": 0.09}
      ]
    }

- Cuando ``"conjunta"`` está presente, el motor la usa directamente. Las
  combinaciones imposibles (p.ej. victoria local + clasificado visitante)
  simplemente no aparecen en la lista, eliminando la simplificación de
  independencia del modelo separado.
- ``resultado`` y ``clasifica`` siempre se incluyen (marginales) para
  compatibilidad con código que no usa la distribución conjunta.
- La confianza o incertidumbre del proveedor es responsabilidad de cada
  implementación: puede ajustar sus probabilidades internamente (p.ej.
  mezclar con distribución uniforme cuando hay poca información) sin que
  el motor Monte Carlo necesite conocer ese detalle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

RESULTADOS = ("1", "X", "2")
CLASIFICA = ("1", "2")

# Distribuciones por defecto cuando un partido no tiene probabilidades propias.
# Ligera ventaja local en el resultado; clasificación equilibrada (la prórroga
# y los penaltis hacen el pase a una eliminatoria prácticamente 50/50).
DEFAULT_RESULTADO: dict[str, float] = {"1": 0.40, "X": 0.27, "2": 0.33}
DEFAULT_CLASIFICA: dict[str, float] = {"1": 0.50, "2": 0.50}


@runtime_checkable
class ProveedorProbabilidades(Protocol):
    """Contrato mínimo que el simulador consume."""

    def distribucion(self, partido: Any) -> dict[str, dict[str, float]]:
        """Devuelve la distribución normalizada de un partido."""
        ...


def _normalizar(dist: dict[str, float], claves: tuple[str, ...]) -> dict[str, float]:
    """Valida claves y normaliza una distribución para que sume 1."""
    limpio: dict[str, float] = {}
    for clave in claves:
        valor = dist.get(clave, 0.0)
        try:
            numero = float(valor)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Probabilidad inválida para '{clave}': {valor!r}.") from exc
        if numero < 0:
            raise ValueError(f"Probabilidad negativa para '{clave}': {numero}.")
        limpio[clave] = numero

    total = sum(limpio.values())
    if total <= 0:
        raise ValueError(f"La distribución {dist!r} no tiene masa positiva.")

    return {clave: valor / total for clave, valor in limpio.items()}


def _normalizar_conjunta(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Valida y normaliza una distribución conjunta resultado × clasifica.

    Acepta la lista del JSON:
        [{"resultado": "1", "clasifica": "1", "prob": 0.46}, …]

    Elimina entradas con prob ≤ 0 (combinaciones imposibles) y normaliza el
    resto a que sumen 1. Lanza ``ValueError`` si los valores son inválidos.
    """
    validos: list[dict[str, Any]] = []
    total = 0.0
    for item in items:
        r = str(item.get("resultado", ""))
        c = str(item.get("clasifica", ""))
        try:
            prob = float(item.get("prob", 0.0))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"'prob' inválida en distribución conjunta: {item!r}.") from exc
        if r not in RESULTADOS:
            raise ValueError(f"'resultado' inválido en distribución conjunta: {r!r}.")
        if c not in CLASIFICA:
            raise ValueError(f"'clasifica' inválido en distribución conjunta: {c!r}.")
        if prob < 0:
            raise ValueError(f"Probabilidad negativa en distribución conjunta: {prob}.")
        if prob > 0:
            validos.append({"resultado": r, "clasifica": c, "prob": prob})
            total += prob
    if total <= 0:
        raise ValueError("La distribución conjunta no tiene masa positiva.")
    return [
        {"resultado": x["resultado"], "clasifica": x["clasifica"], "prob": x["prob"] / total}
        for x in validos
    ]


class ProveedorManual:
    """Probabilidades manuales: mapa por id de partido + valores por defecto.

    El mapa admite claves int o str (id del partido). Cada entrada puede
    definir ``resultado`` y/o ``clasifica``; lo que falte usa el valor por
    defecto. Así se pueden ajustar solo los partidos relevantes.
    """

    def __init__(
        self,
        mapa_por_id: dict[Any, dict[str, dict[str, float]]] | None = None,
        *,
        resultado_por_defecto: dict[str, float] | None = None,
        clasifica_por_defecto: dict[str, float] | None = None,
    ) -> None:
        self._mapa = {str(clave): valor for clave, valor in (mapa_por_id or {}).items()}
        self._res_defecto = _normalizar(
            resultado_por_defecto or DEFAULT_RESULTADO, RESULTADOS
        )
        self._cls_defecto = _normalizar(
            clasifica_por_defecto or DEFAULT_CLASIFICA, CLASIFICA
        )

    def distribucion(self, partido: Any) -> dict[str, Any]:
        entrada = self._mapa.get(str(_id_partido(partido)), {})

        # ── Distribución conjunta (elimina la simplificación de independencia) ──
        if isinstance(entrada.get("conjunta"), list):
            conjunta = _normalizar_conjunta(entrada["conjunta"])
            # Derivar marginales para compatibilidad con código que no usa conjunta.
            marginal_r: dict[str, float] = {r: 0.0 for r in RESULTADOS}
            marginal_c: dict[str, float] = {c: 0.0 for c in CLASIFICA}
            for item in conjunta:
                marginal_r[item["resultado"]] += item["prob"]
                marginal_c[item["clasifica"]] += item["prob"]
            return {
                "resultado": marginal_r,
                "clasifica": marginal_c,
                "conjunta": conjunta,
            }

        # ── Distribución separada (modelo de independencia original) ────────────
        resultado = entrada.get("resultado")
        clasifica = entrada.get("clasifica")
        return {
            "resultado": (
                _normalizar(resultado, RESULTADOS)
                if isinstance(resultado, dict)
                else dict(self._res_defecto)
            ),
            "clasifica": (
                _normalizar(clasifica, CLASIFICA)
                if isinstance(clasifica, dict)
                else dict(self._cls_defecto)
            ),
        }


def _id_partido(partido: Any) -> Any:
    """Obtiene el id de un partido tanto si es objeto como dict."""
    if isinstance(partido, dict):
        return partido.get("id")
    return getattr(partido, "id", None)


def cargar_proveedor(ruta: Path | None) -> ProveedorProbabilidades:
    """Carga un proveedor manual desde JSON; si no existe, usa los defaults."""
    if ruta is not None and ruta.exists():
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        if not isinstance(datos, dict):
            raise ValueError(f"{ruta.as_posix()} debe ser un objeto {{id: distribución}}.")
        return ProveedorManual(datos)
    return ProveedorManual()
