# Porra Mundial 2026

Sistema de gestión y clasificación de una porra del Mundial 2026.

## Estructura del proyecto

```
porra-mundial/
├── participantes/           # Pronósticos de cada participante (JSON)
│   ├── agus.json
│   ├── mario.json
│   └── ...
├── partidos.json            # Metadatos de los partidos
├── resultados.json          # Resultados reales de los partidos
├── clasificacion.json       # Clasificación generada (salida)
├── proyeccion.py            # Motor Monte Carlo (proyección del campeonato)
├── probabilidades.py        # Proveedor de probabilidades (desacoplado)
├── scripts/
│   ├── calcular_clasificacion.py
│   └── calcular_proyeccion.py
├── docs/                    # Frontend (GitHub Pages)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── config.js            # Configuración del frontend (analítica, etc.)
│   ├── analytics.js         # Carga dinámica de analítica
│   ├── clasificacion.json   # Sincronizado automáticamente
│   └── partidos.json        # Sincronizado automáticamente
└── README.md
```

Este módulo complementa el conversor CSV → JSON (`mundial-json-converter/`), que genera los ficheros de `participantes/` y `partidos.json` a partir de hojas de Google Sheets.

## Responsabilidad de cada fichero

| Fichero | Contenido |
|---------|-----------|
| `partidos.json` | Metadatos de cada partido (fecha, equipos, fase, peso) |
| `participantes/*.json` | Pronósticos de cada jugador |
| `resultados.json` | Resultados reales |
| `clasificacion.json` | Clasificación calculada |

## Formato de los JSON

### Partidos (`partidos.json`)

```json
[
  {
    "id": 1,
    "fecha": "2026-06-11",
    "hora": "21:00",
    "local": "México",
    "visitante": "Sudáfrica",
    "fase": "grupos",
    "peso": 1
  }
]
```

### Participante (`participantes/nombre.json`)

```json
{
  "nombre": "Agus",
  "pronosticos": [
    "1",
    "X",
    "2",
    "1",
    null,
    "2"
  ]
}
```

- Cada posición del array representa un partido.
- El orden es idéntico para todos los participantes y para `resultados.json`.
- `null` indica que el participante no ha pronosticado ese partido.

### Resultados (`resultados.json`)

```json
[
  "1",
  "X",
  "2",
  null,
  null,
  null
]
```

- Array con un resultado por partido, en el mismo orden que los pronósticos.
- `null` significa partido todavía no disputado.
- Solo se puntúan partidos cuyo resultado no sea `null`.

### Clasificación (`clasificacion.json`)

```json
[
  {
    "posicion": 1,
    "nombre": "Agus",
    "aciertos": 42,
    "puntos": 42
  },
  {
    "posicion": 2,
    "nombre": "Juan",
    "aciertos": 40,
    "puntos": 40
  }
]
```

## Sistema de puntuación

Cada acierto suma el **peso** del partido según su fase:

| Fase | Partidos | Peso | Máximo |
|------|----------|------|--------|
| Grupos | 72 | 1 | 72 |
| Dieciseisavos | 16 | 2 | 32 |
| Octavos | 8 | 4 | 32 |
| Cuartos | 4 | 8 | 32 |
| Semifinales | 2 | 16 | 32 |
| Tercer puesto | 1 | 25 | 25 |
| Final | 1 | 50 | 50 |

**Total: 104 partidos · Puntos máximos posibles: 275**

Durante el torneo pueden existir menos de 104 partidos en `partidos.json`. El sistema funciona con los disponibles y aplica los pesos automáticamente al completar el calendario.

Los aciertos y los puntos son independientes: un participante puede tener 45 aciertos y 123 puntos.

La lógica está en `puntuacion_fases.py` y `PuntuacionPorPeso` en `scripts/calcular_clasificacion.py`.

## Cómo ejecutar el script

Desde la raíz de `porra-mundial/`:

```bash
python scripts/calcular_clasificacion.py
```

Requisitos: Python 3.12+. No necesita dependencias externas.

Ejemplo de salida:

```
Partidos cargados: 71
Resultados cargados: 71 partidos
Participantes procesados: 2

1. Agus - 45 puntos
2. Mario - 30 puntos

Clasificación guardada en clasificacion.json
```

## Cómo añadir nuevos participantes

1. Exporta el pronóstico desde Google Sheets como CSV.
2. Conviértelo a JSON con el módulo `mundial-json-converter`.
3. Copia `output/partidos.json` a `porra-mundial/partidos.json` (si es la primera vez o hay nuevos partidos).
4. Copia el JSON del participante a `participantes/` (por ejemplo, `participantes/juan.json`).
5. Asegúrate de que partidos, resultados y pronósticos tengan la misma longitud.
6. Ejecuta `python scripts/calcular_clasificacion.py`.

Si un participante tiene longitud incorrecta o JSON inválido, se ignora y se muestra una advertencia:

```
⚠ Participante pedro ignorado: longitud incorrecta
```

## Cómo actualizar resultados

1. Edita `resultados.json`.
2. Sustituye los `null` por el resultado real (`"1"`, `"X"` o `"2"`) de cada partido disputado.
3. Mantén el orden de los partidos sin cambios.
4. Ejecuta de nuevo `python scripts/calcular_clasificacion.py`.

El fichero `clasificacion.json` se sobrescribe automáticamente con la clasificación actualizada. También se sincroniza a `docs/` para el frontend.

## Validación de coherencia

El motor comprueba que coincidan:

- número de partidos en `partidos.json`
- número de resultados en `resultados.json`
- número de pronósticos en cada participante

Si no coinciden:

```
ERROR: longitud inconsistente (partidos: 71, resultados: 71, pronosticos: 70)
```

## Frontend (docs/)

Interfaz premium para visualizar la clasificación en tiempo real.

### GitHub Pages

Configuración recomendada en el repositorio:

- **Branch:** `main`
- **Folder:** `/docs`

No requiere cambios adicionales en el proyecto.

### Cómo abrirlo en local

Desde la carpeta `docs/`:

```bash
cd docs
python3 -m http.server 8080
```

Abre en el navegador: `http://localhost:8080`

También puedes abrir `docs/index.html` directamente: los datos embebidos en `clasificacion.js` permiten ver la clasificación sin servidor.

### Analítica (Cloudflare Web Analytics)

El frontend usa [Cloudflare Web Analytics](https://developers.cloudflare.com/web-analytics/) para medir visitas en GitHub Pages. La integración es estática, sin dependencias ni build: el script se inserta dinámicamente desde JavaScript solo cuando está activado.

**Configuración:** editar `docs/config.js` (no hace falta tocar `index.html`).

```javascript
window.APP_CONFIG = {
  analytics: {
    enabled: true,
    cloudflareToken: "YOUR_CLOUDFLARE_ANALYTICS_TOKEN",
  },
};
```

| Campo | Descripción |
|-------|-------------|
| `enabled` | `true` activa la analítica; `false` no inserta nada en el DOM |
| `cloudflareToken` | Token del sitio en Cloudflare Web Analytics |

**Activar por primera vez:**

1. Crear la propiedad en [Cloudflare Web Analytics](https://dash.cloudflare.com/) → **Web Analytics** → **Add a site**.
2. Copiar el token que proporciona Cloudflare.
3. Pegarlo en `cloudflareToken` dentro de `docs/config.js`.
4. Confirmar que `enabled` es `true`.
5. Hacer commit y push a GitHub Pages.

Mientras el token siga siendo el placeholder `YOUR_CLOUDFLARE_ANALYTICS_TOKEN`, no se carga ningún script aunque `enabled` sea `true`.

**Desactivar:** poner `enabled: false` en `docs/config.js`.

La lógica de carga está en `docs/analytics.js` (`initAnalytics()`), llamada al arrancar la aplicación. Está preparada para añadir otros proveedores en el futuro sin modificar el HTML.

### Características

- Tema oscuro premium con glassmorphism y gradientes sutiles
- Hero con estadísticas (participantes, líder, última actualización)
- Podio visual para el top 3
- Tabla de clasificación con animaciones y hover
- Diseño responsive optimizado para móvil
- Skeleton loading mientras carga el JSON
- Carga de `partidos.json` preparada para futuras vistas (detalle de jugador, estadísticas)

## Proyección del campeonato (Monte Carlo)

Motor de simulación que estima cómo puede terminar la porra. No son porcentajes
inventados ni una IA prediciendo: es un Monte Carlo que simula miles de veces el
resto del Mundial reutilizando **exactamente el mismo motor de puntuación** que
la clasificación real.

Calcula dos métricas:

- 🏆 **Probabilidad de ganar la porra** — participan todos (incluidas las IA).
- 🥉 **Probabilidad de terminar en el Top 3** — solo participantes reales; GPT y
  GEMINI se eliminan de cada clasificación simulada *antes* de recortar el Top 3
  (criterio idéntico al del reparto de premios).

### Arquitectura

| Fichero | Responsabilidad |
|---------|-----------------|
| `proyeccion.py` | Motor Monte Carlo (lógica pura, vectorizada con NumPy) |
| `probabilidades.py` | Proveedor de probabilidades desacoplado del simulador |
| `scripts/calcular_proyeccion.py` | Orquestador: carga datos, simula y genera `proyeccion.json` |

El motor **no duplica reglas**: la puntuación usa `apuestas.puntos_apuesta` /
`contar_aciertos_apuesta` y el desempate replica el de `calcular_clasificacion`.
Solo sustituye los partidos pendientes por resultados simulados.

### Configuración

En `proyeccion.py`:

```python
SIMULACIONES = 20000   # desarrollo: 5000 · producción: 20000
RANDOM_SEED = 2026     # semilla fija → resultados reproducibles
```

Con la misma semilla y los mismos datos, la simulación produce **exactamente**
los mismos porcentajes. Solo cambian cuando cambian los resultados reales.

### Probabilidades de los partidos

El simulador nunca conoce el origen de las probabilidades: solo consume el
contrato `ProveedorProbabilidades`. Hoy son manuales; mañana pueden venir de
ELO, casas de apuestas, Football-Data o una IA sin tocar el motor.

Formato opcional de `probabilidades.json` (en la raíz de `porra-mundial/`),
indexado por id de partido:

```json
{
  "89": {
    "resultado": { "1": 0.47, "X": 0.28, "2": 0.25 },
    "clasifica": { "1": 0.59, "2": 0.41 }
  }
}
```

Lo que no se especifique usa los valores por defecto de `probabilidades.py`.
`clasifica` solo se aplica en eliminatorias.

### Salida (`docs/proyeccion.json`)

```json
{
  "generatedAt": "2026-06-20T20:30:00Z",
  "simulaciones": 20000,
  "seed": 2026,
  "partidos_pendientes": 32,
  "partidos_jugados": 80,
  "movimiento": {
    "hay_cambio": true,
    "desde": "2026-06-20T18:30:00Z",
    "ultimo_partido": { "id": 81, "local": "Bélgica", "visitante": "Senegal", "fase": "dieciseisavos", "marcador": "2-1" },
    "beneficiado": { "nombre": "SERGIO", "inicial": "S", "color": "#f5c518", "probabilidad": 11.14, "delta": 1.02 },
    "perjudicado": { "nombre": "GEMINI", "inicial": "G", "color": "#c0b3e0", "probabilidad": 7.70, "delta": -1.49 }
  },
  "campeon": [ { "nombre": "SERGIO", "inicial": "S", "color": "#f5c518", "es_ia": false, "probabilidad": 46.31, "delta": 1.02 } ],
  "top3":    [ { "nombre": "SERGIO", "inicial": "S", "color": "#f5c518", "probabilidad": 98.42, "delta": 0.40 } ],
  "distribucion": { "SERGIO": [46.31, 22.10, 11.0, 7.2, "…"] }
}
```

El esquema está diseñado para ampliarse sin romper compatibilidad:

- **`distribucion`** — probabilidad (%) de terminar en cada puesto del ranking
  global, por participante. Es el artefacto central: `campeon` no es más que la
  columna del puesto 1. Habilita métricas futuras (valor esperado del premio,
  probabilidad de quedar último, etc.) sin volver a tocar el motor.
- **`movimiento`** — evolución respecto a la proyección anterior. Solo se marca
  `hay_cambio: true` cuando se ha jugado algún partido nuevo (con semilla fija,
  sin nuevos resultados el delta es nulo, así que no hay ruido). Incluye el
  partido que provocó el cambio y el mayor beneficiado/perjudicado.
- **`delta`** — variación en puntos porcentuales de cada probabilidad respecto a
  la ejecución previa; el frontend lo muestra como ▲/▼ junto a cada jugador.

El frontend pinta una franja de *momentum* («cómo cambió el campeonato tras el
último partido») sobre las dos tarjetas de probabilidad.

Se recalcula automáticamente en el workflow tras cada actualización de
resultados (paso *Calcular proyeccion*, entre la evolución y la sincronización).

## Ordenación

La clasificación se ordena por:

1. Puntos (descendente)
2. Aciertos (descendente)
3. Nombre (ascendente)

No hay posiciones compartidas: cada participante recibe una posición única (1, 2, 3…).
