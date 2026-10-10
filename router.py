from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from models.schemas import (
    EvacuationRequest,
    EvacuationPlanResponse,
    DynamicRerouteRequest,
    SimulationScenario,
    Shelter,
    Node,
    RoadSegment,
    WeatherTimelineResponse,
    AIConfidenceMetrics,
    MLFloodPredictRequest,
    FloodSeverity,
    MedicalFacility,
    FoodFacility,
    CityFloodRiskAssessmentResponse,
)

from data.road_network import (
    REGIONS,
    NODES,
    BASE_ROAD_SEGMENTS,
    SHELTERS,
    SIMULATION_SCENARIOS,
)
from services.evacuation_service import EvacuationService
from services.simulation_service import SimulationService
from services.weather_service import WeatherService

api_router = APIRouter(prefix="")

evacuation_service = EvacuationService()
simulation_service = SimulationService(evacuation_service)
weather_service = WeatherService()


@api_router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Pan-India Flood Evacuation Route Planner API",
        "version": "2.0.0",
        "regions_supported": list(REGIONS.keys()),
        "total_nodes_loaded": len(NODES),
        "total_roads_loaded": len(BASE_ROAD_SEGMENTS),
        "total_shelters_loaded": len(SHELTERS),
    }


@api_router.get("/regions")
def get_regions():
    """
    Returns the catalog of supported Pan-India disaster floodplains.
    """
    region_list = []
    for reg_id, r in REGIONS.items():
        region_list.append({
            "id": r["id"],
            "name": r["name"],
            "state": r["state"],
            "river_basin": r["river_basin"],
            "center": r["center"],
            "zoom": r["zoom"],
            "default_origin_id": r["default_origin_id"],
            "default_shelter_id": r["default_shelter_id"],
            "node_count": len(r["nodes"]),
            "road_count": len(r["roads"]),
            "shelter_count": len(r["shelters"]),
            "scenario_count": len(r["scenarios"]),
        })
    return region_list


@api_router.get("/network")
def get_network_data(
    region: Optional[str] = Query(None, description="Region ID (e.g. chennai, mumbai, delhi, kerala, assam, kolkata, gujarat)"),
    city: Optional[str] = Query(None, description="City name for custom Indian location"),
    lat: Optional[float] = Query(None, description="Latitude for custom Indian location"),
    lng: Optional[float] = Query(None, description="Longitude for custom Indian location")
):
    """
    Returns road network topology, nodes, shelters, and scenarios for the specified region or dynamically for any Indian city.
    """
    from data.road_network import get_or_create_city_network
    if lat is not None and lng is not None and city:
        target_reg = get_or_create_city_network(city, lat, lng)
    elif region and region in REGIONS:
        target_reg = REGIONS[region]
    else:
        target_reg = REGIONS["chennai"]

    def_origin_node = next((n for n in target_reg["nodes"] if n.id == target_reg["default_origin_id"]), target_reg["nodes"][0])

    return {
        "region": target_reg["id"],
        "region_name": target_reg["name"],
        "state": target_reg["state"],
        "river_basin": target_reg["river_basin"],
        "center": target_reg["center"],
        "zoom": target_reg["zoom"],
        "nodes": target_reg["nodes"],
        "roads": target_reg["roads"],
        "shelters": target_reg["shelters"],
        "medical_facilities": target_reg.get("medical_facilities", []),
        "food_facilities": target_reg.get("food_facilities", []),
        "scenarios": target_reg["scenarios"],
        "default_origin": {
            "id": def_origin_node.id,
            "name": def_origin_node.name,
            "lat": def_origin_node.lat,
            "lng": def_origin_node.lng,
            "elevation_m": def_origin_node.elevation_m,
        },
        "default_shelter_id": target_reg["default_shelter_id"],
        "available_regions": [
            {
                "id": r["id"],
                "name": r["name"],
                "state": r["state"],
                "center": r["center"],
                "zoom": r["zoom"]
            }
            for r in REGIONS.values()
        ]
    }


@api_router.get("/shelters", response_model=List[Shelter])
def get_shelters(region: Optional[str] = Query(None)):
    if region and region in REGIONS:
        return REGIONS[region]["shelters"]
    return SHELTERS


@api_router.post("/assess-route", response_model=EvacuationPlanResponse)
def assess_and_plan_route(request: EvacuationRequest):
    try:
        response = evacuation_service.plan_evacuation(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing analysis error: {str(e)}")


@api_router.post("/find-safest-shelter")
def find_safest_shelter(request: EvacuationRequest):
    try:
        request.shelter_id = "auto"
        response = evacuation_service.plan_evacuation(request)
        return {
            "recommended_shelter": response.selected_shelter,
            "rankings": response.candidate_shelters_ranked,
            "route": response.recommended_route,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shelter evaluation error: {str(e)}")


@api_router.get("/simulation/scenarios", response_model=List[SimulationScenario])
def get_simulation_scenarios(region: Optional[str] = Query(None)):
    if region and region in REGIONS:
        return REGIONS[region]["scenarios"]
    return SIMULATION_SCENARIOS


@api_router.post("/simulation/reroute")
def run_dynamic_simulation(request: DynamicRerouteRequest):
    try:
        result = simulation_service.execute_dynamic_reroute(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")


@api_router.get("/weather/timeline", response_model=WeatherTimelineResponse)
def get_weather_timeline(day_offset: int = 0, lat: float = 13.0827, lng: float = 80.2707):
    """
    Returns 7-day weather details (-3 days past to +3 days future)
    along with AI Forecast Confidence Detection analysis for flood evacuation.
    """
    try:
        return weather_service.get_7day_timeline(lat=lat, lng=lng, active_day_offset=day_offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather service error: {str(e)}")


@api_router.get("/weather/confidence", response_model=AIConfidenceMetrics)
def get_weather_confidence(day_offset: int = 0, lat: float = 13.0827, lng: float = 80.2707):
    """
    Returns dedicated AI Confidence Detection metrics and explainable rationale.
    """
    try:
        timeline = weather_service.get_7day_timeline(lat=lat, lng=lng, active_day_offset=day_offset)
        return timeline.ai_confidence
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Confidence calculation error: {str(e)}")


@api_router.get("/ml-model-info")
def get_ml_model_info():
    """Returns training metrics and feature importances for the AI Flood Inundation Predictor."""
    try:
        from backend.flood_predictor import ai_flood_predictor
        return {
            "is_trained": ai_flood_predictor.is_trained,
            "metrics": ai_flood_predictor.metrics,
            "feature_importances": ai_flood_predictor.feature_importances,
            "feature_names": ai_flood_predictor.feature_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML Model info error: {str(e)}")


@api_router.post("/ml-predict")
def predict_flood_when_and_where(request: MLFloodPredictRequest):
    """
    Executes AI Flood Inundation & Timing Prediction for ungauged river basins.
    Predicts:
    1. WHEN: Time of concentration, peak flood crest arrival, and recession horizon.
    2. WHERE: Inundation probability (%) and water depth (cm) across nodes and road segments.
    """
    try:
        from backend.flood_predictor import ai_flood_predictor
        reg_id = (request.region or "chennai").lower()
        target_reg = REGIONS.get(reg_id, REGIONS["chennai"])

        prediction = ai_flood_predictor.predict_when_and_where(
            region_id=reg_id,
            rainfall_forecast_mm=request.rainfall_forecast_mm,
            rainfall_intensity_mmh=request.rainfall_intensity_mmh,
            soil_saturation_state=request.soil_saturation_state or "saturated",
            forecast_lead_day=request.forecast_lead_day or 4,
            nodes=target_reg["nodes"],
            roads=target_reg["roads"]
        )
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Flood prediction error: {str(e)}")


@api_router.post("/ml-evacuate")
def plan_ml_flood_evacuation(request: MLFloodPredictRequest):
    """
    Combines AI Inundation Prediction with Topological Evacuation Routing:
    1. Predicts submerged roads using the trained ML model.
    2. Dynamically blocks all submerged roads in the routing engine.
    3. Calculates the optimal, elevated evacuation route to the safest shelter.
    """
    try:
        from backend.flood_predictor import ai_flood_predictor
        reg_id = (request.region or "chennai").lower()
        target_reg = REGIONS.get(reg_id, REGIONS["chennai"])

        prediction = ai_flood_predictor.predict_when_and_where(
            region_id=reg_id,
            rainfall_forecast_mm=request.rainfall_forecast_mm,
            rainfall_intensity_mmh=request.rainfall_intensity_mmh,
            soil_saturation_state=request.soil_saturation_state or "saturated",
            forecast_lead_day=request.forecast_lead_day or 4,
            nodes=target_reg["nodes"],
            roads=target_reg["roads"]
        )

        submerged_road_ids = prediction["where_flood_comes"]["submerged_road_ids"]

        # Determine origin node
        orig_id = request.origin_node_id or target_reg["default_origin_id"]
        orig_node = next((n for n in target_reg["nodes"] if n.id == orig_id), target_reg["nodes"][0])

        shelter_id = request.destination_shelter_id or target_reg["default_shelter_id"]

        evac_req = EvacuationRequest(
            origin_name=orig_node.name,
            origin_lat=orig_node.lat,
            origin_lng=orig_node.lng,
            shelter_id=shelter_id,
            flood_severity=FloodSeverity.SEVERE,
            user_blocked_road_ids=submerged_road_ids,
            algorithm="dijkstra"
        )

        evac_plan = evacuation_service.plan_evacuation(evac_req)

        return {
            "prediction": prediction,
            "evacuation_plan": evac_plan,
            "ml_avoided_submerged_roads_count": len(submerged_road_ids),
            "evacuation_status": "SUCCESS" if evac_plan.success else "NO_SAFE_ROUTE"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML Flood evacuation error: {str(e)}")


@api_router.get("/assess-city-risk", response_model=CityFloodRiskAssessmentResponse)
def assess_city_risk_endpoint(
    city: str = Query(..., description="City or Basin name across India"),
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    admin1: Optional[str] = Query("", description="State or Administrative Region")
):
    """
    Evaluates comprehensive flood risk for any Indian city or river basin,
    generates tailored civil defense preventive measures, and returns nearby
    essential facilities (medical shops, food supply depots, and safe shelters)
    with safe evacuation routing guidance.
    """
    try:
        from services.city_risk_service import assess_city_flood_risk
        return assess_city_flood_risk(city, lat, lng, admin1 or "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"City flood risk assessment error: {str(e)}")


@api_router.get("/medical-facilities", response_model=List[MedicalFacility])
def get_medical_facilities(
    region: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None)
):
    from data.road_network import get_or_create_city_network
    if lat is not None and lng is not None and city:
        target_reg = get_or_create_city_network(city, lat, lng)
    elif region and region in REGIONS:
        target_reg = REGIONS[region]
    else:
        target_reg = REGIONS["chennai"]
    return target_reg.get("medical_facilities", [])


@api_router.get("/food-facilities", response_model=List[FoodFacility])
def get_food_facilities(
    region: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None)
):
    from data.road_network import get_or_create_city_network
    if lat is not None and lng is not None and city:
        target_reg = get_or_create_city_network(city, lat, lng)
    elif region and region in REGIONS:
        target_reg = REGIONS[region]
    else:
        target_reg = REGIONS["chennai"]
    return target_reg.get("food_facilities", [])


