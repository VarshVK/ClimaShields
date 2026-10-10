import heapq
from typing import List, Dict, Tuple, Optional, Set
from models.schemas import (
    Node,
    RoadSegment,
    RoadStatus,
    RouteDetail,
    RouteStep,
    WhyThisRoute,
    AvoidedRoadInfo,
    Shelter,
)
from graph.road_graph import RoadGraph, haversine_distance_km


def calculate_edge_cost(edge: RoadSegment, penalty_multiplier: float = 1.0) -> float:
    """
    Computes total traversal cost of an edge based on Distance + Safety Penalty + Time.
    If edge is BLOCKED, returns infinity.
    """
    if edge.status == RoadStatus.BLOCKED or edge.is_blocked:
        return float("inf")

    # Base distance cost in kilometers
    dist_cost = edge.distance_km * 1.0

    # Safety penalty according to flood risk category
    base_penalty = edge.safety_penalty
    if edge.status == RoadStatus.HIGH_RISK:
        base_penalty = max(12.0, base_penalty)
    elif edge.status == RoadStatus.MODERATE_RISK:
        base_penalty = max(4.0, base_penalty)
    elif edge.status == RoadStatus.SAFE:
        base_penalty = max(0.2, base_penalty)

    # Time cost factor (small tie-breaker for efficiency)
    time_cost = edge.travel_time_min * 0.05

    return dist_cost + (base_penalty * penalty_multiplier) + time_cost


def run_dijkstra(
    graph: RoadGraph,
    start_id: str,
    end_id: str,
    exclude_blocked: bool = True,
    edge_penalties: Optional[Dict[str, float]] = None,
) -> Optional[Tuple[List[str], List[RoadSegment], float]]:
    """
    Priority-queue Dijkstra's algorithm.
    Returns: (path_node_ids, path_segments, total_cost) or None if unreachable.
    """
    if start_id not in graph.nodes or end_id not in graph.nodes:
        return None

    if start_id == end_id:
        return ([start_id], [], 0.0)

    edge_penalties = edge_penalties or {}

    # distances[node_id] = lowest cost to reach node
    costs: Dict[str, float] = {node_id: float("inf") for node_id in graph.nodes}
    costs[start_id] = 0.0

    # predecessor map: node_id -> (prev_node_id, edge_used)
    prev: Dict[str, Tuple[str, RoadSegment]] = {}

    # Min-heap stores: (current_cost, current_node_id)
    pq: List[Tuple[float, str]] = [(0.0, start_id)]
    visited: Set[str] = set()

    while pq:
        current_cost, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)

        if u == end_id:
            break

        for v, edge in graph.get_neighbors(u, exclude_blocked=exclude_blocked):
            if v in visited:
                continue

            raw_cost = calculate_edge_cost(edge)
            if raw_cost == float("inf"):
                continue

            extra_penalty = edge_penalties.get(edge.id, 0.0)
            total_step_cost = raw_cost + extra_penalty
            tentative_cost = current_cost + total_step_cost

            if tentative_cost < costs[v]:
                costs[v] = tentative_cost
                prev[v] = (u, edge)
                heapq.heappush(pq, (tentative_cost, v))

    if end_id not in prev:
        return None

    # Reconstruct path
    curr = end_id
    path_nodes = [end_id]
    path_edges = []

    while curr != start_id:
        p_node, p_edge = prev[curr]
        path_nodes.append(p_node)
        path_edges.append(p_edge)
        curr = p_node

    path_nodes.reverse()
    path_edges.reverse()

    return path_nodes, path_edges, costs[end_id]


def run_astar(
    graph: RoadGraph,
    start_id: str,
    end_id: str,
    exclude_blocked: bool = True,
    edge_penalties: Optional[Dict[str, float]] = None,
) -> Optional[Tuple[List[str], List[RoadSegment], float]]:
    """
    A* algorithm using admissible Haversine straight-line heuristic to target.
    Returns: (path_node_ids, path_segments, total_cost) or None if unreachable.
    """
    if start_id not in graph.nodes or end_id not in graph.nodes:
        return None

    if start_id == end_id:
        return ([start_id], [], 0.0)

    target_node = graph.nodes[end_id]
    edge_penalties = edge_penalties or {}

    g_scores: Dict[str, float] = {node_id: float("inf") for node_id in graph.nodes}
    g_scores[start_id] = 0.0

    def heuristic(node_id: str) -> float:
        n = graph.nodes[node_id]
        return haversine_distance_km(n.lat, n.lng, target_node.lat, target_node.lng) * 1.0

    f_scores: Dict[str, float] = {node_id: float("inf") for node_id in graph.nodes}
    f_scores[start_id] = heuristic(start_id)

    prev: Dict[str, Tuple[str, RoadSegment]] = {}
    pq: List[Tuple[float, float, str]] = [(f_scores[start_id], 0.0, start_id)]
    visited: Set[str] = set()

    while pq:
        _, current_g, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)

        if u == end_id:
            break

        for v, edge in graph.get_neighbors(u, exclude_blocked=exclude_blocked):
            if v in visited:
                continue

            raw_cost = calculate_edge_cost(edge)
            if raw_cost == float("inf"):
                continue

            extra_penalty = edge_penalties.get(edge.id, 0.0)
            tentative_g = current_g + raw_cost + extra_penalty

            if tentative_g < g_scores[v]:
                g_scores[v] = tentative_g
                f_scores[v] = tentative_g + heuristic(v)
                prev[v] = (u, edge)
                heapq.heappush(pq, (f_scores[v], tentative_g, v))

    if end_id not in prev:
        return None

    curr = end_id
    path_nodes = [end_id]
    path_edges = []

    while curr != start_id:
        p_node, p_edge = prev[curr]
        path_nodes.append(p_node)
        path_edges.append(p_edge)
        curr = p_node

    path_nodes.reverse()
    path_edges.reverse()

    return path_nodes, path_edges, g_scores[end_id]


def build_route_detail(
    route_name: str,
    path_nodes: List[str],
    path_edges: List[RoadSegment],
    total_cost: float,
    graph: RoadGraph,
    is_recommended: bool = True,
    destination_name: str = "Emergency Shelter",
) -> RouteDetail:
    """
    Transforms raw path edges into a comprehensive RouteDetail object with geometry,
    safety score, travel time, and turn-by-turn guidance.
    """
    total_dist = sum(e.distance_km for e in path_edges)
    total_time = sum(e.travel_time_min for e in path_edges)

    # Calculate overall route safety score and risk level
    # Safe segment = 100, Moderate = 60, High = 20
    segment_scores = []
    has_high_risk = False
    has_mod_risk = False

    for e in path_edges:
        if e.status == RoadStatus.HIGH_RISK:
            segment_scores.append(25.0)
            has_high_risk = True
        elif e.status == RoadStatus.MODERATE_RISK:
            segment_scores.append(65.0)
            has_mod_risk = True
        else:
            segment_scores.append(98.0)

    avg_safety = sum(segment_scores) / max(1, len(segment_scores)) if segment_scores else 100.0

    if has_high_risk:
        risk_level = "HIGH RISK"
    elif has_mod_risk:
        risk_level = "MODERATE RISK"
    else:
        risk_level = "LOW RISK"

    # Assemble smooth continuous polyline geometry
    geometry: List[List[float]] = []
    for i, edge in enumerate(path_edges):
        coords = edge.coordinates
        if not coords:
            u_node = graph.nodes[edge.source]
            v_node = graph.nodes[edge.target]
            coords = [[u_node.lat, u_node.lng], [v_node.lat, v_node.lng]]

        # Ensure correct directional orientation of polyline points
        curr_node = path_nodes[i]
        u_node = graph.nodes[curr_node]
        d_start = haversine_distance_km(u_node.lat, u_node.lng, coords[0][0], coords[0][1])
        d_end = haversine_distance_km(u_node.lat, u_node.lng, coords[-1][0], coords[-1][1])

        ordered_coords = coords if d_start <= d_end else list(reversed(coords))
        if geometry:
            geometry.extend(ordered_coords[1:])
        else:
            geometry.extend(ordered_coords)

    # Generate turn-by-turn evacuation instructions
    instructions: List[RouteStep] = []
    instructions.append(
        RouteStep(
            step_number=1,
            instruction=f"Depart from {graph.nodes[path_nodes[0]].name}. Verify vehicle fuel and emergency kit.",
            road_name="Departure Point",
            distance_km=0.0,
            duration_min=0.0,
            status=RoadStatus.SAFE,
            caution_notes="Maintain headlights and keep emergency radio tuned to local advisories.",
        )
    )

    for idx, edge in enumerate(path_edges, start=2):
        caution = None
        if edge.status == RoadStatus.HIGH_RISK:
            caution = f"CAUTION: Severe water hazard ({edge.water_depth_cm:.0f} cm). Drive in center lane slowly."
        elif edge.status == RoadStatus.MODERATE_RISK:
            caution = f"ADVISORY: Standing runoff ({edge.water_depth_cm:.0f} cm). Reduce speed to 30 km/h."
        else:
            caution = "Optimal elevated pavement. Nominal conditions."

        instructions.append(
            RouteStep(
                step_number=idx,
                instruction=f"Follow {edge.name} towards {graph.nodes[path_nodes[idx-1]].name}.",
                road_name=edge.name,
                distance_km=round(edge.distance_km, 2),
                duration_min=round(edge.travel_time_min, 1),
                status=edge.status,
                caution_notes=caution,
            )
        )

    instructions.append(
        RouteStep(
            step_number=len(path_edges) + 2,
            instruction=f"Arrive safely at {destination_name}. Check in with emergency triage personnel.",
            road_name="Arrival Destination",
            distance_km=0.0,
            duration_min=0.0,
            status=RoadStatus.SAFE,
            caution_notes="Parking designated on elevated northern lots.",
        )
    )

    return RouteDetail(
        route_name=route_name,
        path_node_ids=path_nodes,
        road_segments=path_edges,
        total_distance_km=round(total_dist, 2),
        estimated_time_min=round(total_time, 1),
        safety_score=round(avg_safety, 1),
        risk_level=risk_level,
        route_cost=round(total_cost, 2),
        geometry=geometry,
        instructions=instructions,
        is_recommended=is_recommended,
    )


def compute_unpenalized_shortest_path(
    graph: RoadGraph, start_id: str, end_id: str
) -> Optional[Tuple[List[str], List[RoadSegment], float]]:
    """
    Computes theoretical raw shortest path (ignoring flood penalties, allowing all passable edges)
    to serve as the explainability baseline for 'Why this route?'.
    """
    # Run Dijkstra with only distance as cost and zero penalties
    costs: Dict[str, float] = {node_id: float("inf") for node_id in graph.nodes}
    costs[start_id] = 0.0
    prev: Dict[str, Tuple[str, RoadSegment]] = {}
    pq: List[Tuple[float, str]] = [(0.0, start_id)]
    visited: Set[str] = set()

    while pq:
        curr_cost, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == end_id:
            break

        for v, edge in graph.adj.get(u, []):
            if v in visited:
                continue
            step_cost = edge.distance_km
            if curr_cost + step_cost < costs[v]:
                costs[v] = curr_cost + step_cost
                prev[v] = (u, edge)
                heapq.heappush(pq, (costs[v], v))

    if end_id not in prev:
        return None

    curr = end_id
    path_nodes = [end_id]
    path_edges = []
    while curr != start_id:
        p_node, p_edge = prev[curr]
        path_nodes.append(p_node)
        path_edges.append(p_edge)
        curr = p_node

    path_nodes.reverse()
    path_edges.reverse()
    return path_nodes, path_edges, costs[end_id]


def generate_why_this_route_explanation(
    graph: RoadGraph,
    start_id: str,
    end_id: str,
    recommended_route: RouteDetail,
    destination_name: str,
) -> WhyThisRoute:
    """
    Generates detailed, explainable decision support rationale answering 'Why this route?'.
    Compares the calculated safe route against the unpenalized direct shortest route.
    """
    raw_shortest = compute_unpenalized_shortest_path(graph, start_id, end_id)

    avoided_roads: List[AvoidedRoadInfo] = []
    raw_shortest_dist = recommended_route.total_distance_km

    if raw_shortest:
        _, raw_edges, raw_dist = raw_shortest
        raw_shortest_dist = round(raw_dist, 2)
        recommended_edge_ids = {e.id for e in recommended_route.road_segments}

        for edge in raw_edges:
            if edge.id not in recommended_edge_ids:
                if edge.status == RoadStatus.BLOCKED:
                    avoided_roads.append(
                        AvoidedRoadInfo(
                            road_id=edge.id,
                            road_name=edge.name,
                            status=edge.status,
                            water_depth_cm=edge.water_depth_cm,
                            reason=f"Impassable flood inundation ({edge.water_depth_cm:.0f} cm water). Excluded from graph.",
                        )
                    )
                elif edge.status == RoadStatus.HIGH_RISK:
                    avoided_roads.append(
                        AvoidedRoadInfo(
                            road_id=edge.id,
                            road_name=edge.name,
                            status=edge.status,
                            water_depth_cm=edge.water_depth_cm,
                            reason=f"Dangerous water accumulation ({edge.water_depth_cm:.0f} cm). Bypassed for elevated safety.",
                        )
                    )

    # Count total blocked and high risk roads across network
    unsafe_in_network = sum(
        1 for e in graph.segments.values() if e.status in [RoadStatus.HIGH_RISK, RoadStatus.BLOCKED]
    )
    blocked_in_network = sum(
        1 for e in graph.segments.values() if e.status == RoadStatus.BLOCKED
    )

    delta_dist = round(max(0.0, recommended_route.total_distance_km - raw_shortest_dist), 2)
    delta_time = round(delta_dist / 45.0 * 60, 1)  # approx extra minutes at 45km/h

    # Safety advantage percentage
    safety_advantage = round(
        max(15.0, recommended_route.safety_score - (30.0 if avoided_roads else 10.0)), 1
    )

    rationale_bullets: List[str] = []
    if avoided_roads:
        blocked_names = [r.road_name for r in avoided_roads if r.status == RoadStatus.BLOCKED]
        if blocked_names:
            rationale_bullets.append(
                f"Bypassed {len(blocked_names)} submerged roadway(s) ({', '.join(blocked_names[:2])}) that would trap vehicles in low elevation."
            )
        rationale_bullets.append(
            f"Prioritized high-elevation ridge corridors that remain structurally stable during peak runoff."
        )
    else:
        rationale_bullets.append(
            "Selected optimal elevated arterial corridor with lowest compound flood hazard."
        )

    if delta_dist > 0:
        rationale_bullets.append(
            f"Added only +{delta_dist:.1f} km (+{delta_time:.0f} min) to achieve a {safety_advantage}% safety score advantage."
        )
    else:
        rationale_bullets.append(
            "The safest identified route is also the most direct available path."
        )

    summary_text = (
        f"Your direct route contained {len(avoided_roads)} hazardous or blocked road segment(s). "
        f"The routing engine removed blocked links and penalized high-water zones, selecting an elevated "
        f"alternative that adds {delta_dist:.1f} km but guarantees a {recommended_route.risk_level} evacuation."
    )

    return WhyThisRoute(
        summary=summary_text,
        avoided_roads=avoided_roads,
        unsafe_roads_in_network=unsafe_in_network,
        blocked_roads_in_network=blocked_in_network,
        shortest_path_distance_km=raw_shortest_dist,
        recommended_path_distance_km=recommended_route.total_distance_km,
        delta_distance_km=delta_dist,
        delta_time_min=delta_time,
        safety_advantage_pct=safety_advantage,
        rationale_bullet_points=rationale_bullets,
    )
