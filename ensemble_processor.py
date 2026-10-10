"""
Processes Open-Meteo Ensemble forecasts.
Calculates ensemble mean, spread (standard deviation), percentiles (P10, P25, P75, P90),
prediction intervals, and member exceedance statistics for Days 3 through 10.
"""

import math
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional
import numpy as np


class EnsembleProcessor:
    @staticmethod
    def process_forecast(
        raw_ensemble: Dict[str, Any],
        variable: str,
        start_lead_day: int = 3,
        end_lead_day: int = 10,
        error_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Parses raw daily ensemble forecast and computes statistical metrics.
        """
        daily = raw_ensemble.get("daily", {})
        units = raw_ensemble.get("daily_units", {})
        times = daily.get("time", [])

        if not times:
            raise ValueError("No forecast time series returned from Ensemble API.")

        # Identify base variable key
        var_map = {
            "wind_speed_10m": "wind_speed_10m_max",
            "wind_speed": "wind_speed_10m_max",
            "temperature_2m": "temperature_2m_max",
            "temperature": "temperature_2m_max",
            "precipitation": "precipitation_sum"
        }
        target_var = var_map.get(variable, variable)

        # Collect all member keys
        base_series = daily.get(target_var, [])
        member_keys = [
            k for k in daily.keys()
            if k.startswith(f"{target_var}_member") or (k == target_var and base_series is not None)
        ]
        # Distinguish pure members
        pure_member_keys = [k for k in daily.keys() if k.startswith(f"{target_var}_member")]
        if not pure_member_keys:
            # Fallback if model returned only deterministic or aggregated
            pure_member_keys = [target_var]

        total_members_count = len(pure_member_keys)
        unit_str = units.get(target_var, "")

        today = datetime.now(timezone.utc).date()
        daily_records = []

        for idx, date_str in enumerate(times):
            f_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            lead_day = (f_date - today).days

            # Filter for requested horizon (default Day 3 through Day 10)
            if lead_day < start_lead_day or lead_day > end_lead_day:
                continue

            # Gather values from all members for this day
            member_values = []
            for m_key in pure_member_keys:
                val = daily[m_key][idx]
                if val is not None and not math.isnan(val):
                    member_values.append(float(val))

            if not member_values:
                # If no member values, check deterministic
                det_val = base_series[idx] if idx < len(base_series) else None
                if det_val is not None:
                    member_values = [float(det_val)]

            if not member_values:
                continue

            arr = np.array(member_values, dtype=float)
            mean_val = float(np.mean(arr))
            median_val = float(np.median(arr))
            std_spread = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
            min_val = float(np.min(arr))
            max_val = float(np.max(arr))
            p10 = float(np.percentile(arr, 10))
            p25 = float(np.percentile(arr, 25))
            p75 = float(np.percentile(arr, 75))
            p90 = float(np.percentile(arr, 90))
            iqr = p75 - p25
            interval_80 = p90 - p10

            # Deterministic/operational value
            det_val = float(base_series[idx]) if idx < len(base_series) and base_series[idx] is not None else mean_val

            # Exceedance count relative to threshold
            exceed_count = 0
            exceed_ratio = 0.0
            if error_threshold is not None and error_threshold > 0:
                # Number of members differing from mean by more than error_threshold
                exceed_count = int(np.sum(np.abs(arr - mean_val) > error_threshold))
                exceed_ratio = float(exceed_count / len(arr))

            daily_records.append({
                "date": date_str,
                "lead_day": lead_day,
                "deterministic_forecast": round(det_val, 2),
                "ensemble_mean": round(mean_val, 2),
                "ensemble_median": round(median_val, 2),
                "ensemble_spread": round(std_spread, 2),
                "min": round(min_val, 2),
                "max": round(max_val, 2),
                "p10": round(p10, 2),
                "p25": round(p25, 2),
                "p75": round(p75, 2),
                "p90": round(p90, 2),
                "iqr": round(iqr, 2),
                "interval_80": round(interval_80, 2),
                "member_count": len(member_values),
                "member_values": [round(v, 2) for v in member_values],
                "exceed_count": exceed_count,
                "exceed_ratio": round(exceed_ratio, 3)
            })

        return {
            "variable": target_var,
            "unit": unit_str,
            "total_members": total_members_count,
            "start_lead_day": start_lead_day,
            "end_lead_day": end_lead_day,
            "records": daily_records
        }
