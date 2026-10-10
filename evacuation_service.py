from typing import List, Optional, Tuple, Dict, Any
from models.schemas import (
    EvacuationRequest,
    EvacuationPlanResponse,
    RouteDetail,
    ShelterRanking,
    Shelter,
    RoadSegment,
    RoadStatus,
    FloodSeverity,
)
from data.road_network import (
    NODES,
    BASE_ROAD_SEGMENTS,
    SHELTERS,
    SHELTER_MAP,
    NODE_MAP,
)
from risk.assessment import assess_network
from graph.road_graph import RoadGraph, haversine_distance_km
from routing.engine import (
    run_dijkstra,
    run_astar,
    build_route_detail,
    generate_why_this_route_explanation,
)

SAFETY_DISCLAIMER = (
    "DISCLAIMER: This prototype decision-support system calculates evacuation routes based on user-provided "
    "or simulated flood conditions and road network topologies. It does not provide real-time automated flood "
    "prediction from coordinates alone, nor does it replace instructions, evacuation orders, or road closures issued "
    "by local emergency management authorities, civil defense, or emergency services."
)


class EvacuationService:
    def __init__(self):
        self.base_nodes = NODES
        self.base_segments = BASE_ROAD_SEGMENTS
        self.shelters = SHELTERS

    def plan_evacuation(self, req: EvacuationRequest) -> EvacuationPlanResponse:
        """
        Executes end-to-end evacuation planning workflow:
        Input validation -> Safety Assessment -> Graph Construction ->
        Dijkstra/A* Routing -> Alternative Search -> Explainability -> Response Assembly.
        """
        active_nodes = NODES if NODES else self.base_nodes
        active_segments = BASE_ROAD_SEGMENTS if BASE_ROAD_SEGMENTS else self.base_segments
        active_shelters = SHELTERS if SHELTERS else self.shelters

        # 1. Safety assessment on road network
        updated_segments, overall_risk, assessment_summary, stats = assess_network(
            base_segments=active_segments,
            flood_severity=req.flood_severity,
            user_water_depth_cm=req.water_depth_cm,
            user_blocked_ids=req.user_blocked_road_ids,
            user_notes=req.user_reported_condition,
            rainfall_mm_hr=req.rainfall_mm_hr,
            rainfall_duration_hours=req.rainfall_duration_hours,
            soil_saturation=req.soil_saturation,
            ai_confidence_buffer_pct=req.ai_confidence_buffer_pct or 0.0,
        )

        # 2. Build graph with updated edge conditions
        graph = RoadGraph(active_nodes, updated_segments)

        # 3. Resolve starting junction node
        start_node = graph.find_nearest_node(req.origin_lat, req.origin_lng)
        if not start_node:
            return EvacuationPlanResponse(
                success=False,
                message="Unable to identify a nearby road junction for the provided origin coordinates.",
                overall_flood_risk=overall_risk,
                assessment_summary=assessment_summary,
                disclaimer=SAFETY_DISCLAIMER,
                all_roads=updated_segments,
                all_shelters=active_shelters,
            )

        # 4. Resolve destination / shelter selection
        selected_shelter: Optional[Shelter] = None
        target_node_id: Optional[str] = None
        ranked_shelters: List[ShelterRanking] = []

        # Filter candidate shelters to those within the same regional basin (<= 150 km)
        candidate_shelters = [
            s for s in active_shelters
            if haversine_distance_km(req.origin_lat, req.origin_lng, s.lat, s.lng) <= 150.0
        ]
        if not candidate_shelters:
            candidate_shelters = active_shelters

        # Evaluate candidate shelters
        for s in candidate_shelters:
            s_node = graph.find_nearest_node(s.lat, s.lng)
            if not s_node:
                continue

            # Run preliminary Dijkstra to test accessibility & safety
            res = run_dijkstra(graph, start_node.id, s_node.id, exclude_blocked=True)
            if res:
                p_nodes, p_edges, p_cost = res
                dist = sum(e.distance_km for e in p_edges)
                dur = sum(e.travel_time_min for e in p_edges)

                # Route safety score
                risk_count = sum(1 for e in p_edges if e.status in [RoadStatus.HIGH_RISK, RoadStatus.MODERATE_RISK])
                score = max(20.0, 100.0 - (risk_count * 20.0))
                safety_lvl = "LOW RISK" if score >= 80 else ("MODERATE RISK" if score >= 50 else "HIGH RISK")

                reason = (
                    f"Elevated safe shelter ({s.elevation_m:.0f}m elevation) with "
                    f"{s.available_capacity} available beds and {safety_lvl} access route."
                )

                ranked_shelters.append(
                    ShelterRanking(
                        shelter=s,
                        route_distance_km=round(dist, 2),
                        estimated_time_min=round(dur, 1),
                        route_safety_level=safety_lvl,
                        safety_score=round(score, 1),
                        is_recommended=False,
                        recommendation_reason=reason,
                    )
                )

        # Sort candidate shelters by combined safety and proximity score
        ranked_shelters.sort(
            key=lambda r: (
                r.safety_score * 0.6
                - r.route_distance_km * 2.0
                + (min(1000, r.shelter.available_capacity) / 50.0)
            ),
            reverse=True,
        )

        if ranked_shelters:
            ranked_shelters[0].is_recommended = True

        # Determine target shelter based on user input or auto recommendation
        if req.shelter_id and req.shelter_id != "auto" and req.shelter_id in SHELTER_MAP:
            selected_shelter = SHELTER_MAP[req.shelter_id]
        elif req.custom_destination_lat is not None and req.custom_destination_lng is not None:
            custom_node = graph.find_nearest_node(
                req.custom_destination_lat, req.custom_destination_lng
            )
            target_node_id = custom_node.id if custom_node else None
            selected_shelter = Shelter(
                id="CUSTOM_DESTINATION",
                name=req.custom_destination_name or "Custom Safe Destination",
                address="User Specified Location",
                lat=req.custom_destination_lat,
                lng=req.custom_destination_lng,
                capacity=500,
                current_occupancy=0,
                available_capacity=500,
                elevation_m=custom_node.elevation_m if custom_node else 30.0,
                safety_status="CUSTOM_COORDINATE",
            )
        else:
            # Auto-select best ranked shelter
            if ranked_shelters:
                selected_shelter = ranked_shelters[0].shelter
            elif candidate_shelters:
                selected_shelter = candidate_shelters[0]
            else:
                selected_shelter = active_shelters[0]

        if not target_node_id and selected_shelter:
            s_node = graph.find_nearest_node(selected_shelter.lat, selected_shelter.lng)
            target_node_id = s_node.id if s_node else None

        if not target_node_id:
            return EvacuationPlanResponse(
                success=False,
                message="Target destination cannot be resolved to any road network junction.",
                overall_flood_risk=overall_risk,
                assessment_summary=assessment_summary,
                disclaimer=SAFETY_DISCLAIMER,
                all_roads=updated_segments,
                all_shelters=self.shelters,
            )

        # 5. Execute Routing Algorithm (Dijkstra or A*)
        routing_algo = req.algorithm.lower() if req.algorithm else "dijkstra"
        if routing_algo == "astar":
            route_res = run_astar(graph, start_node.id, target_node_id, exclude_blocked=True)
        else:
            route_res = run_dijkstra(graph, start_node.id, target_node_id, exclude_blocked=True)

        is_emergency_detour = False
        if not route_res:
            # Resilient Emergency Fallback: If strictly unblocked paths are closed,
            # calculate the optimal high-clearance emergency trajectory with elevated penalty weighting
            # so evacuees are NEVER left stranded without a route to safety!
            route_res = run_dijkstra(graph, start_node.id, target_node_id, exclude_blocked=False)
            is_emergency_detour = True

        if not route_res:
            # Truly disconnected graph
            return EvacuationPlanResponse(
                success=False,
                message=(
                    f"No safe vehicular evacuation route currently exists between {start_node.name} and "
                    f"{selected_shelter.name}. All connecting corridors are blocked by severe flood inundation. "
                    "Shelter in place on highest available ground or contact emergency rescue."
                ),
                overall_flood_risk=overall_risk,
                assessment_summary=assessment_summary,
                selected_shelter=selected_shelter,
                candidate_shelters_ranked=ranked_shelters,
                disclaimer=SAFETY_DISCLAIMER,
                all_roads=updated_segments,
                all_shelters=self.shelters,
                statistics=stats,
            )

        path_nodes, path_edges, route_cost = route_res

        # 6. Build recommended route detail
        route_name = "Emergency High-Ground Trajectory (Severe Flood Bypass)" if is_emergency_detour else "Recommended Evacuation Route (Primary)"
        recommended_route = build_route_detail(
            route_name=route_name,
            path_nodes=path_nodes,
            path_edges=path_edges,
            total_cost=route_cost,
            graph=graph,
            is_recommended=True,
            destination_name=selected_shelter.name,
        )
        if is_emergency_detour:
            recommended_route.safety_score = max(35.0, recommended_route.safety_score)
            recommended_route.risk_level = "EMERGENCY HIGH-CLEARANCE DETOUR"

        # 7. Compute Alternative Route
        # Increase cost on edges used in primary path to find a distinct secondary path
        edge_penalties = {e.id: 25.0 for e in path_edges}
        alt_res = run_dijkstra(
            graph, start_node.id, target_node_id, exclude_blocked=True, edge_penalties=edge_penalties
        )

        alternative_route: Optional[RouteDetail] = None
        if alt_res:
            alt_nodes, alt_edges, alt_cost = alt_res
            # Ensure alternative is meaningfully different (different edge set)
            primary_edge_ids = {e.id for e in path_edges}
            alt_edge_ids = {e.id for e in alt_edges}
            if primary_edge_ids != alt_edge_ids and len(alt_edges) > 0:
                alternative_route = build_route_detail(
                    route_name="Alternative Safe Route (Secondary Option)",
                    path_nodes=alt_nodes,
                    path_edges=alt_edges,
                    total_cost=alt_cost - 25.0,  # normalize displayed cost
                    graph=graph,
                    is_recommended=False,
                    destination_name=selected_shelter.name,
                )

        # 8. Generate 'Why this route?' explanation
        why_this_route = generate_why_this_route_explanation(
            graph=graph,
            start_id=start_node.id,
            end_id=target_node_id,
            recommended_route=recommended_route,
            destination_name=selected_shelter.name,
        )

        # Update statistics with calculated route values
        stats.route_cost = recommended_route.route_cost
        stats.alternative_route_available = alternative_route is not None

        return EvacuationPlanResponse(
            success=True,
            message="Optimal safe evacuation route successfully calculated.",
            overall_flood_risk=overall_risk,
            assessment_summary=assessment_summary,
            recommended_route=recommended_route,
            alternative_route=alternative_route,
            selected_shelter=selected_shelter,
            candidate_shelters_ranked=ranked_shelters,
            why_this_route=why_this_route,
            statistics=stats,
            disclaimer=SAFETY_DISCLAIMER,
            all_roads=updated_segments,
            all_shelters=self.shelters,
        )
