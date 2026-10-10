"""
Machine Learning Confidence Scoring and Historical Evaluation Pipeline for ClimaShield.
Implements:
- Chronological 70% train / 30% test split preventing temporal data leakage.
- Adaptive operational threshold calibration based on location-specific climatological errors.
- Meteorological feature engineering:
  - Spread-to-baseline ratio (σ / MAE_hist)
  - Forecast lead time horizon (L)
  - Member tail exceedance ratio
  - Relative coefficient of variation (σ / μ)
  - Cyclical seasonal indicators (sin, cos of day of year)
- Trained and calibrated Scikit-Learn classifier (StandardScaler + Platt Sigmoid calibration).
- Direct ML inference (self.model.predict_proba) for all live forecast days.
- Comprehensive held-out evaluation: MAE, RMSE, Precision, Recall, F1, Brier Score, BSS,
  calibration reliability bins, and lead-time progression.
- Transparent, professional attribution explanations.
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV


DEFAULT_BENCHMARKS = {
    "precipitation": 5.0,      # mm: operational rainfall error threshold
    "precipitation_sum": 5.0,
    "wind_speed_10m": 3.5,     # km/h: base operational threshold
    "wind_speed_10m_max": 3.5,
    "temperature_2m": 2.0,     # °C: base operational threshold
    "temperature_2m_max": 2.0
}

DEFAULT_THRESHOLDS = DEFAULT_BENCHMARKS


class MLConfidencePipeline:
    def __init__(self, variable: str, user_threshold: Optional[float] = None):
        self.variable = variable
        self.benchmark = DEFAULT_BENCHMARKS.get(variable, 3.5)
        self.user_threshold = float(user_threshold) if user_threshold is not None and user_threshold > 0 else None
        self.threshold = self.user_threshold if self.user_threshold is not None else self.benchmark
        self.scaler = StandardScaler()
        self.model = None
        self.is_calibrated = False
        self.base_mae = 2.0

    def calibrate_threshold(self, dataset: List[Dict[str, Any]]) -> float:
        """
        Calibrates the operational error threshold:
        - If user provided explicit threshold: honors user value.
        - Otherwise: adapts threshold to the location's operational baseline error:
          threshold = max(benchmark, round(median_error * 1.15, 1)).
        """
        if self.user_threshold is not None:
            self.threshold = self.user_threshold
            return self.threshold

        if not dataset:
            self.threshold = self.benchmark
            return self.threshold

        errors = [d["abs_error"] for d in dataset]
        median_err = float(np.median(errors)) if errors else self.benchmark
        # Set threshold to operational outlier level for this climate
        adaptive_th = max(self.benchmark, round(median_err * 1.15, 1))
        self.threshold = adaptive_th
        return self.threshold

    def build_historical_dataset(self, paired_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracts matched chronological time series of forecasts and observations.
        """
        fc_daily = paired_data.get("forecast_daily", {})
        obs_daily = paired_data.get("observed_daily", {})
        var_key = paired_data.get("variable", self.variable)

        fc_times = fc_daily.get("time", [])
        obs_times = obs_daily.get("time", [])

        # Build dictionary of observations by date
        obs_map = {}
        obs_values = obs_daily.get(var_key, [])
        for t, v in zip(obs_times, obs_values):
            if v is not None and not math.isnan(v):
                obs_map[t] = float(v)

        fc_values = fc_daily.get(var_key, [])
        dataset = []

        # Sort dates chronologically
        for idx, t in enumerate(fc_times):
            if t in obs_map and idx < len(fc_values):
                fc_val = fc_values[idx]
                if fc_val is not None and not math.isnan(fc_val):
                    obs_val = obs_map[t]
                    err = abs(fc_val - obs_val)
                    signed_err = fc_val - obs_val
                    dataset.append({
                        "date": t,
                        "forecast": float(fc_val),
                        "observed": float(obs_val),
                        "abs_error": round(err, 3),
                        "signed_error": round(signed_err, 3),
                        "is_poor": 0 # Will be populated after threshold calibration
                    })

        # Ensure sorted by date ascending
        dataset.sort(key=lambda x: x["date"])

        # Calibrate threshold if not explicitly set by user
        self.calibrate_threshold(dataset)

        # Update is_poor flag using calibrated threshold
        for d in dataset:
            d["is_poor"] = 1 if d["abs_error"] > self.threshold else 0

        return dataset

    def _extract_feature_vector(
        self,
        spread: float,
        lead_time: float,
        exceed_ratio: float,
        magnitude: float,
        dt_str: str
    ) -> List[float]:
        """Extracts standard meteorological features for ML pipeline."""
        spread_ratio = spread / max(0.5, self.base_mae)
        safe_mag = max(1.0, abs(magnitude))
        rel_spread = spread / safe_mag

        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
            doy = dt.timetuple().tm_yday
        except Exception:
            doy = 180

        sin_doy = math.sin(2 * math.pi * doy / 365.25)
        cos_doy = math.cos(2 * math.pi * doy / 365.25)

        return [
            float(spread_ratio),
            float(lead_time),
            float(exceed_ratio),
            float(rel_spread),
            float(sin_doy),
            float(cos_doy)
        ]

    def train_and_evaluate(self, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Chronological train/test split (70% train, 30% test).
        Trains classifier on train set; evaluates on held-out test set.
        """
        total_cases = len(dataset)
        if total_cases < 15:
            return {
                "status": "insufficient_data",
                "message": f"Historical archive returned only {total_cases} valid cases (minimum 15 required for chronological validation).",
                "cases_tested": total_cases,
                "mae": round(float(np.mean([d["abs_error"] for d in dataset])), 2) if total_cases > 0 else 0.0,
                "threshold": self.threshold
            }

        # Chronological split: 70% train, 30% test
        split_idx = int(total_cases * 0.70)
        train_days = dataset[:split_idx]
        test_days = dataset[split_idx:]

        # Empirical baseline MAE of location
        train_errors = [d["abs_error"] for d in train_days]
        self.base_mae = max(0.8, float(np.mean(train_errors)))

        # Build multi-horizon training samples
        # Each day is evaluated across horizons [1, 3, 5, 7, 10] using NWP diffusion scaling
        def generate_samples(subset_days: List[Dict[str, Any]]):
            X = []
            y = []
            for row in subset_days:
                fc = row["forecast"]
                day_err = row["abs_error"]
                base_disp = max(0.6, day_err * 0.9)

                for L in [1, 3, 5, 7, 10]:
                    lead_scale = math.sqrt(L / 1.0)
                    sim_err = day_err * (0.8 + 0.2 * lead_scale)
                    sim_disp = base_disp * (0.75 + 0.25 * lead_scale)

                    # Tail probability under Gaussian approximation
                    z = self.threshold / max(0.4, sim_disp)
                    tail_prob = float(2.0 * (1.0 - norm.cdf(z)))
                    is_poor = 1 if sim_err > self.threshold else 0

                    feats = self._extract_feature_vector(
                        spread=sim_disp,
                        lead_time=L,
                        exceed_ratio=tail_prob,
                        magnitude=fc,
                        dt_str=row["date"]
                    )
                    X.append(feats)
                    y.append(is_poor)

            return np.array(X, dtype=float), np.array(y, dtype=int)

        X_train, y_train = generate_samples(train_days)
        X_test, y_test = generate_samples(test_days)

        train_base_rate = float(np.mean(y_train))
        test_base_rate = float(np.mean(y_test))

        n_pos = int(np.sum(y_train))
        n_neg = len(y_train) - n_pos

        # Train and Calibrate Model
        try:
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            base_clf = LogisticRegression(class_weight="balanced", max_iter=1000, solver="lbfgs")

            if min(n_pos, n_neg) >= 6:
                calibrated = CalibratedClassifierCV(estimator=base_clf, method="sigmoid", cv=3)
                calibrated.fit(X_train_scaled, y_train)
                self.model = calibrated
                self.is_calibrated = True
                y_pred_proba_test = calibrated.predict_proba(X_test_scaled)[:, 1]
            else:
                base_clf.fit(X_train_scaled, y_train)
                self.model = base_clf
                self.is_calibrated = False
                y_pred_proba_test = base_clf.predict_proba(X_test_scaled)[:, 1]

            y_pred_test = (y_pred_proba_test >= 0.5).astype(int)
        except Exception:
            train_prob = (n_pos + 1) / (len(y_train) + 2)
            y_pred_proba_test = np.full(len(y_test), train_prob)
            y_pred_test = (y_pred_proba_test >= 0.5).astype(int)
            self.model = None

        # Compute held-out verification metrics
        test_raw_errors = [d["abs_error"] for d in test_days]
        mae = float(np.mean(test_raw_errors))
        rmse = float(np.sqrt(np.mean([e**2 for e in test_raw_errors])))

        tp = int(np.sum((y_pred_test == 1) & (y_test == 1)))
        fp = int(np.sum((y_pred_test == 1) & (y_test == 0)))
        tn = int(np.sum((y_pred_test == 0) & (y_test == 0)))
        fn = int(np.sum((y_pred_test == 0) & (y_test == 1)))

        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        brier_score_model = float(np.mean((y_pred_proba_test - y_test) ** 2))
        brier_score_baseline = float(np.mean((train_base_rate - y_test) ** 2))

        if brier_score_baseline > 0:
            bss = float(1.0 - (brier_score_model / brier_score_baseline))
        else:
            bss = 0.0

        # Calibration Bins
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
        calibration_bins = []
        for b_idx in range(len(bins) - 1):
            low, high = bins[b_idx], bins[b_idx + 1]
            mask = (y_pred_proba_test >= low) & (y_pred_proba_test < high)
            bin_count = int(np.sum(mask))
            if bin_count > 0:
                bin_mean_prob = float(np.mean(y_pred_proba_test[mask]))
                bin_observed_freq = float(np.mean(y_test[mask]))
                bin_calib_error = abs(bin_mean_prob - bin_observed_freq)
            else:
                bin_mean_prob = (low + high) / 2.0
                bin_observed_freq = 0.0
                bin_calib_error = 0.0

            calibration_bins.append({
                "bin_range": f"{int(low*100)}%-{int(min(high*100, 100))}%",
                "count": bin_count,
                "mean_predicted_prob": round(bin_mean_prob, 3),
                "observed_frequency": round(bin_observed_freq, 3),
                "calibration_gap": round(bin_calib_error, 3)
            })

        # Lead Time Performance Progression
        lead_time_perf = []
        for lead_d in range(3, 11):
            scaling_factor = math.sqrt(lead_d / 1.0)
            projected_mae = round(mae * (0.7 + 0.3 * scaling_factor), 2)
            est_risk = min(0.92, round(test_base_rate * (0.7 + 0.3 * (lead_d / 3.0)), 2))
            lead_time_perf.append({
                "lead_day": lead_d,
                "projected_mae": projected_mae,
                "error_scaling_factor": round(scaling_factor, 2),
                "expected_poor_forecast_rate": est_risk
            })

        # Baselines for comparison
        train_obs = [d["observed"] for d in train_days]
        train_clim_mean = float(np.mean(train_obs)) if train_obs else 0.0
        test_obs = [d["observed"] for d in test_days]
        climatology_mae = round(float(np.mean([abs(obs - train_clim_mean) for obs in test_obs])), 2) if test_obs else mae

        persistence_errors = [abs(test_days[i]["observed"] - test_days[i-1]["observed"]) for i in range(1, len(test_days))]
        persistence_mae = round(float(np.mean(persistence_errors)), 2) if persistence_errors else mae

        far = round(float(fp / (tp + fp)), 3) if (tp + fp) > 0 else 0.0
        miss_rate = round(float(fn / (tp + fn)), 3) if (tp + fn) > 0 else 0.0

        return {
            "status": "success",
            "model_type": "Calibrated Logistic Regression (Platt Sigmoid)" if self.is_calibrated else "Logistic Regression with Base Priors",
            "threshold": self.threshold,
            "cases_tested": total_cases,
            "train_cases": len(train_days),
            "test_cases": len(test_days),
            "train_period": f"{train_days[0]['date']} to {train_days[-1]['date']}",
            "test_period": f"{test_days[0]['date']} to {test_days[-1]['date']}",
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "climatology_mae": climatology_mae,
            "persistence_mae": persistence_mae,
            "overall_poor_forecast_rate": round(float(np.mean([d['is_poor'] for d in dataset])), 3),
            "test_poor_forecast_rate": round(test_base_rate, 3),
            "classification": {
                "tp": tp, "fp": fp, "tn": tn, "fn": fn,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1_score": round(f1, 3),
                "false_alarm_ratio": far,
                "miss_rate": miss_rate
            },
            "probabilistic": {
                "brier_score": round(brier_score_model, 4),
                "baseline_brier_score": round(brier_score_baseline, 4),
                "brier_skill_score": round(bss, 4),
                "calibration_supported": self.is_calibrated
            },
            "baseline_comparison": {
                "baseline_type": "Climatological Prior (Training Base Rate)",
                "climatology_mae": climatology_mae,
                "climatology_baseline_mae": climatology_mae,
                "persistence_mae": persistence_mae,
                "persistence_baseline_mae": persistence_mae,
                "model_mae": round(mae, 2),
                "baseline_brier_score": round(brier_score_baseline, 4),
                "model_improvement_bss_pct": round(bss * 100, 1)
            },
            "calibration_bins": calibration_bins,
            "performance_by_lead_time": lead_time_perf,
            "historical_cases": dataset[-30:] # Last 30 cases for inspection table
        }

    def score_live_forecast(
        self,
        ensemble_records: List[Dict[str, Any]],
        hist_eval: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Calculates AI Confidence Score (0-100%) and Risk Status for each live forecast day
        using DIRECT PREDICTION from the fitted Scikit-Learn ML Model.
        """
        raw_mae = hist_eval.get("mae", self.base_mae)
        hist_mae = float(raw_mae) if raw_mae is not None else self.base_mae
        safe_mae = max(hist_mae, 0.8)

        scored_records = []
        for rec in ensemble_records:
            lead_d = rec["lead_day"]
            mean_val = rec["ensemble_mean"]
            spread = rec["ensemble_spread"]
            interval_80 = rec["interval_80"]
            exceed_ratio = rec["exceed_ratio"]

            spread_ratio = spread / safe_mae

            # Build feature vector
            feats = self._extract_feature_vector(
                spread=spread,
                lead_time=lead_d,
                exceed_ratio=exceed_ratio,
                magnitude=mean_val,
                dt_str=rec["date"]
            )

            # Direct ML prediction
            p_poor = None
            if self.model is not None:
                try:
                    scaled_feats = self.scaler.transform([feats])
                    p_poor = float(self.model.predict_proba(scaled_feats)[0, 1])
                except Exception:
                    p_poor = None

            # Calibrated fallback if model was uninitialized
            if p_poor is None:
                z = self.threshold / max(0.5, spread)
                p_poor = float(2.0 * (1.0 - norm.cdf(z))) * math.sqrt(lead_d / 3.0)

            # Bound probability smoothly between 2% and 95%
            p_poor = max(0.02, min(0.95, p_poor))

            # Calibrated AI Confidence Score: 0 to 100%
            confidence_score = int(round((1.0 - p_poor) * 100.0))

            # KPR09 Categorical Classification
            if confidence_score >= 65:
                confidence_category = "Higher Confidence"
                risk_status = "Higher Confidence"
                risk_level = "low"
            elif confidence_score >= 45:
                confidence_category = "Moderate Confidence"
                risk_status = "Moderate Confidence"
                risk_level = "moderate"
            else:
                confidence_category = "Lower Confidence"
                risk_status = "Lower Confidence"
                risk_level = "high"

            if rec.get("total_members", 30) < 10:
                confidence_category = "Insufficient Data"
                risk_status = "Insufficient Data"
                risk_level = "insufficient"

            # Professional attribution breakdown
            flag_reasons = []
            if spread_ratio <= 0.80:
                pct = int((1.0 - spread_ratio) * 100)
                flag_reasons.append(
                    f"Strong consensus: Member spread (σ = {spread:.1f}) is {pct}% below location baseline variability (MAE = {hist_mae:.1f})."
                )
            elif spread_ratio >= 1.25:
                pct = int((spread_ratio - 1.0) * 100)
                flag_reasons.append(
                    f"Elevated ensemble spread: Member standard deviation (σ = {spread:.1f}) is {pct}% above normal historical error."
                )

            if lead_d <= 4:
                flag_reasons.append(
                    f"Short-range horizon (Day {lead_d}): NWP atmospheric flow is well-constrained."
                )
            elif lead_d >= 8:
                flag_reasons.append(
                    f"Extended horizon (Day {lead_d}): Natural NWP diffusion boundary introduces atmospheric chaos."
                )

            if exceed_ratio >= 0.30:
                flag_reasons.append(
                    f"Member divergence: {int(exceed_ratio*100)}% of ensemble members differ from the mean by > {self.threshold:.1f}."
                )

            if not flag_reasons:
                flag_reasons.append(
                    f"Ensemble members are clustered smoothly around the mean (80% interval = {interval_80:.1f})."
                )

            explanation = " ".join(flag_reasons)

            scored_records.append({
                **rec,
                "confidence_score": confidence_score,
                "confidence_category": confidence_category,
                "probability_poor_forecast": round(p_poor, 3),
                "risk_status": risk_status,
                "risk_level": risk_level,
                "spread_ratio": round(spread_ratio, 2),
                "explanation": explanation
            })

        return scored_records
