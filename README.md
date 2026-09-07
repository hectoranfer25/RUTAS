# IDS26-E5T8 — Simulador de flota vial

Proyecto full stack para la evaluación IDS26-E5T8.

## Arquitectura

- **Backend:** Python + FastAPI.
- **Frontend:** React + Vite + Leaflet / React-Leaflet.
- **Actualización:** polling cada 3 segundos.
- **Ruta:** grafo construido desde puntos consecutivos de `Routes`; Dijkstra con distancia geográfica como costo.
- **Simulación:** 5 camiones, velocidades reproducibles con semilla configurable.
- **Reporte:** media aritmética de las muestras y explicación heurística sin cifras inventadas.
- **Estado:** memoria del proceso; no requiere base de datos.


## Requisitos

- Python 3.11+
- Node.js 20+
- npm 10+

## 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Swagger:
`http://localhost:8000/docs`

Variables opcionales:

```env
DATA_FILE=data/input.json
RANDOM_SEED=5923
MIN_SPEED_KMH=22
MAX_SPEED_KMH=52
TICK_SECONDS=3
SNAP_MAX_METERS=2000
```

## 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Abrir la URL mostrada por Vite, normalmente `http://localhost:5173`.

Si el backend está en otra URL:

```env
VITE_API_URL=http://localhost:8000/api
```

## API

### `GET /api/routes`
Devuelve todos los tramos validados.

### `GET /api/locations`
Devuelve cargas, descargas y advertencias de validación.

### `POST /api/simulations/start`
Reinicia e inicia una ejecución con exactamente cinco camiones.

Respuesta simplificada:

```json
{
  "simulation_id": "....",
  "seed": 5923,
  "truck_ids": ["CA01", "CA02", "CA03", "CA04", "CA05"],
  "assignments": [...]
}
```

### `GET /api/simulations/current`
Consulta posiciones, velocidades, estado, timestamp y progreso.

### `GET /api/simulations/report`
Devuelve muestras, mínimo, máximo, promedio y muestras fuera de 25–50 km/h, además de la explicación heurística.

### `POST /api/simulations/reset`
Detiene la simulación y elimina el estado actual.

## Decisiones técnicas

La red se modela como un grafo de coordenadas. Cada pareja de puntos consecutivos de una polilínea genera una arista bidireccional cuyo costo es la distancia Haversine. Para seleccionar una ruta se ejecuta Dijkstra; en caso de empate se favorece el tramo final con menor `id_trm_cs`. Las ubicaciones se asocian al vértice vial más cercano dentro de `SNAP_MAX_METERS`, y una ubicación que no pueda asociarse o que quede en otro componente se reporta de forma controlada.

Se eligió polling cada 3 segundos porque satisface directamente el intervalo exigido y reduce la complejidad operacional frente a WebSocket/SSE para una simulación pequeña. Con más tiempo, SSE sería una buena alternativa para evitar solicitudes periódicas y entregar eventos de movimiento al navegador.

La simulación conserva el estado en memoria. Cada intervalo genera una velocidad pseudoaleatoria entre los límites configurables y avanza sobre la geometría acumulando distancia, nunca mediante una línea recta entre origen y destino. La semilla por defecto es `5923`, por lo que una ejecución puede reproducirse.

## Validaciones y manejo de errores

- JSON inválido: error controlado al iniciar.
- Colecciones faltantes: error de configuración.
- Coordenadas inválidas: se registran como advertencias y no se modifican silenciosamente.
- Tramos sin geometría suficiente: se excluyen de la red y se reportan.
- Menos de un par carga-descarga alcanzable: `422`.
- Excepción inesperada: `500` con mensaje consistente.

## Limitaciones

1. El estado desaparece al reiniciar el proceso.
2. El dataset de demostración debe reemplazarse por el JSON oficial para la entrega.
3. No hay autenticación porque la evaluación no la exige.
4. El despliegue público requiere configurar las variables de entorno y CORS del proveedor.

## Despliegue

### Backend
Puede desplegarse en Render, Railway, Fly.io u otro proveedor compatible con Python/Uvicorn.

Comando:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Frontend
Vercel:
```bash
npm install
npm run build
```
Configurar `VITE_API_URL` con la URL pública del backend.

## Criterios cubiertos

- 5 camiones con IDs estables.
- Movimiento cada 3 segundos.
- Velocidad 22–52 km/h configurable.
- Semilla 5923 configurable.
- Dijkstra sobre la red vial.
- Mapa Leaflet con colores de `Routes`.
- Cargas y descargas diferenciadas.
- Reporte por camión.
- Heurística en lenguaje humano.
- Estados de carga, error y ausencia de datos.
- Código `IDS26-E5T8` visible.

## Ejecución con Docker

El proyecto incluye `Dockerfile` para backend y frontend, además de `docker-compose.yml`. El frontend se sirve con Nginx y hace proxy de `/api` hacia el backend, por lo que no necesitas exponer el puerto 8000 al navegador.

### Requisitos

- Docker Engine 24+ recomendado.
- Docker Compose v2.

### Iniciar todo

Desde la raíz del proyecto:

```bash
docker compose up --build
```

Luego abrir:

```text
http://localhost:8081
```

La documentación de la API queda disponible en:

```text
http://localhost:8081/api/docs
```

El backend también responde internamente en `backend:8000` dentro de la red Docker.

### Ejecutar en segundo plano

```bash
docker compose up --build -d
```

Ver logs:

```bash
docker compose logs -f
```

Detener:

```bash
docker compose down
```

### Configuración

Puedes copiar `.env.example` como `.env` y ajustar, por ejemplo:

```env
RANDOM_SEED=5923
MIN_SPEED_KMH=22
MAX_SPEED_KMH=52
TICK_SECONDS=3
SNAP_MAX_METERS=2000
CORS_ORIGINS=http://localhost:8081
```

El dataset real de la evaluación está incluido en `backend/data/input.json`.
