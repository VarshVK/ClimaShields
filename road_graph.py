import math
from typing import List, Dict, Tuple, Optional
from models.schemas import Node, RoadSegment, RoadStatus


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in kilometers.
    """
    r = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class RoadGraph:
    """
    In-memory graph representation of the road network for Dijkstra and A* routing.
    """
    def __init__(self, nodes: List[Node], segments: List[RoadSegment]):
        self.nodes: Dict[str, Node] = {n.id: n for n in nodes}
        self.segments: Dict[str, RoadSegment] = {s.id: s for s in segments}
        self.adj: Dict[str, List[Tuple[str, RoadSegment]]] = {n.id: [] for n in nodes}

        # Build directed adjacency list (paired segments provide bidirectional connectivity)
        for seg in segments:
            u = seg.source
            v = seg.target
            if u in self.adj and v in self.adj:
                self.adj[u].append((v, seg))

    def get_neighbors(self, node_id: str, exclude_blocked: bool = True) -> List[Tuple[str, RoadSegment]]:
        """
        Returns accessible neighbors. If exclude_blocked is True, omits BLOCKED roads.
        """
        if node_id not in self.adj:
            return []
        results = []
        for neighbor_id, seg in self.adj[node_id]:
            if exclude_blocked and seg.status == RoadStatus.BLOCKED:
                continue
            results.append((neighbor_id, seg))
        return results

    def find_nearest_node(self, lat: float, lng: float) -> Node:
        """
        Finds the closest road network junction to any given GPS coordinate.
        """
        best_node = None
        min_dist = float("inf")
        for node in self.nodes.values():
            d = haversine_distance_km(lat, lng, node.lat, node.lng)
            if d < min_dist:
                min_dist = d
                best_node = node
        return best_node

    def get_edge_between(self, u: str, v: str) -> Optional[RoadSegment]:
        """
        Finds edge connecting u and v.
        """
        if u not in self.adj:
            return None
        for nbr, seg in self.adj[u]:
            if nbr == v:
                return seg
        return None
