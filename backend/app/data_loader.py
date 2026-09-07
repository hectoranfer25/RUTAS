import json
from pathlib import Path
from typing import Any


class DataValidationError(Exception):
    pass


def _coord(value):
    if not isinstance(value, list) or len(value) != 2:
        return None
    try:
        lat, lon = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return [lat, lon]


def load_and_validate(path: str):
    p = Path(path)
    if not p.exists():
        raise DataValidationError(f"No existe el archivo de datos: {path}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataValidationError(f"JSON inválido: {exc.msg}") from exc

    warnings = []
    for key in ("Routes", "Load", "Dump"):
        if key not in raw or not isinstance(raw[key], list):
            raise DataValidationError(f"El arreglo raíz '{key}' es obligatorio.")

    routes = []
    for idx, item in enumerate(raw["Routes"]):
        if not isinstance(item, dict):
            warnings.append(f"Routes[{idx}] ignorado: no es objeto.")
            continue
        try:
            rid = int(item["id_trm_cs"])
            name = str(item.get("nombre_tramo", ""))
            color = str(item.get("color", "#3388ff"))
            points_raw = item.get("points")
            if not isinstance(points_raw, list) or len(points_raw) < 2:
                raise ValueError("points debe contener al menos dos coordenadas")
            points = []
            for point in points_raw:
                coord = _coord(point)
                if coord is None:
                    raise ValueError("coordenada inválida")
                points.append(coord)
            routes.append({"id_trm_cs": rid, "nombre_tramo": name, "color": color, "points": points})
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append(f"Routes[{idx}] ignorado: {exc}")

    def locations(key):
        result = []
        for idx, item in enumerate(raw[key]):
            if not isinstance(item, dict):
                warnings.append(f"{key}[{idx}] ignorado: no es objeto.")
                continue
            coord = _coord(item.get("coor"))
            if coord is None:
                warnings.append(f"{key}[{idx}] ignorado: coordenada inválida.")
                continue
            try:
                ident = int(item["id"])
            except (KeyError, TypeError, ValueError):
                warnings.append(f"{key}[{idx}] ignorado: id inválido.")
                continue
            radio = item.get("radio")
            try:
                radio = int(radio) if radio is not None else None
            except (TypeError, ValueError):
                warnings.append(f"{key}[{idx}].radio inválido; se usa null.")
                radio = None
            result.append({"id": ident, "name": str(item.get("name", "")),
                           "coor": coord, "radio": radio})
        return result

    return routes, locations("Load"), locations("Dump"), warnings
