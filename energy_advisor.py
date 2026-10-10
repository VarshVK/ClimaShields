"""
Renewable Energy Advisor Module — Wind Energy Demonstration.
Provides wind energy operators with actionable scenario planning recommendations
when wind speed forecasts have high uncertainty / low confidence.
Strictly avoids unverified generation or financial claims.
"""

from typing import Any, Dict, List


class WindEnergyAdvisor:
    @staticmethod
    def generate_advisory(scored_records: List[Dict[str, Any]], unit: str = "km/h") -> Dict[str, Any]:
        """
        Generates renewable energy operational advisory for wind speed forecasts.
        """
        low_confidence_days = []
        moderate_confidence_days = []
        all_day_summaries = []

        is_kmh = "km" in unit.lower()

        for rec in scored_records:
            date_str = rec["date"]
            lead_d = rec["lead_day"]
            mean_val = rec["ensemble_mean"]
            median_val = rec["ensemble_median"]
            p10 = rec["p10"]
            p90 = rec["p90"]
            spread = rec["ensemble_spread"]
            conf = rec["confidence_score"]
            risk = rec["risk_status"]
            explanation = rec["explanation"]

            # Speed conversions
            if is_kmh:
                speed_ms_mean = round(mean_val / 3.6, 2)
                speed_ms_p10 = round(p10 / 3.6, 2)
                speed_ms_p90 = round(p90 / 3.6, 2)
                speed_display = f"{mean_val} km/h ({speed_ms_mean} m/s)"
                uncertainty_display = f"{p10} to {p90} km/h ({speed_ms_p10} to {speed_ms_p90} m/s)"
            else:
                speed_ms_mean = mean_val
                speed_ms_p10 = p10
                speed_ms_p90 = p90
                speed_display = f"{mean_val} m/s"
                uncertainty_display = f"{p10} to {p90} m/s"

            # Turbine operational regime context (standard IEC Class II turbine cut-in ~3.0 m/s, rated ~11.5 m/s, cut-out ~25 m/s)
            regime_note = ""
            if speed_ms_p10 < 3.5 and speed_ms_p90 >= 3.5:
                regime_note = "Ensemble spans the turbine cut-in boundary (3.0-3.5 m/s), creating high risk of intermittent zero-generation hours."
            elif speed_ms_p10 < 11.5 and speed_ms_p90 >= 11.5:
                regime_note = "Ensemble spans the turbine rated speed threshold (11.5 m/s), meaning output could vary from partial load to full rated capacity."
            elif speed_ms_p90 >= 22.0:
                regime_note = "Ensemble tail reaches storm / high-wind cut-out range (22-25 m/s); potential automated turbine feathering risk."

            # Actionable recommendations
            recommendations = []
            if conf < 45: # High Risk / Low Confidence
                recommendations.append(
                    f"Evaluate dual generation scenarios: simulate both conservative low-generation scenario (P10: {speed_ms_p10} m/s) and high-generation scenario (P90: {speed_ms_p90} m/s)."
                )
                recommendations.append(
                    "Do not lock in fixed forward day-ahead delivery commitments solely on the ensemble mean."
                )
                recommendations.append(
                    "Review reserve dispatch requirements and retain battery / peaking flexibility to absorb sudden ramp errors."
                )
                recommendations.append(
                    "Re-evaluate wind speed distribution upon the next 12-hour NWP model cycle update."
                )
            elif conf < 70: # Moderate Risk
                recommendations.append(
                    f"Plan with asymmetric uncertainty: review generation variance between {speed_ms_p10} m/s and {speed_ms_p90} m/s."
                )
                recommendations.append(
                    "Maintain standard balancing reserves; monitor intra-day ensemble member spread for convergence."
                )
            else: # Low Risk / High Confidence
                recommendations.append(
                    "Ensemble spread is narrow; standard baseline scheduling can proceed with regular monitoring."
                )

            summary_item = {
                "date": date_str,
                "lead_day": lead_d,
                "expected_wind_speed": speed_display,
                "mean_val": mean_val,
                "median_val": median_val,
                "uncertainty_range": uncertainty_display,
                "p10": p10,
                "p90": p90,
                "spread": spread,
                "confidence_score": conf,
                "risk_status": risk,
                "regime_note": regime_note,
                "warning_reason": explanation,
                "recommendations": recommendations
            }

            all_day_summaries.append(summary_item)
            if conf < 45:
                low_confidence_days.append(summary_item)
            elif conf < 70:
                moderate_confidence_days.append(summary_item)

        return {
            "title": "Wind Energy Operational Reliability Advisory",
            "demonstration_scope": "Wind speed forecasts for wind energy generation planning",
            "total_days_evaluated": len(scored_records),
            "low_confidence_count": len(low_confidence_days),
            "moderate_confidence_count": len(moderate_confidence_days),
            "high_confidence_count": len(scored_records) - len(low_confidence_days) - len(moderate_confidence_days),
            "action_required": len(low_confidence_days) > 0,
            "low_confidence_days": low_confidence_days,
            "all_days": all_day_summaries,
            "methodology_disclaimer": (
                "Operational recommendations are derived from meteorological numerical weather prediction (NWP) ensemble spread "
                "and calibrated historical forecast error distributions. Actual turbine generation, wake losses, curtailment constraints, "
                "and financial reserves require site-specific SCADA telemetry, turbine power curves, and PPA contract rules."
            )
        }
