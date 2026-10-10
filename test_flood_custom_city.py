import unittest
from backend.flood.data.road_network import get_or_create_city_network, REGIONS
from backend.flood.services.evacuation_service import EvacuationService
from backend.flood.models.schemas import EvacuationRequest, FloodSeverity, MLFloodPredictRequest
from backend.flood_predictor import ai_flood_predictor


class TestDynamicFloodCityAndRouting(unittest.TestCase):
    def setUp(self):
        self.service = EvacuationService()

    def test_dynamic_city_network_generation(self):
        """Verify dynamic generation of road network for arbitrary Indian cities."""
        pune_net = get_or_create_city_network("Pune", 18.5204, 73.8567, "Maharashtra")
        self.assertIsNotNone(pune_net)
        self.assertIn("pune", REGIONS)
        self.assertEqual(len(pune_net["nodes"]), 6)
        self.assertGreaterEqual(len(pune_net["roads"]), 12)  # Bidirectional pairs
        self.assertGreaterEqual(len(pune_net["shelters"]), 2)

        # Verify shelters have positive elevation and high capacity
        for s in pune_net["shelters"]:
            self.assertGreater(s.elevation_m, 20.0)
            self.assertGreater(s.capacity, 1000)

    def test_evacuation_routing_never_stranded_under_severe_flooding(self):
        """
        Verify that even under extreme cyclonic downpours (120mm/hr),
        the evacuation service successfully plots an Emergency High-Ground Trajectory
        instead of returning zero routes or crashing.
        """
        # Test on dynamically generated city
        city_net = get_or_create_city_network("Patna", 25.5941, 85.1376, "Bihar")
        origin_node = city_net["nodes"][0]  # Central hub
        safe_shelter = city_net["shelters"][0]

        req = EvacuationRequest(
            origin_name=origin_node.name,
            origin_lat=origin_node.lat,
            origin_lng=origin_node.lng,
            shelter_id=safe_shelter.id,
            flood_severity=FloodSeverity.SEVERE,
            rainfall_mm_hr=120.0,
            rainfall_duration_hours=6.0,
            soil_saturation="saturated",
            ai_confidence_buffer_pct=25.0,
            user_blocked_road_ids=["R_patna_1A", "R_patna_3A"],
            algorithm="dijkstra"
        )

        response = self.service.plan_evacuation(req)
        self.assertTrue(response.success)
        self.assertIsNotNone(response.recommended_route)
        self.assertGreater(response.recommended_route.total_distance_km, 0.0)
        self.assertGreater(response.recommended_route.estimated_time_min, 0.0)

    def test_ml_flood_prediction_when_and_where(self):
        """Verify trained ML model correctly outputs arrival timing, crest, and hotspot depths."""
        self.assertTrue(ai_flood_predictor.is_trained)
        self.assertGreater(ai_flood_predictor.metrics["test_accuracy"], 85.0)

        pune_net = get_or_create_city_network("Pune", 18.5204, 73.8567, "Maharashtra")
        pred = ai_flood_predictor.predict_when_and_where(
            region_id="pune",
            rainfall_forecast_mm=95.0,
            rainfall_intensity_mmh=32.0,
            soil_saturation_state="saturated",
            forecast_lead_day=4,
            nodes=pune_net["nodes"],
            roads=pune_net["roads"]
        )

        # Check WHEN
        when = pred["when_flood_comes"]
        self.assertIn("hours_to_inundation_onset", when)
        self.assertIn("hours_to_peak_crest", when)
        self.assertIn("hydrograph", when)
        self.assertGreater(len(when["hydrograph"]), 5)

        # Check WHERE
        where = pred["where_flood_comes"]
        self.assertIn("submerged_roads_count", where)
        self.assertIn("top_vulnerable_hotspots", where)
        self.assertGreater(len(where["top_vulnerable_hotspots"]), 0)

    def test_city_flood_risk_assessment_and_facilities(self):
        """Verify city risk assessment calculates risk level, preventive measures, and returns medical & food facilities."""
        from backend.flood.services.city_risk_service import assess_city_flood_risk
        assessment = assess_city_flood_risk("Bengaluru", 12.9716, 77.5946, "Karnataka")
        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.city_name, "Bengaluru")
        self.assertIn(assessment.flood_risk_level, ["HIGH RISK", "MODERATE RISK", "LOW RISK / SAFE"])
        self.assertGreater(len(assessment.preventive_measures.immediate_actions), 2)
        self.assertGreater(len(assessment.preventive_measures.emergency_supplies_kit), 4)
        self.assertGreaterEqual(len(assessment.nearby_medical_facilities), 3)
        self.assertGreaterEqual(len(assessment.nearby_food_facilities), 3)
        self.assertGreater(len(assessment.safe_evacuation_route_summary), 20)


if __name__ == "__main__":
    unittest.main()
