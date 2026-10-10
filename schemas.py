from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RoadStatus(str, Enum):
    SAFE = "SAFE"
    MODERATE_RISK = "MODERATE_RISK"
    HIGH_RISK = "HIGH_RISK"
    BLOCKED = "BLOCKED"


class FloodSeverity(str, Enum):
    NONE = "No Flooding"
    LOW = "Low Flooding"
    MODERATE = "Moderate Flooding"
    SEVERE = "Severe Flooding"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            v_norm = value.strip().upper().replace("_", " ")
            if v_norm in ("NONE", "NO FLOODING", "NORMAL", "DRY"):
                return cls.NONE
            if v_norm in ("LOW", "LOW FLOODING"):
                return cls.LOW
            if v_norm in ("MODERATE", "MODERATE FLOODING", "MED"):
                return cls.MODERATE
            if v_norm in ("SEVERE", "SEVERE FLOODING", "HIGH", "CRITICAL"):
                return cls.SEVERE
        return None


class Coordinates(BaseModel):
    lat: float
    lng: float


class Node(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    elevation_m: float
    description: Optional[str] = None


class RoadSegment(BaseModel):
    id: str
    source: str
    target: str
    name: str
    distance_km: float
    base_speed_kmh: float
    travel_time_min: float
    elevation_m: float
    flood_zone: str
    status: RoadStatus = RoadStatus.SAFE
    water_depth_cm: float = 0.0
    safety_penalty: float = 0.0
    is_blocked: bool = False
    coordinates: List[List[float]] = Field(default_factory=list)
    condition_notes: Optional[str] = None


class Shelter(BaseModel):
    id: str
    name: str
    address: str
    lat: float
    lng: float
    capacity: int
    current_occupancy: int
    available_capacity: int
    elevation_m: float
    safety_status: str
    has_medical_support: bool = True
    is_pet_friendly: bool = True
    contact_phone: str = "Emergency Hotline: 911 / (555) 234-SAFE"


class RouteStep(BaseModel):
    step_number: int
    instruction: str
    road_name: str
    distance_km: float
    duration_min: float
    status: RoadStatus
    caution_notes: Optional[str] = None


class RouteDetail(BaseModel):
    route_name: str
    path_node_ids: List[str]
    road_segments: List[RoadSegment]
    total_distance_km: float
    estimated_time_min: float
    safety_score: float  # 0 to 100 (100 = perfectly safe)
    risk_level: str  # "LOW RISK", "MODERATE RISK", "HIGH RISK"
    route_cost: float
    geometry: List[List[float]]  # List of [lat, lng] for rendering
    instructions: List[RouteStep]
    is_recommended: bool = True


class AvoidedRoadInfo(BaseModel):
    road_id: str
    road_name: str
    status: RoadStatus
    water_depth_cm: float
    reason: str


class WhyThisRoute(BaseModel):
    summary: str
    avoided_roads: List[AvoidedRoadInfo]
    unsafe_roads_in_network: int
    blocked_roads_in_network: int
    shortest_path_distance_km: float
    recommended_path_distance_km: float
    delta_distance_km: float
    delta_time_min: float
    safety_advantage_pct: float
    rationale_bullet_points: List[str]


class NetworkStatistics(BaseModel):
    total_roads_evaluated: int
    safe_roads_count: int
    moderate_risk_roads_count: int
    high_risk_roads_count: int
    blocked_roads_count: int
    roads_avoided_count: int
    safety_score: float
    route_cost: float
    alternative_route_available: bool
    active_flood_severity: str


class EvacuationRequest(BaseModel):
    origin_name: Optional[str] = "Current Location"
    origin_lat: float
    origin_lng: float
    shelter_id: Optional[str] = "auto"  # "auto" or specific shelter ID
    custom_destination_name: Optional[str] = None
    custom_destination_lat: Optional[float] = None
    custom_destination_lng: Optional[float] = None
    flood_severity: FloodSeverity = FloodSeverity.MODERATE
    water_depth_cm: Optional[float] = 15.0
    rainfall_mm_hr: Optional[float] = 35.0  # mm per hour
    rainfall_duration_hours: Optional[float] = 3.0  # duration in hours
    soil_saturation: Optional[str] = "moderate"  # "dry", "moderate", "saturated", "overflowing"
    user_blocked_road_ids: Optional[List[str]] = Field(default_factory=list)
    user_reported_condition: Optional[str] = None
    algorithm: Optional[str] = "dijkstra"  # "dijkstra" or "astar"
    ai_confidence_buffer_pct: Optional[float] = 0.0  # Dynamic buffer percentage calculated by AI confidence model



class ShelterRanking(BaseModel):
    shelter: Shelter
    route_distance_km: float
    estimated_time_min: float
    route_safety_level: str
    safety_score: float
    is_recommended: bool
    recommendation_reason: str


class EvacuationPlanResponse(BaseModel):
    success: bool
    message: str
    overall_flood_risk: str  # "LOW", "MODERATE", "HIGH", "CRITICAL"
    assessment_summary: str
    recommended_route: Optional[RouteDetail] = None
    alternative_route: Optional[RouteDetail] = None
    selected_shelter: Optional[Shelter] = None
    candidate_shelters_ranked: List[ShelterRanking] = Field(default_factory=list)
    why_this_route: Optional[WhyThisRoute] = None
    statistics: Optional[NetworkStatistics] = None
    disclaimer: str
    all_roads: List[RoadSegment] = Field(default_factory=list)
    all_shelters: List[Shelter] = Field(default_factory=list)


class DynamicRerouteRequest(BaseModel):
    current_origin_lat: float
    current_origin_lng: float
    destination_shelter_id: str
    flood_severity: FloodSeverity = FloodSeverity.MODERATE
    newly_blocked_road_ids: List[str]
    simulation_label: Optional[str] = "Dynamic Road Blockage Simulation"


class SimulationScenario(BaseModel):
    id: str
    title: str
    subtitle: str
    description: str
    origin_lat: float
    origin_lng: float
    origin_name: str
    target_shelter_id: str
    initial_severity: FloodSeverity
    initial_blocked_roads: List[str]
    surge_blocked_roads: List[str]
    surge_description: str


class WeatherDayData(BaseModel):
    date: str  # YYYY-MM-DD
    day_offset: int  # -3, -2, -1, 0, 1, 2, 3
    day_label: str  # e.g., "3 Days Ago", "Today (Active)", "+1 Day Forecast"
    condition: str  # e.g., "Heavy Monsoon Downpour"
    precipitation_mm: float
    peak_rainfall_rate_mm_hr: float
    temp_max_c: float
    temp_min_c: float
    humidity_pct: int
    pressure_hpa: float
    wind_speed_kmh: float
    soil_saturation_pct: float
    flood_risk_level: str  # "LOW", "MODERATE", "HIGH", "SEVERE"
    confidence_score_pct: float  # 0 to 100
    is_forecast: bool


class AIConfidenceMetrics(BaseModel):
    overall_confidence_pct: float
    confidence_category: str  # "HIGH CONFIDENCE", "MODERATE CONFIDENCE", "LOW CONFIDENCE"
    horizon_decay_factor: float
    barometric_stability_index: float
    ensemble_precipitation_variance_mm: float
    soil_saturation_risk_multiplier: float
    ai_precautionary_buffer_pct: float
    rationale_bullet_points: List[str]
    routing_impact_summary: str


class WeatherTimelineResponse(BaseModel):
    location_name: str
    latitude: float
    longitude: float
    api_key_status: str
    active_day_offset: int
    days: List[WeatherDayData]
    ai_confidence: AIConfidenceMetrics


class MLFloodPredictRequest(BaseModel):
    region: Optional[str] = "chennai"
    rainfall_forecast_mm: float = 85.0
    rainfall_intensity_mmh: float = 25.0
    soil_saturation_state: Optional[str] = "saturated"
    forecast_lead_day: Optional[int] = 4
    origin_node_id: Optional[str] = None
    destination_shelter_id: Optional[str] = "auto"


class MedicalFacility(BaseModel):
    id: str
    name: str
    facility_type: str = "PHARMACY"  # "PHARMACY", "HOSPITAL", "DISPENSARY"
    address: str
    lat: float
    lng: float
    elevation_m: float
    phone: str = "108 Emergency / Local Medical Helpline"
    is_open_24x7: bool = True
    emergency_supplies: List[str] = Field(default_factory=lambda: ["First Aid Kits", "Essential Antibiotics", "Insulin", "Water Purification Tablets", "IV Fluids", "Bandages"])


class FoodFacility(BaseModel):
    id: str
    name: str
    facility_type: str = "RATION_DEPOT"  # "RATION_DEPOT", "RELIEF_KITCHEN", "GROCERY_STORE"
    address: str
    lat: float
    lng: float
    elevation_m: float
    phone: str = "1967 Toll-Free Civil Supplies Helpline"
    is_operating: bool = True
    available_rations: List[str] = Field(default_factory=lambda: ["Packaged Drinking Water", "High-Energy Biscuits", "Rice & Wheat Grains", "Baby Food / Infant Formula", "Ready-to-Eat Meal Packets"])


class PreventiveMeasures(BaseModel):
    immediate_actions: List[str]
    property_protection: List[str]
    vulnerable_residents: List[str]
    emergency_supplies_kit: List[str]
    vehicle_and_travel: List[str]
    safe_zone_guidance: List[str]


class CityFloodRiskAssessmentResponse(BaseModel):
    city_name: str
    state: str
    latitude: float
    longitude: float
    river_basin: str
    flood_risk_level: str  # "HIGH RISK", "MODERATE RISK", "LOW RISK / SAFE"
    flood_risk_badge_color: str
    risk_score_pct: float
    rainfall_forecast_mm: float
    rainfall_intensity_mmh: float
    soil_saturation_pct: float
    atmospheric_confidence_pct: float
    inundation_expected: bool
    risk_summary: str
    preventive_measures: PreventiveMeasures
    nearby_medical_facilities: List[MedicalFacility]
    nearby_food_facilities: List[FoodFacility]
    recommended_shelters: List[Shelter]
    safe_evacuation_route_summary: str



