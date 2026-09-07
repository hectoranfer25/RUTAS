import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .data_loader import DataValidationError, load_and_validate
from .network import RoadNetwork
from .simulation import SimulationManager

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = os.getenv("DATA_FILE", str(BASE_DIR / "data" / "input.json"))
SEED = int(os.getenv("RANDOM_SEED") or "5923")
MIN_SPEED = float(os.getenv("MIN_SPEED_KMH") or "22")
MAX_SPEED = float(os.getenv("MAX_SPEED_KMH") or "52")
TICK = int(os.getenv("TICK_SECONDS") or "3")
SNAP_MAX = float(os.getenv("SNAP_MAX_METERS") or "2000")

try:
    routes, loads, dumps, warnings = load_and_validate(DATA_FILE)
    network = RoadNetwork(routes)
    manager = SimulationManager(routes, loads, dumps, network, SEED, MIN_SPEED, MAX_SPEED, TICK, SNAP_MAX)
except Exception as exc:
    routes, loads, dumps, warnings = [], [], [], [str(exc)]
    network = None
    manager = None

app = FastAPI(
    title="SIMULADOR DE RUTAS - CAMIONES",
    version="1.0.0",
    description="API de simulación de cinco camiones sobre una red vial.",
)

origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_ready():
    if manager is None or network is None:
        raise HTTPException(status_code=500, detail={"code": "DATA_ERROR", "message": "No se pudo cargar el dataset.", "warnings": warnings})


@app.get("/health")
def health():
    return {"status": "ok" if manager else "error", "code": "IDS26-E5T8", "warnings": warnings}


@app.get("/routes")
def get_routes():
    require_ready()
    return {"routes": routes, "warnings": warnings}


@app.get("/locations")
def get_locations():
    require_ready()
    return {"load": loads, "dump": dumps, "warnings": warnings}


@app.post("/simulations/start")
def start_simulation():
    require_ready()
    if MIN_SPEED < 0 or MAX_SPEED <= MIN_SPEED:
        raise HTTPException(status_code=500, detail={"code": "CONFIG_ERROR", "message": "Rango de velocidades inválido."})
    try:
        snapshot = manager.start()
        return {
            "simulation_id": snapshot["simulation_id"],
            "seed": snapshot["seed"],
            "truck_ids": [t["id"] for t in snapshot["trucks"]],
            "assignments": [
                {
                    "truck_id": t["id"],
                    "load_id": t["load_id"],
                    "dump_id": t["dump_id"],
                    "distance_km": t["distance_km"],
                } for t in snapshot["trucks"]
            ],
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "NO_ROUTE", "message": str(exc)}) from exc


@app.post("/simulations/reset")
def reset_simulation():
    require_ready()
    manager.reset()
    return {"status": "reset"}


@app.get("/simulations/current")
def current_simulation():
    require_ready()
    manager.tick_if_needed()
    snapshot = manager.snapshot()
    if not snapshot:
        return {"status": "idle", "trucks": []}
    return {"status": "running", **snapshot}


@app.get("/simulations/report")
def simulation_report():
    require_ready()
    manager.tick_if_needed()
    if not manager.state:
        return {"status": "idle", "report": []}
    report = manager.report()
    return {"status": "running", "report": report}
