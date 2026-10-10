"""
Automated Unit and Integration Tests for ClimaShield Unified Platform:
- Module 1: AI Weather Forecast Reliability Detector
- Module 2: Flood Evacuation Route Planner
"""

import unittest
import numpy as np
import sys
import os

# Ensure flood subsystem modules are resolvable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "flood")))

from backend.ensemble_processor import EnsembleProcessor
from backend.ml_pipeline import MLConfidencePipeline
from backend.energy_advisor import WindEnergyAdvisor
from backend.open_meteo import OpenMeteoClient

# Flood Evacuation Subsystem
from backend.flood.data.road_network import NODES, BASE_ROAD_SEGMENTS, SHELTERS
from backend.flood.services.evacuation_service import EvacuationService
from backend.flood.models.schemas import EvacuationRequest, FloodSeverity


class TestClimaShieldWeatherPipeline(unittest.TestCase):
    def test_ensemble_processor_statistics(self):
        mock_raw = {
            "daily": {
                "time": ["2026-10-12", "2026-10-13"],
                "wind_speed_10m_max": [15.0, 18.0],
                "wind_speed_10m_max_member01": [14.0, 17.0],
                "wind_speed_10m_max_member02": [16.0, 22.0],
                "wind_speed_10m_max_member03": [15.5, 16.5],
                "wind_speed_10m_max_member04": [14.5, 25.0]
            },
            "daily_units": {
                "wind_speed_10m_max": "km/h"
            }
        }
        res = EnsembleProcessor.process_forecast(
            raw_ensemble=mock_raw,
            variable="wind_speed_10m",
            start_lead_day=0,
            end_lead_day=15,
            error_threshold=3.5
        )
        self.assertEqual(res["unit"], "km/h")
        self.assertGreater(len(res["records"]), 0)
        rec = res["records"][0]
        self.assertIn("ensemble_mean", rec)
        self.assertIn("ensemble_spread", rec)
        self.assertIn("p10", rec)
        self.assertIn("p90", rec)
        self.assertTrue(rec["p10"] <= rec["ensemble_mean"] <= rec["p90"])

    def test_ml_pipeline_chronological_split_and_evaluation(self):
        pipeline = MLConfidencePipeline(variable="wind_speed_10m", user_threshold=3.0)
        dataset = []
        for i in range(40):
            fc = 15.0 + float(i % 5)
            obs = fc + (6.0 if i % 6 == 0 else 1.2)
            dataset.append({
                "date": f"2026-08-{i+1:02d}" if i < 30 else f"2026-09-{i-29:02d}",
                "forecast": fc,
                "observed": obs,
                "abs_error": abs(fc - obs),
                "signed_error": fc - obs,
                "is_poor": 1 if abs(fc - obs) > 3.0 else 0
            })
        eval_res = pipeline.train_and_evaluate(dataset)
        self.assertEqual(eval_res["status"], "success")
        self.assertEqual(eval_res["cases_tested"], 40)
        self.assertEqual(eval_res["train_cases"], 28)
        self.assertEqual(eval_res["test_cases"], 12)
        self.assertIn("brier_score", eval_res["probabilistic"])
        self.assertIn("f1_score", eval_res["classification"])
        self.assertGreaterEqual(eval_res["mae"], 0.0)

    def test_wind_energy_advisor(self):
        mock_scored = [
            {
                "date": "2026-10-15",
                "lead_day": 6,
                "ensemble_mean": 22.0,
                "ensemble_median": 21.5,
                "p10": 12.0,
                "p90": 32.0,
                "ensemble_spread": 6.5,
                "confidence_score": 30,
                "risk_status": "High Risk",
                "explanation": "High ensemble spread (σ = 6.5) at Day 6 lead time."
            }
        ]
        adv = WindEnergyAdvisor.generate_advisory(mock_scored, unit="km/h")
        self.assertEqual(adv["total_days_evaluated"], 1)
        self.assertEqual(adv["low_confidence_count"], 1)
        self.assertTrue(adv["action_required"])
        self.assertIn("methodology_disclaimer", adv)
        self.assertGreater(len(adv["all_days"][0]["recommendations"]), 0)

    def test_disaster_preparedness_advisor(self):
        from backend.disaster_advisor import DisasterPreparednessAdvisor
        mock_forecast = [
            {
                "date": "2026-10-12",
                "lead_day": 3,
                "ensemble_mean": 65.0,
                "p10": 15.0,
                "p90": 110.0,
                "confidence_score": 35.0,
                "confidence_category": "Lower Confidence",
                "risk_status": "High Risk",
                "explanation": "High ensemble spread (σ = 22.5) at Day 3 lead time."
            },
            {
                "date": "2026-10-13",
                "lead_day": 4,
                "ensemble_mean": 55.0,
                "p10": 48.0,
                "p90": 62.0,
                "confidence_score": 82.0,
                "confidence_category": "Higher Confidence",
                "risk_status": "Low Risk",
                "explanation": "High ensemble consensus at Day 4 lead time."
            },
            {
                "date": "2026-10-14",
                "lead_day": 5,
                "ensemble_mean": 8.0,
                "p10": 5.0,
                "p90": 12.0,
                "confidence_score": 90.0,
                "confidence_category": "Higher Confidence",
                "risk_status": "Low Risk",
                "explanation": "Low rainfall consensus."
            }
        ]
        advisory = DisasterPreparednessAdvisor.generate_advisory(mock_forecast, unit="mm")
        self.assertIn("summary", advisory)
        self.assertIn("advisories", advisory)
        self.assertEqual(len(advisory["advisories"]), 3)
        # Day 3 (Heavy rain, Lower confidence) -> Alert Level 2 (Standby)
        self.assertEqual(advisory["advisories"][0]["alert_level"], 2)
        self.assertIn("premature evacuations", advisory["advisories"][0]["key_rationale"].lower())
        # Day 4 (Heavy rain, Higher confidence) -> Alert Level 3 (Pre-Alert)
        self.assertEqual(advisory["advisories"][1]["alert_level"], 3)
        # Day 5 (Light rain) -> Alert Level 0 (Baseline)
        self.assertEqual(advisory["advisories"][2]["alert_level"], 0)

    def test_ml_pipeline_baseline_comparisons(self):
        pipeline = MLConfidencePipeline(variable="precipitation", user_threshold=5.0)
        dataset = []
        for i in range(40):
            fc = 10.0 + float(i % 8)
            obs = fc + (8.0 if i % 5 == 0 else 1.0)
            dataset.append({
                "date": f"2026-08-{i+1:02d}" if i < 30 else f"2026-09-{i-29:02d}",
                "forecast": fc,
                "observed": obs,
                "abs_error": abs(fc - obs),
                "signed_error": fc - obs,
                "is_poor": 1 if abs(fc - obs) > 5.0 else 0
            })
        eval_res = pipeline.train_and_evaluate(dataset)
        self.assertEqual(eval_res["status"], "success")
        self.assertIn("baseline_comparison", eval_res)
        base = eval_res["baseline_comparison"]
        self.assertIn("climatology_baseline_mae", base)
        self.assertIn("persistence_baseline_mae", base)
        self.assertIn("false_alarm_ratio", eval_res["classification"])
        self.assertIn("miss_rate", eval_res["classification"])


class TestClimaShieldFloodPipeline(unittest.TestCase):
    def setUp(self):
        self.service = EvacuationService()

    def test_network_topology_loaded(self):
        self.assertGreater(len(NODES), 10, "Expected at least 10 topological nodes")
        self.assertGreater(len(BASE_ROAD_SEGMENTS), 15, "Expected at least 15 road segments")
        self.assertGreater(len(SHELTERS), 3, "Expected at least 3 emergency shelters")

    def test_safe_route_planning(self):
        req = EvacuationRequest(
            origin_name="T. Nagar (Panagal Park)",
            origin_lat=13.0418,
            origin_lng=80.2341,
            shelter_id="SHELTER_ANNA_UNIV",
            flood_severity=FloodSeverity.MODERATE,
            user_blocked_road_ids=[],
            algorithm="dijkstra"
        )
        plan = self.service.plan_evacuation(req)
        self.assertTrue(plan.success)
        self.assertIsNotNone(plan.recommended_route)
        self.assertGreater(plan.recommended_route.total_distance_km, 0)
        self.assertGreater(plan.recommended_route.estimated_time_min, 0)
        self.assertGreater(len(plan.recommended_route.instructions), 0)
        self.assertIsNotNone(plan.selected_shelter)
        self.assertEqual(plan.selected_shelter.id, "SHELTER_ANNA_UNIV")

    def test_dynamic_rerouting_around_blocked_causeway(self):
        # Baseline plan from Saidapet to St. Thomas Mount
        req_base = EvacuationRequest(
            origin_name="Saidapet Adyar River Causeway",
            origin_lat=13.0210,
            origin_lng=80.2230,
            shelter_id="SHELTER_ST_THOMAS_MOUNT",
            flood_severity=FloodSeverity.LOW,
            user_blocked_road_ids=[],
            algorithm="dijkstra"
        )
        plan_base = self.service.plan_evacuation(req_base)

        # Plan with Saidapet causeway blocked
        req_blocked = EvacuationRequest(
            origin_name="Saidapet Adyar River Causeway",
            origin_lat=13.0210,
            origin_lng=80.2230,
            shelter_id="SHELTER_ST_THOMAS_MOUNT",
            flood_severity=FloodSeverity.LOW,
            user_blocked_road_ids=["R_SAIDAPET_GUINDY"],
            algorithm="dijkstra"
        )
        plan_blocked = self.service.plan_evacuation(req_blocked)

        self.assertTrue(plan_blocked.success)
        self.assertIsNotNone(plan_blocked.recommended_route)
        # Rerouted path must be different from direct causeway crossing
        self.assertNotEqual(
            plan_base.recommended_route.total_distance_km,
            plan_blocked.recommended_route.total_distance_km
        )
        # Avoided roads should list the blocked segment
        avoided_names = [r.road_name for r in (plan_blocked.why_this_route.avoided_roads if plan_blocked.why_this_route else [])]
        self.assertTrue(any("Saidapet" in name for name in avoided_names))

    def test_auto_shelter_optimization(self):
        req_auto = EvacuationRequest(
            origin_name="Velachery Vijayanagar Junction",
            origin_lat=12.9780,
            origin_lng=80.2210,
            shelter_id="auto",
            flood_severity=FloodSeverity.MODERATE,
            user_blocked_road_ids=[],
            algorithm="dijkstra"
        )
        plan_auto = self.service.plan_evacuation(req_auto)
        self.assertTrue(plan_auto.success)
        self.assertIsNotNone(plan_auto.selected_shelter)
        self.assertGreater(len(plan_auto.candidate_shelters_ranked), 0)

    def test_pan_india_regions_routing(self):
        from backend.flood.data.road_network import REGIONS
        self.assertGreaterEqual(len(REGIONS), 7)
        # Test routing in Mumbai, Delhi, Kerala, Assam, Kolkata, Gujarat
        for reg_id in ["mumbai", "delhi", "kerala", "assam", "kolkata", "gujarat"]:
            reg = REGIONS[reg_id]
            orig_node = next(n for n in reg["nodes"] if n.id == reg["default_origin_id"])
            req = EvacuationRequest(
                origin_name=orig_node.name,
                origin_lat=orig_node.lat,
                origin_lng=orig_node.lng,
                shelter_id=reg["default_shelter_id"],
                flood_severity=FloodSeverity.MODERATE
            )
            plan = self.service.plan_evacuation(req)
            self.assertTrue(plan.success, f"Failed evacuation plan for region: {reg_id}")
            self.assertIsNotNone(plan.recommended_route)
            self.assertGreater(plan.recommended_route.total_distance_km, 0)

    def test_open_meteo_client_resilient_failover(self):
        client = OpenMeteoClient()
        # Even if DNS is offline or restricted, get_live_ensemble must return valid structure
        ens = client.get_live_ensemble(8.26, 77.53, "wind_speed_10m", forecast_days=10)
        self.assertIn("daily", ens)
        self.assertIn("time", ens["daily"])
        self.assertGreaterEqual(len(ens["daily"]["time"]), 8)

        # Historical verification must return paired dates
        hist = client.get_historical_verification_data(8.26, 77.53, "wind_speed_10m", days_back=90)
        self.assertIn("forecast_daily", hist)
        self.assertIn("observed_daily", hist)
        self.assertEqual(len(hist["forecast_daily"]["time"]), len(hist["observed_daily"]["time"]))

    def test_ai_flood_predictor_when_and_where(self):
        from backend.flood_predictor import ai_flood_predictor
        from backend.flood.data.road_network import REGIONS
        self.assertTrue(ai_flood_predictor.is_trained)
        self.assertGreater(ai_flood_predictor.metrics["test_accuracy"], 80.0)
        self.assertGreater(ai_flood_predictor.metrics["roc_auc"], 0.85)

        chennai = REGIONS["chennai"]
        pred = ai_flood_predictor.predict_when_and_where(
            region_id="chennai",
            rainfall_forecast_mm=100.0,
            rainfall_intensity_mmh=30.0,
            soil_saturation_state="saturated",
            forecast_lead_day=4,
            nodes=chennai["nodes"],
            roads=chennai["roads"]
        )

        self.assertEqual(pred["status"], "success")
        # Check 'WHEN' outputs
        when = pred["when_flood_comes"]
        self.assertIn("hours_to_inundation_onset", when)
        self.assertIn("hours_to_peak_crest", when)
        self.assertIn("timing_verdict", when)
        self.assertGreater(when["peak_discharge_m3s"], 0)
        self.assertGreater(len(when["hydrograph"]), 5)

        # Check 'WHERE' outputs
        where = pred["where_flood_comes"]
        self.assertGreater(where["total_nodes_analyzed"], 5)
        self.assertGreater(where["submerged_roads_count"], 0)
        self.assertIn("spatial_verdict", where)
        self.assertGreater(len(where["top_vulnerable_hotspots"]), 0)

    def test_ml_evacuation_routing(self):
        from backend.flood.api.router import plan_ml_flood_evacuation, MLFloodPredictRequest
        req = MLFloodPredictRequest(
            region="chennai",
            rainfall_forecast_mm=55.0,
            rainfall_intensity_mmh=18.0,
            soil_saturation_state="saturated"
        )
        res = plan_ml_flood_evacuation(req)
        self.assertIn("prediction", res)
        self.assertIn("evacuation_plan", res)
        self.assertTrue(res["evacuation_plan"].success)
        self.assertIsNotNone(res["evacuation_plan"].recommended_route)


if __name__ == "__main__":
    unittest.main()

