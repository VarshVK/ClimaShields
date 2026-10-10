"""
Disaster Preparedness Contingency Advisor for KPR09.
Translates Medium-Range Rainfall Forecasts and AI Confidence Classifications
into concrete, actionable emergency civil defense protocols.
Strictly distinguishes forecast confidence from flood certainty.
"""

from typing import Any, Dict, List


class DisasterPreparednessAdvisor:
    @staticmethod
    def generate_advisory(
        scored_records: List[Dict[str, Any]],
        location_name: str = "Selected Region",
        variable: str = "precipitation",
        unit: str = "mm"
    ) -> Dict[str, Any]:
        """
        Generates emergency disaster preparedness and contingency decision support.
        Maps (Forecast Rainfall Magnitude, AI Confidence State) to civil defense actions.
        """
        day_advisories = []
        highest_level = 0
        max_rain = 0.0
        most_critical_day = None

        for rec in scored_records:
            date_str = rec.get("date", "")
            lead_d = rec.get("lead_day", 3)
            mean_rain = rec.get("ensemble_mean", 0.0)
            median_rain = rec.get("ensemble_median", mean_rain)
            p10 = rec.get("p10", 0.0)
            p90 = rec.get("p90", mean_rain)
            spread = rec.get("ensemble_spread", 0.0)
            conf_score = rec.get("confidence_score", 70)
            conf_cat = rec.get("confidence_category", "Higher Confidence" if conf_score >= 60 else "Lower Confidence")

            if mean_rain > max_rain:
                max_rain = mean_rain

            # Decision Logic Matrix:
            # 1. Rain intensity threshold
            # Heavy: >= 40mm; Moderate: 15-40mm; Light: 3-15mm; Trace/None: < 3mm
            if mean_rain >= 40.0:
                rain_category = "Heavy Rainfall Threat"
                if conf_cat == "Higher Confidence":
                    action_level = 3
                    level_name = "Level 3: Active Preparation & Pre-Alert"
                    badge_color = "#ef4444"
                    action_title = "Pre-Position Evacuation Assets & Clear Sluice Gates"
                    action_detail = (
                        f"High confidence forecast of heavy rain ({mean_rain:.1f} mm, spread ±{spread:.1f} mm). "
                        "Mobilize regional SDRF/NDRF teams to vulnerable lowlands, open storm drainage gates, "
                        "and verify emergency shelter readiness. Pre-evacuation staging recommended."
                    )
                    contingency_note = "Model runs show strong convergence on heavy downpour; high likelihood of urban runoff."
                elif conf_cat == "Lower Confidence":
                    action_level = 2
                    level_name = "Level 2: Heightened Monitoring & Contingency Standby"
                    badge_color = "#f97316"
                    action_title = "Maintain Standby & Intensify Radar Tracking (Do Not Order Premature Evacuation)"
                    action_detail = (
                        f"Forecast indicates heavy rain ({mean_rain:.1f} mm), but LOW forecast confidence (high spread: {p10:.1f} to {p90:.1f} mm). "
                        "Avoid costly premature evacuations which cause panic. Place emergency services on 2-hour standby, "
                        "increase automatic weather station polling to 15-minute intervals, and prepare alternate evacuation routes."
                    )
                    contingency_note = "Large ensemble dispersion indicates uncertain cloudburst track or timing. Decision: Enhanced surveillance without panic."
                else:
                    action_level = 1
                    level_name = "Level 1: Ground Sensor Telemetry Check"
                    badge_color = "#94a3b8"
                    action_title = "Rely on In-Situ IMD Telemetry"
                    action_detail = "Insufficient ensemble data. Base medium-range decisions on regional radar and rain gauge observations."
                    contingency_note = "Missing numerical model members."
            elif mean_rain >= 15.0:
                rain_category = "Moderate Rainfall"
                if conf_cat == "Higher Confidence":
                    action_level = 1
                    level_name = "Level 1: Routine Urban Stormwater Operations"
                    badge_color = "#0284c7"
                    action_title = "Clear Street Gutters & Deploy Pumping Units"
                    action_detail = (
                        f"Confident moderate rain ({mean_rain:.1f} mm, spread ±{spread:.1f} mm). "
                        "Ensure municipal drainage pumps are operational at known urban underpasses. Normal municipal protocols."
                    )
                    contingency_note = "Expected rainfall within standard urban infiltration and drainage design capacities."
                else:
                    action_level = 1
                    level_name = "Level 1: Precautionary Catchment Monitoring"
                    badge_color = "#f59e0b"
                    action_title = "Monitor Upstream Reservoir Inflow"
                    action_detail = (
                        f"Moderate rain predicted ({mean_rain:.1f} mm) with lower confidence (range {p10:.1f} to {p90:.1f} mm). "
                        "Check upstream dam reservoir levels to buffer against unexpected surge."
                    )
                    contingency_note = "Ensemble tails range from dry spells to localized downpours."
            else:
                rain_category = "Light / Low Precipitation"
                action_level = 0
                level_name = "Level 0: Baseline Readiness"
                badge_color = "#10b981"
                action_title = "Standard Civil Defense Posture"
                action_detail = f"Low precipitation expected ({mean_rain:.1f} mm). Normal municipal operations."
                contingency_note = "No meteorological flood hazard indicated."

            if action_level > highest_level:
                highest_level = action_level
                most_critical_day = date_str

            day_advisories.append({
                "date": date_str,
                "lead_day": lead_d,
                "predicted_rainfall_mm": round(mean_rain, 1),
                "rainfall_mean_mm": round(mean_rain, 1),
                "rainfall_p10_mm": round(p10, 1),
                "rainfall_p90_mm": round(p90, 1),
                "rainfall_range_p10_p90": f"{p10:.1f} - {p90:.1f} mm",
                "ensemble_spread_mm": round(spread, 1),
                "confidence_score": conf_score,
                "confidence_category": conf_cat,
                "rain_category": rain_category,
                "action_level": action_level,
                "alert_level": action_level,
                "level_name": level_name,
                "alert_title": level_name,
                "badge_color": badge_color,
                "alert_color": badge_color,
                "action_title": action_title,
                "action_detail": action_detail,
                "key_rationale": action_detail,
                "contingency_note": contingency_note,
                "contingency_actions": [action_title, action_detail, contingency_note]
            })

        overall_label = {
            3: "LEVEL 3: ACTIVE PRE-ALERT & EVACUATION ASSET MOBILIZATION",
            2: "LEVEL 2: HEIGHTENED MONITORING & CONTINGENCY STANDBY",
            1: "LEVEL 1: ROUTINE URBAN STORMWATER ADVISORY",
            0: "LEVEL 0: BASELINE NORMAL READINESS"
        }.get(highest_level, "LEVEL 0: BASELINE READINESS")

        overall_headline = (
            f"Overall Decision Status: {overall_label}" if highest_level > 0
            else "Baseline Normal Posture: No immediate meteorological flood emergency indicated across medium-range horizon (Days 3-10)."
        )

        return {
            "overall_action_level": highest_level,
            "overall_status_label": overall_label,
            "overall_headline": overall_headline,
            "summary": {
                "highest_alert_level": highest_level,
                "highest_alert_title": overall_label,
                "highest_alert_color": {3: "#ef4444", 2: "#f97316", 1: "#0284c7", 0: "#10b981"}.get(highest_level, "#10b981"),
                "headline": overall_headline,
                "advisory_count": len(day_advisories),
            },
            "most_critical_day": most_critical_day,
            "max_predicted_rainfall_mm": round(max_rain, 1),
            "location_name": location_name,
            "timeline_advisories": day_advisories,
            "advisories": day_advisories,
            "contingency_matrix_rules": [
                {
                    "forecast_condition": "Heavy Rain (≥40mm) + HIGHER Confidence",
                    "action": "Level 3: Pre-position rescue boats & staging areas, verify high-ground shelter readiness, alert vulnerable colonies.",
                    "rationale": "High NWP convergence justifies pre-event mobilization costs."
                },
                {
                    "forecast_condition": "Heavy Rain (≥40mm) + LOWER Confidence",
                    "action": "Level 2: Heightened radar polling, 2-hour crew standby, review alternate routes; DO NOT order preemptive evacuation.",
                    "rationale": "High forecast uncertainty means evacuation orders risk false alarms and civic disruption. Decision shifts to agile contingency standby."
                },
                {
                    "forecast_condition": "Moderate Rain (15-40mm) + Any Confidence",
                    "action": "Level 1: Routine municipal drain clearance, underpass pump verification, upstream dam level logging.",
                    "rationale": "Standard urban stormwater capacity adequate; prevent local waterlogging."
                },
                {
                    "forecast_condition": "Low Rain (<15mm) + Any Confidence",
                    "action": "Level 0: Baseline readiness, routine civic maintenance.",
                    "rationale": "No flood hazard trigger."
                }
            ]
        }
