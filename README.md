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
├── scripts/
│   └── calcular_clasificacion.py
├── docs/                    # Frontend (GitHub Pages)
│   ├── index.html
│   ├── styles.css
│   ├── app.js
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

### Características

- Tema oscuro premium con glassmorphism y gradientes sutiles
- Hero con estadísticas (participantes, líder, última actualización)
- Podio visual para el top 3
- Tabla de clasificación con animaciones y hover
- Diseño responsive optimizado para móvil
- Skeleton loading mientras carga el JSON
- Carga de `partidos.json` preparada para futuras vistas (detalle de jugador, estadísticas)

## Ordenación

La clasificación se ordena por:

1. Puntos (descendente)
2. Aciertos (descendente)
3. Nombre (ascendente)

No hay posiciones compartidas: cada participante recibe una posición única (1, 2, 3…).
