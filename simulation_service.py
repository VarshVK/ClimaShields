from typing import Dict, Any, List, Optional
from models.schemas import (
    SimulationScenario,
    DynamicRerouteRequest,
    EvacuationPlanResponse,
    EvacuationRequest,
    FloodSeverity,
    RoadStatus,
)
from data.road_network import (
    SIMULATION_SCENARIOS,
    NODES,
    BASE_ROAD_SEGMENTS,
    SHELTERS,
    SHELTER_MAP,
)
from services.evacuation_service import EvacuationService


class SimulationService:
    def __init__(self, evacuation_service: EvacuationService):
        self.evacuation_service = evacuation_service
        self.scenarios = SIMULATION_SCENARIOS

    def get_all_scenarios(self) -> List[SimulationScenario]:
        return self.scenarios

    def get_scenario_by_id(self, scenario_id: str) -> Optional[SimulationScenario]:
        for s in self.scenarios:
            if s.id == scenario_id:
                return s
        return None

    def execute_dynamic_reroute(self, req: DynamicRerouteRequest) -> Dict[str, Any]:
        """
        Executes dynamic reroute simulation:
        1. Calculates initial route without the new blockages
        2. Applies the dynamic blockages
        3. Recalculates route instantly
        4. Returns comparison demonstrating the DETECT -> EVALUATE -> REROUTE -> EVACUATE pipeline.
        """
        # Step 1: Baseline plan before surge
        before_request = EvacuationRequest(
            origin_name="Simulation Origin",
            origin_lat=req.current_origin_lat,
            origin_lng=req.current_origin_lng,
            shelter_id=req.destination_shelter_id,
            flood_severity=req.flood_severity,
            water_depth_cm=10.0,
            user_blocked_road_ids=[],
        )
        before_plan: EvacuationPlanResponse = self.evacuation_service.plan_evacuation(before_request)

        # Step 2: Plan after surge with newly blocked roads
        after_request = EvacuationRequest(
            origin_name="Simulation Origin",
            origin_lat=req.current_origin_lat,
            origin_lng=req.current_origin_lng,
            shelter_id=req.destination_shelter_id,
            flood_severity=FloodSeverity.SEVERE,
            water_depth_cm=None,
            user_blocked_road_ids=req.newly_blocked_road_ids,
        )
        after_plan: EvacuationPlanResponse = self.evacuation_service.plan_evacuation(after_request)

        # Find names of newly blocked roads
        blocked_names = []
        for r in after_plan.all_roads:
            if r.id in req.newly_blocked_road_ids or (r.is_blocked and r.status == RoadStatus.BLOCKED):
                if r.name not in blocked_names:
                    blocked_names.append(r.name)

        blocked_str = ", ".join(blocked_names[:3]) if blocked_names else "Designated road corridor"

        alert_message = (
            f"Road link(s) ({blocked_str}) became BLOCKED due to flash flood inundation. "
            f"The routing engine immediately purged the blocked edges from the topology and "
            f"dynamically rerouted evacuation through safe elevated alternatives."
        )

        return {
            "simulation_label": req.simulation_label,
            "status": "ROUTE_UPDATED",
            "alert_title": "ROUTE UPDATED",
            "alert_message": alert_message,
            "blocked_roads": blocked_names,
            "blocked_road_ids": req.newly_blocked_road_ids,
            "before_route": before_plan.recommended_route,
            "after_route": after_plan.recommended_route,
            "after_plan": after_plan,
        }
