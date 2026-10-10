import copy
from typing import List, Tuple, Dict, Any, Optional
from models.schemas import RoadSegment, RoadStatus, FloodSeverity, NetworkStatistics


def evaluate_road_status_and_penalty(
    segment: RoadSegment,
    flood_severity: FloodSeverity,
    user_water_depth_cm: Optional[float] = None,
    user_blocked_ids: Optional[List[str]] = None,
    rainfall_mm_hr: Optional[float] = None,
    rainfall_duration_hours: Optional[float] = None,
    soil_saturation: Optional[str] = "moderate",
    ai_confidence_buffer_pct: Optional[float] = 0.0,
) -> Tuple[RoadStatus, float, float, bool, str]:
    """
    Evaluates an individual road segment's status, water depth, penalty, and blocked condition.
    Calculates physical runoff pooling based on:
    - Rainfall rate (mm/hr)
    - Rainfall duration (hours)
    - Soil saturation (dry / moderate / saturated / overflowing)
    - Road elevation & flood basin vulnerability
    Returns: (status, safety_penalty, calculated_water_depth_cm, is_blocked, reason)
    """
    user_blocked_ids = user_blocked_ids or []

    # 1. Direct user blockage overrides
    is_manually_blocked = segment.id in user_blocked_ids
    if is_manually_blocked:
        return (
            RoadStatus.BLOCKED,
            9999.0,
            max(50.0, user_water_depth_cm or 50.0),
            True,
            "Manually closed by emergency incident report or user barricade."
        )

    # 2. Derive rainfall precipitation volume
    rain_rate = rainfall_mm_hr if rainfall_mm_hr is not None else (
        8.0 if flood_severity == FloodSeverity.LOW else (
            35.0 if flood_severity == FloodSeverity.MODERATE else (
                75.0 if flood_severity == FloodSeverity.SEVERE else 0.0
            )
        )
    )
    rain_duration = rainfall_duration_hours if rainfall_duration_hours is not None else 3.0
    total_rain_mm = rain_rate * rain_duration

    sat_mult = 1.0
    if soil_saturation == "saturated":
        sat_mult = 1.35
    elif soil_saturation == "overflowing":
        sat_mult = 1.75
    elif soil_saturation == "dry":
        sat_mult = 0.65

    elev = segment.elevation_m
    zone = segment.flood_zone

    # Hydrologic pooling model: Low basins pool rapidly; ridges drain instantly
    if elev <= 10.0:  # River basin & low confluence
        runoff_depth_cm = (total_rain_mm / 10.0) * 3.6 * sat_mult
    elif elev <= 15.0:  # Lowland fringe & canal zone
        runoff_depth_cm = (total_rain_mm / 10.0) * 2.2 * sat_mult
    elif elev <= 25.0:  # Midland terrace
        runoff_depth_cm = (total_rain_mm / 10.0) * 1.1 * sat_mult
    elif elev <= 35.0:  # Foothill slopes
        runoff_depth_cm = (total_rain_mm / 10.0) * 0.4 * sat_mult
    else:  # Highland ridges (> 35m)
        runoff_depth_cm = (total_rain_mm / 10.0) * 0.08 * sat_mult

    effective_depth = max(runoff_depth_cm, user_water_depth_cm if user_water_depth_cm is not None else 0.0)

    # Inundation categorization thresholds
    if effective_depth >= 40.0:
        if elev <= 12.0:
            status = RoadStatus.BLOCKED
            penalty = 9999.0
            depth = round(effective_depth, 1)
            blocked = True
            notes = f"Submerged low-lying causeway ({effective_depth:.0f} cm water in {zone}). Excluded."
        else:
            status = RoadStatus.HIGH_RISK
            penalty = 22.0
            depth = round(min(effective_depth, 28.0), 1)
            blocked = False
            notes = f"Elevated corridor ({elev:.0f}m elev) shedding runoff ({depth:.0f} cm water). High-clearance passage only."
    elif effective_depth >= 25.0:
        status = RoadStatus.HIGH_RISK
        penalty = 14.0
        depth = round(effective_depth, 1)
        blocked = False
        notes = f"Severe standing water ({effective_depth:.0f} cm). Severe hydroplaning risk."
    elif effective_depth >= 10.0:
        status = RoadStatus.MODERATE_RISK
        penalty = 4.0
        depth = round(effective_depth, 1)
        blocked = False
        notes = f"Moderate runoff ({effective_depth:.0f} cm). Passable with caution."
    else:
        status = RoadStatus.SAFE
        penalty = 0.2
        depth = round(effective_depth, 1)
        blocked = False
        notes = f"Elevated road surface safe ({effective_depth:.0f} cm runoff). Nominal traction."

    # Weather Confidence Decoupling:
    # Road inundation and structural traversal status are determined purely by physical terrain hydrology.
    # Weather forecast uncertainty informs emergency monitoring posture, strictly decoupled from road flooding.
    return (status, penalty, depth, blocked, notes)


def assess_network(
    base_segments: List[RoadSegment],
    flood_severity: FloodSeverity,
    user_water_depth_cm: Optional[float] = None,
    user_blocked_ids: Optional[List[str]] = None,
    user_notes: Optional[str] = None,
    rainfall_mm_hr: Optional[float] = None,
    rainfall_duration_hours: Optional[float] = None,
    soil_saturation: Optional[str] = "moderate",
    ai_confidence_buffer_pct: Optional[float] = 0.0,
) -> Tuple[List[RoadSegment], str, str, NetworkStatistics]:
    """
    Evaluates the entire road network under current simulated/reported flood conditions.
    """
    updated_segments: List[RoadSegment] = []
    safe_cnt = 0
    mod_cnt = 0
    high_cnt = 0
    blocked_cnt = 0

    effective_blocked = set(user_blocked_ids or [])
    # Detect all reciprocal return segments for any blocked road
    blocked_endpoints = set()
    for seg in base_segments:
        if seg.id in effective_blocked:
            blocked_endpoints.add((seg.source, seg.target))
            blocked_endpoints.add((seg.target, seg.source))

    if blocked_endpoints:
        for seg in base_segments:
            if (seg.source, seg.target) in blocked_endpoints:
                effective_blocked.add(seg.id)

    effective_blocked_list = list(effective_blocked)

    for seg in base_segments:
        new_seg = copy.deepcopy(seg)
        status, penalty, depth, blocked, notes = evaluate_road_status_and_penalty(
            segment=new_seg,
            flood_severity=flood_severity,
            user_water_depth_cm=user_water_depth_cm,
            user_blocked_ids=effective_blocked_list,
            rainfall_mm_hr=rainfall_mm_hr,
            rainfall_duration_hours=rainfall_duration_hours,
            soil_saturation=soil_saturation,
            ai_confidence_buffer_pct=ai_confidence_buffer_pct,
        )

        new_seg.status = status
        new_seg.safety_penalty = penalty
        new_seg.water_depth_cm = depth
        new_seg.is_blocked = blocked
        new_seg.condition_notes = notes

        if status == RoadStatus.SAFE:
            safe_cnt += 1
        elif status == RoadStatus.MODERATE_RISK:
            mod_cnt += 1
        elif status == RoadStatus.HIGH_RISK:
            high_cnt += 1
        elif status == RoadStatus.BLOCKED:
            blocked_cnt += 1

        updated_segments.append(new_seg)

    total_roads = len(updated_segments)
    hazard_ratio = (blocked_cnt * 2 + high_cnt * 1.5 + mod_cnt * 0.8) / max(1, total_roads * 2)

    total_rain = (rainfall_mm_hr or 35.0) * (rainfall_duration_hours or 3.0)

    if hazard_ratio >= 0.45 or blocked_cnt >= 3:
        overall_risk = "CRITICAL"
        summary = (
            f"FLOOD / ROAD RISK: CRITICAL. Heavy precipitation ({total_rain:.0f}mm accumulated) has submerged "
            f"{blocked_cnt} road segments in low-lying river and canal corridors. The routing engine has excluded all "
            f"blocked roads and routed through elevated highland ridges."
        )
    elif hazard_ratio >= 0.25 or blocked_cnt >= 1:
        overall_risk = "HIGH"
        summary = (
            f"FLOOD / ROAD RISK: HIGH. {blocked_cnt} roads are impassable due to runoff, and {high_cnt} "
            f"arterial roads present severe hydroplaning hazards. Routing has prioritized elevated bypass paths."
        )
    elif hazard_ratio >= 0.12 or mod_cnt >= 2:
        overall_risk = "MODERATE"
        summary = (
            f"FLOOD / ROAD RISK: MODERATE. Standing water affects {mod_cnt} road segments. "
            f"Roads are passable with reduced speed. Safety penalties applied to bias toward higher ground."
        )
    else:
        overall_risk = "LOW"
        summary = (
            "FLOOD / ROAD RISK: LOW. All evaluated arterial routes are clear and safe for standard vehicular transit."
        )

    stats = NetworkStatistics(
        total_roads_evaluated=total_roads,
        safe_roads_count=safe_cnt,
        moderate_risk_roads_count=mod_cnt,
        high_risk_roads_count=high_cnt,
        blocked_roads_count=blocked_cnt,
        roads_avoided_count=blocked_cnt + high_cnt,
        safety_score=round(max(10.0, 100.0 - (hazard_ratio * 100.0)), 1),
        route_cost=0.0,
        alternative_route_available=True,
        active_flood_severity=flood_severity.value,
    )

    return updated_segments, overall_risk, summary, stats
