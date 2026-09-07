from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000.0 * 2 * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class Edge:
    target: tuple[float, float]
    distance_m: float
    route_id: int


class RoadNetwork:
    def __init__(self, routes: list[dict]):
        self.routes = routes
        self.adj: dict[tuple[float, float], list[Edge]] = defaultdict(list)
        self.route_ids_by_edge: dict[tuple[tuple[float, float], tuple[float, float]], int] = {}
        for route in routes:
            points = [tuple(p) for p in route["points"]]
            for a, b in zip(points, points[1:]):
                d = haversine(a, b)
                if d <= 0:
                    continue
                self.adj[a].append(Edge(b, d, route["id_trm_cs"]))
                self.adj[b].append(Edge(a, d, route["id_trm_cs"]))
                self.route_ids_by_edge[(a, b)] = route["id_trm_cs"]
                self.route_ids_by_edge[(b, a)] = route["id_trm_cs"]

    @property
    def nodes(self):
        return list(self.adj.keys())

    def nearest_node(self, coord: list[float], max_m: float) -> tuple[tuple[float, float] | None, float]:
        point = tuple(coord)
        best = None
        best_d = float("inf")
        for node in self.adj:
            d = haversine(point, node)
            if d < best_d:
                best, best_d = node, d
        if best is None or best_d > max_m:
            return None, best_d
        return best, best_d

    def shortest_path(self, start, goal):
        if start not in self.adj or goal not in self.adj:
            return None
        queue = [(0.0, start)]
        dist = {start: 0.0}
        prev = {}
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != dist.get(node):
                continue
            if node == goal:
                break
            for edge in self.adj[node]:
                nc = cost + edge.distance_m
                if nc < dist.get(edge.target, float("inf")):
                    dist[edge.target] = nc
                    prev[edge.target] = node
                    heapq.heappush(queue, (nc, edge.target))
        if goal not in dist:
            return None
        path = []
        cur = goal
        while cur != start:
            path.append(cur)
            cur = prev[cur]
        path.append(start)
        path.reverse()
        return path, dist[goal]

    def connected_components(self):
        seen = set()
        components = []
        for node in self.adj:
            if node in seen:
                continue
            stack = [node]
            comp = set()
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                comp.add(cur)
                stack.extend(edge.target for edge in self.adj[cur] if edge.target not in seen)
            components.append(comp)
        return components


def path_cumulative(path):
    cumulative = [0.0]
    for a, b in zip(path, path[1:]):
        cumulative.append(cumulative[-1] + haversine(a, b))
    return cumulative


def interpolate_path(path, cumulative, distance_m):
    if not path:
        return None
    if distance_m <= 0:
        return path[0]
    total = cumulative[-1]
    if distance_m >= total:
        return path[-1]
    for i in range(1, len(path)):
        if cumulative[i] >= distance_m:
            segment = cumulative[i] - cumulative[i - 1]
            ratio = (distance_m - cumulative[i - 1]) / segment if segment else 0
            lat = path[i - 1][0] + (path[i][0] - path[i - 1][0]) * ratio
            lon = path[i - 1][1] + (path[i][1] - path[i - 1][1]) * ratio
            return lat, lon
    return path[-1]
