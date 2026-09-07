from __future__ import annotations

import random
import threading
import uuid
from datetime import datetime, timezone

from .network import RoadNetwork, haversine, interpolate_path, path_cumulative


TRUCK_IDS = [f"CAMION-{i:03d}" for i in range(1, 6)]


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class SimulationManager:
    def __init__(self, routes, loads, dumps, network, seed=5923, min_speed=22, max_speed=52, tick=3, snap_max=2000):
        self.routes = routes
        self.loads = loads
        self.dumps = dumps
        self.network = network
        self.seed = seed
        self.min_speed = min_speed
        self.max_speed = max_speed
        self.tick = tick
        self.snap_max = snap_max
        self.lock = threading.Lock()
        self.state = None
        self._assignment_cache = None

    def _build_assignments(self, rng):
        # Se calcula una sola vez. Antes se ejecutaba Dijkstra para cada
        # combinación carga-descarga (30 x 139 = 4,170 rutas).
        if self._assignment_cache is None:
            pairs = []

            load_nodes = {}
            for load in self.loads:
                lnode, _ = self.network.nearest_node(load["coor"], self.snap_max)
                if lnode is not None:
                    load_nodes[load["id"]] = lnode

            dump_nodes = {}
            for dump in self.dumps:
                dnode, _ = self.network.nearest_node(dump["coor"], self.snap_max)
                if dnode is not None:
                    dump_nodes[dump["id"]] = dnode

            # Un Dijkstra por nodo de carga, en lugar de uno por cada
            # combinación carga-descarga.
            loads_by_node = {}
            for load in self.loads:
                lnode = load_nodes.get(load["id"])
                if lnode is not None:
                    loads_by_node.setdefault(lnode, []).append(load)

            for lnode, loads_at_node in loads_by_node.items():
                distances, previous = self.network._dijkstra(lnode)

                for dump in self.dumps:
                    dnode = dump_nodes.get(dump["id"])
                    if dnode is None or dnode not in distances:
                        continue

                    path = self.network._reconstruct_path(lnode, dnode, previous)
                    if path:
                        distance = distances[dnode]
                        for load in loads_at_node:
                            pairs.append((load, dump, path, distance))

            if not pairs:
                raise ValueError("No existe ningún par carga-descarga alcanzable.")

            self._assignment_cache = pairs

        # Copiamos antes de mezclar para que los siguientes inicios
        # sigan siendo deterministas y no reconstruyan las rutas.
        candidates = list(self._assignment_cache)
        rng.shuffle(candidates)
        return candidates

    def start(self):
        with self.lock:
            rng = random.Random(self.seed)
            candidates = self._build_assignments(rng)
            trucks = {}
            for idx, truck_id in enumerate(TRUCK_IDS):
                load, dump, path, distance = candidates[idx % len(candidates)]
                cumulative = path_cumulative(path)
                speed = rng.uniform(self.min_speed, self.max_speed)
                trucks[truck_id] = {
                    "id": truck_id,
                    "load_id": load["id"],
                    "load_name": load["name"],
                    "dump_id": dump["id"],
                    "dump_name": dump["name"],
                    "path": path,
                    "cumulative": cumulative,
                    "total_distance_m": distance,
                    "traveled_m": 0.0,
                    "speed_kmh": speed,
                    "status": "moving",
                    "timestamp": utcnow(),
                    "samples": [speed],
                }
            self.state = {
                "simulation_id": str(uuid.uuid4()),
                "seed": self.seed,
                "started_at": utcnow(),
                "last_tick": datetime.now(timezone.utc).timestamp(),
                "trucks": trucks,
            }
            return self.snapshot()

    def reset(self):
        with self.lock:
            self.state = None

    def tick_if_needed(self):
        with self.lock:
            if not self.state:
                return
            now = datetime.now(timezone.utc).timestamp()
            elapsed = now - self.state["last_tick"]
            if elapsed < self.tick:
                return
            steps = min(int(elapsed // self.tick), 10)
            for _ in range(steps):
                self._advance_once()
            self.state["last_tick"] += steps * self.tick

    def _advance_once(self):
        rng = random.Random(self.seed + int(self.state["last_tick"]))
        all_finished = True
        for truck in self.state["trucks"].values():
            if truck["status"] == "finished":
                continue
            all_finished = False
            speed = rng.uniform(self.min_speed, self.max_speed)
            truck["speed_kmh"] = speed
            truck["samples"].append(speed)
            truck["traveled_m"] += speed / 3.6 * self.tick
            if truck["traveled_m"] >= truck["total_distance_m"]:
                truck["traveled_m"] = truck["total_distance_m"]
                truck["status"] = "finished"
                truck["speed_kmh"] = 0.0
            truck["timestamp"] = utcnow()
        if all_finished:
            return

    def snapshot(self):
        if not self.state:
            return None
        trucks = []
        for truck in self.state["trucks"].values():
            pos = interpolate_path(truck["path"], truck["cumulative"], truck["traveled_m"])
            total = truck["total_distance_m"]
            trucks.append({
                "id": truck["id"],
                "load_id": truck["load_id"],
                "load_name": truck["load_name"],
                "dump_id": truck["dump_id"],
                "dump_name": truck["dump_name"],
                "lat": pos[0],
                "lon": pos[1],
                "speed_kmh": round(truck["speed_kmh"], 2),
                "status": truck["status"],
                "timestamp": truck["timestamp"],
                "progress": round(truck["traveled_m"] / total, 4) if total else 1.0,
                "distance_km": round(total / 1000, 3),
            })
        return {
            "simulation_id": self.state["simulation_id"],
            "seed": self.state["seed"],
            "started_at": self.state["started_at"],
            "trucks": trucks,
        }

    def report(self):
        if not self.state:
            return []
        fleet_avg = sum(
            sum(t["samples"]) / len(t["samples"]) for t in self.state["trucks"].values()
        ) / len(self.state["trucks"])
        result = []
        for t in self.state["trucks"].values():
            samples = t["samples"]
            avg = sum(samples) / len(samples)
            outside = sum(1 for x in samples if x < 25 or x > 50)
            pct = outside / len(samples) * 100
            delta = avg - fleet_avg
            if len(samples) < 3:
                explanation = f"{t['id']} tiene pocas muestras ({len(samples)}), por lo que la lectura es preliminar."
            elif pct > 25:
                explanation = f"{t['id']} promedia {avg:.1f} km/h y {pct:.1f}% de sus muestras queda fuera del rango de 25–50 km/h."
            elif abs(delta) >= 5:
                relation = "por encima" if delta > 0 else "por debajo"
                explanation = f"{t['id']} promedia {avg:.1f} km/h, {abs(delta):.1f} km/h {relation} del promedio de la flota ({fleet_avg:.1f} km/h)."
            else:
                explanation = f"{t['id']} promedia {avg:.1f} km/h y se mantiene cerca del promedio de la flota ({fleet_avg:.1f} km/h)."
            result.append({
                "truck_id": t["id"],
                "samples": len(samples),
                "min_speed_kmh": round(min(samples), 2),
                "max_speed_kmh": round(max(samples), 2),
                "avg_speed_kmh": round(avg, 2),
                "outside_25_50_samples": outside,
                "outside_25_50_percent": round(pct, 2),
                "explanation": explanation,
            })
        if result:
            fastest = max(result, key=lambda x: x["avg_speed_kmh"])
            slowest = min(result, key=lambda x: x["avg_speed_kmh"])
            result[0]["fleet_note"] = f"Mayor promedio: {fastest['truck_id']}; menor promedio: {slowest['truck_id']}."
        return result
