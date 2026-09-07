from typing import Literal
from pydantic import BaseModel, Field


class Route(BaseModel):
    id_trm_cs: int
    nombre_tramo: str
    color: str
    points: list[list[float]]


class Location(BaseModel):
    id: int
    name: str
    coor: list[float]
    radio: int | None = None


class TruckState(BaseModel):
    id: str
    load_id: int
    load_name: str
    dump_id: int
    dump_name: str
    lat: float
    lon: float
    speed_kmh: float
    status: Literal["loading", "moving", "finished", "error"]
    timestamp: str
    progress: float = Field(ge=0, le=1)
    distance_km: float


class TruckReport(BaseModel):
    truck_id: str
    samples: int
    min_speed_kmh: float
    max_speed_kmh: float
    avg_speed_kmh: float
    outside_25_50_samples: int
    outside_25_50_percent: float
    explanation: str
