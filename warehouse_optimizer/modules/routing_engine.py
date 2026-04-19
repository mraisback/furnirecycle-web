"""
RoutingEngine: Computes optimal picker routes for single and batch orders.

Graph model:
  - Every grid cell (storage + aisle) is a node.
  - Edges connect orthogonally adjacent cells; weight = cell_size_m.
  - Shortest paths use Dijkstra via NetworkX.

Batch picking strategy:
  - Cluster orders by geographic proximity of their SKU locations.
  - Route the picker through all pick-points using a nearest-neighbour
    TSP heuristic (2-opt improvement for batches > 8 items).
"""

from __future__ import annotations

import math
import itertools
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

from .data_processor import WarehouseLayout


PickPoint = Tuple[int, int]   # (row, col)


class RoutingEngine:
    """Builds the warehouse graph and computes picker routes."""

    def __init__(self, layout: WarehouseLayout, assignment: Dict[str, PickPoint]):
        self.layout = layout
        self.assignment = assignment   # sku_id → grid position
        self.graph = self._build_graph()
        self._path_cache: Dict[Tuple[PickPoint, PickPoint], float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route_order(self, sku_ids: List[str]) -> Tuple[List[PickPoint], float]:
        """
        Return (route, total_distance) for a single order.
        Route starts and ends at entry_exit.
        """
        pick_points = self._resolve_pick_points(sku_ids)
        if not pick_points:
            return [], 0.0
        return self._tsp_route(pick_points)

    def route_batch(
        self,
        orders: Dict[str, List[str]],
        batch_size: int = 5,
    ) -> Dict[str, Tuple[List[PickPoint], float]]:
        """
        Group orders into batches of `batch_size` and route each batch.
        Returns {batch_id: (route, distance)}.
        """
        order_items = list(orders.items())
        results: Dict[str, Tuple[List[PickPoint], float]] = {}
        batch_num = 0
        for i in range(0, len(order_items), batch_size):
            chunk = order_items[i : i + batch_size]
            combined_skus: List[str] = []
            for _, skus in chunk:
                combined_skus.extend(skus)
            route, dist = self.route_order(combined_skus)
            results[f"batch_{batch_num:03d}"] = (route, dist)
            batch_num += 1
        return results

    def shortest_path_distance(self, a: PickPoint, b: PickPoint) -> float:
        """Cached Dijkstra distance between two grid cells."""
        key = (min(a, b), max(a, b))
        if key not in self._path_cache:
            try:
                d = nx.dijkstra_path_length(self.graph, a, b, weight="weight")
            except nx.NetworkXNoPath:
                d = math.inf
            self._path_cache[key] = d
        return self._path_cache[key]

    def shortest_path(self, a: PickPoint, b: PickPoint) -> List[PickPoint]:
        try:
            return nx.dijkstra_path(self.graph, a, b, weight="weight")
        except nx.NetworkXNoPath:
            return []

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> nx.Graph:
        """
        All grid cells are nodes; edges connect orthogonal neighbours.
        Storage cells cost cell_size_m; aisles cost cell_size_m (traversable).
        """
        G = nx.Graph()
        rows, cols = self.layout.rows, self.layout.cols
        w = self.layout.cell_size_m

        for r in range(rows):
            for c in range(cols):
                G.add_node((r, c))
                if r > 0:
                    G.add_edge((r, c), (r - 1, c), weight=w)
                if c > 0:
                    G.add_edge((r, c), (r, c - 1), weight=w)
        return G

    # ------------------------------------------------------------------
    # TSP heuristic (nearest-neighbour + optional 2-opt)
    # ------------------------------------------------------------------

    def _tsp_route(
        self, pick_points: List[PickPoint]
    ) -> Tuple[List[PickPoint], float]:
        start = self.layout.entry_exit
        unvisited = list(dict.fromkeys(pick_points))   # deduplicate, preserve order

        route = [start]
        total = 0.0
        current = start

        while unvisited:
            nearest = min(unvisited, key=lambda p: self.shortest_path_distance(current, p))
            total += self.shortest_path_distance(current, nearest)
            route.append(nearest)
            unvisited.remove(nearest)
            current = nearest

        # Return to dispatch
        total += self.shortest_path_distance(current, start)
        route.append(start)

        # 2-opt improvement for larger batches
        if len(route) > 8:
            route, total = self._two_opt(route, total)

        return route, total

    def _two_opt(
        self, route: List[PickPoint], current_dist: float
    ) -> Tuple[List[PickPoint], float]:
        improved = True
        best = route[:]
        best_dist = current_dist
        n = len(best)
        while improved:
            improved = False
            for i in range(1, n - 2):
                for j in range(i + 1, n - 1):
                    d_removed = (
                        self.shortest_path_distance(best[i - 1], best[i])
                        + self.shortest_path_distance(best[j], best[j + 1])
                    )
                    d_added = (
                        self.shortest_path_distance(best[i - 1], best[j])
                        + self.shortest_path_distance(best[i], best[j + 1])
                    )
                    if d_added < d_removed - 1e-6:
                        best[i : j + 1] = best[i : j + 1][::-1]
                        best_dist = best_dist - d_removed + d_added
                        improved = True
        return best, best_dist

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_pick_points(self, sku_ids: List[str]) -> List[PickPoint]:
        pts = []
        for sid in sku_ids:
            pos = self.assignment.get(sid)
            if pos:
                pts.append(pos)
        return pts
