import copy
import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pymannkendall as mk
from app.config import VARIABLES, region_config
from app.main import app
from app.models.schemas import SeriesAnalysisRequest
from app.responses import SafeJSONResponse
from app.routers.point_analysis import analyze_series_endpoint
from app.services import region_analysis, trend_engine


POLYGON = {
    "type": "Polygon",
    "coordinates": [[[29.0, 41.0], [29.2, 41.0], [29.2, 41.2], [29.0, 41.2], [29.0, 41.0]]],
}


class AnalysisSafetyTests(unittest.TestCase):
    def setUp(self):
        with region_analysis._cache_lock:
            region_analysis._cache.clear()

    def test_large_polygon_then_point_analysis_keeps_point_product_and_result(self):
        variables_before = copy.deepcopy(VARIABLES["ndvi"])
        region_before = copy.deepcopy(region_config["ndvi"])
        fake_ee = MagicMock()
        collection = MagicMock()
        fake_ee.ImageCollection.return_value.filterBounds.return_value = collection
        collection.map.return_value = collection
        collection.filterDate.return_value = collection
        collection.select.return_value = collection
        collection.merge.return_value = collection
        fake_ee.FeatureCollection.return_value.getInfo.return_value = {
            "features": [{"properties": {"year": 2001, "value": 0.4}}],
        }

        with patch.object(trend_engine, "ee", fake_ee):
            point_before = trend_engine.analyze_point(39, 32, "ndvi", 2000, 2001)

            def use_large_region_product(_geometry, cfg, _start_year, _end_year):
                cfg.update({
                    "collection": "MODIS/061/MOD13A3",
                    "band": "NDVI",
                    "scale": 1000,
                    "source_used": "MODIS/061/MOD13A3",
                    "scale_used": 1000,
                    "nominal_cell_area_m2": 1_000_000,
                })
                return [{
                    "properties": {
                        "year": 2001,
                        "numerator": 0.4,
                        "denominator": 1,
                        "valid_pixel_count": 1,
                        "area_m2": 200_000_000_000,
                    },
                }]

            with patch.object(
                region_analysis, "_fetch_ee_features", side_effect=use_large_region_product
            ):
                polygon_result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2001)

            point_after = trend_engine.analyze_point(39, 32, "ndvi", 2000, 2001)

        self.assertEqual(polygon_result["source_used"], "MODIS/061/MOD13A3")
        self.assertEqual(point_after, point_before)
        self.assertEqual(VARIABLES["ndvi"], variables_before)
        self.assertEqual(region_config["ndvi"], region_before)
        self.assertEqual(
            [call.args[0] for call in fake_ee.ImageCollection.call_args_list],
            ["MODIS/061/MOD13Q1", "MODIS/061/MOD13Q1"],
        )

    def test_point_analysis_excludes_non_finite_values_and_marks_empty_series(self):
        fake_ee = MagicMock()
        collection = MagicMock()
        fake_ee.ImageCollection.return_value.filterBounds.return_value = collection
        collection.map.return_value = collection
        fake_ee.FeatureCollection.return_value.getInfo.return_value = {
            "features": [
                {"properties": {"year": 2000, "value": float("nan")}},
                {"properties": {"year": 2001, "value": float("inf")}},
                {"properties": {"year": 2002, "value": None}},
            ],
        }

        with patch.object(trend_engine, "ee", fake_ee):
            result = trend_engine.analyze_point(39, 32, "ndvi", 2000, 2002)

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["observation_count"], 0)
        self.assertEqual(result["raw_series"], [])
        self.assertIn("geçerli yıllık gözlem bulunamadı", result["message"])

    def test_analysis_endpoint_serializes_nested_non_finite_values_as_null(self):
        analysis_paths = {
            "/api/analyze-series",
            "/api/analyze-point",
            "/api/analyze-region",
            "/api/analyze-sea-level",
            "/api/sea-level-availability",
            "/api/cascade-correlation",
        }
        # FastAPI's current lazy router inclusion stores these as IncludedRouter
        # nodes rather than flattening APIRoute objects into app.routes.
        self.assertTrue(analysis_paths.issubset(set(app.openapi()["paths"])))
        self.assertIs(app.router.default_response_class, SafeJSONResponse)
        response = SafeJSONResponse(content={
            "status": "insufficient_data",
            "raw_series": [{"value": float("nan")}],
            "details": [float("inf"), float("-inf")],
        })
        payload = json.loads(response.body)
        self.assertIsNone(payload["raw_series"][0]["value"])
        self.assertEqual(payload["details"], [None, None])

    def test_empty_polygon_series_returns_insufficient_data_instead_of_server_error(self):
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[]):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2000)

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["raw_series"], [])
        self.assertIn("No valid source pixels", result["message"])

    def test_24_complete_annual_observations_have_finite_mann_kendall_statistics(self):
        series = [
            (year, 0.1 + (year - 2002) * 0.002056 + (((year * 17) % 11) - 5) * 0.003)
            for year in range(2002, 2026)
        ]
        result = trend_engine.analyze_annual_series(series, 2002, 2025)
        independent = mk.hamed_rao_modification_test(
            [value for _, value in series], lag=None
        )

        self.assertEqual(result["observation_count"], 24)
        self.assertEqual(result["test_status"], "available")
        self.assertEqual(result["test_method"], "hamed_rao_modified_mann_kendall")
        self.assertTrue(math.isfinite(result["z_score"]))
        self.assertTrue(math.isfinite(result["p_value"]))
        self.assertEqual(result["trend"], independent.trend)
        self.assertAlmostEqual(result["z_score"], float(independent.z), places=5)
        self.assertAlmostEqual(result["p_value"], float(independent.p), places=12)

    def test_analysis_series_route_returns_finite_statistics_for_24_complete_years(self):
        request = SeriesAnalysisRequest(
            variable="ndvi",
            unit="NDVI",
            dataset_id="MODIS/061/MOD13Q1",
            start_year=2002,
            end_year=2025,
            series=[
                {
                    "year": year,
                    "value": 0.1 + (year - 2002) * 0.002056 + (((year * 17) % 11) - 5) * 0.003,
                }
                for year in range(2002, 2026)
            ],
        )
        result = analyze_series_endpoint(request)

        self.assertEqual(result["observation_count"], 24)
        self.assertTrue(math.isfinite(result["z_score"]))
        self.assertTrue(math.isfinite(result["p_value"]))
        self.assertEqual(result["test_status"], "available")

    def test_analysis_series_route_withholds_test_when_requested_endpoint_year_is_missing(self):
        request = SeriesAnalysisRequest(
            variable="ndvi",
            unit="NDVI",
            dataset_id="MODIS/061/MOD13Q1",
            start_year=2002,
            end_year=2025,
            series=[
                {"year": year, "value": year * 0.01}
                for year in range(2003, 2026)
            ],
        )
        result = analyze_series_endpoint(request)

        self.assertEqual(result["test_status"], "insufficient_data")
        self.assertIsNone(result["p_value"])
        self.assertIn("requested annual observations are missing", result["message"])

    def test_invalid_hamed_rao_result_falls_back_to_classic_mann_kendall(self):
        series = [(year, year * 0.002 + (year % 3) * 0.001) for year in range(2000, 2024)]
        invalid_result = SimpleNamespace(trend="no trend", z=float("nan"), p=float("nan"))
        classic_result = SimpleNamespace(trend="increasing", z=3.0, p=0.0027)

        with patch.object(
            trend_engine.mk, "hamed_rao_modification_test", return_value=invalid_result
        ), patch.object(
            trend_engine.mk, "original_test", return_value=classic_result
        ) as classic_test:
            result = trend_engine.analyze_annual_series(series, 2000, 2023)

        classic_test.assert_called_once()
        self.assertEqual(result["trend"], "increasing")
        self.assertEqual(result["test_status"], "available")
        self.assertEqual(result["test_method"], "mann_kendall_classic")
        self.assertEqual(result["z_score"], 3.0)
        self.assertEqual(result["p_value"], 0.0027)

    def test_if_both_tests_fail_result_does_not_claim_nonsignificance(self):
        series = [(year, year * 0.002 + (year % 3) * 0.001) for year in range(2000, 2024)]
        invalid_result = SimpleNamespace(trend="no trend", z=float("nan"), p=float("nan"))

        with patch.object(
            trend_engine.mk, "hamed_rao_modification_test", return_value=invalid_result
        ), patch.object(
            trend_engine.mk, "original_test", return_value=invalid_result
        ):
            result = trend_engine.analyze_annual_series(series, 2000, 2023)

        self.assertEqual(result["test_status"], "unavailable")
        self.assertEqual(result["trend"], "statistical_test_unavailable")
        self.assertIsNone(result["z_score"])
        self.assertIsNone(result["p_value"])
        self.assertIsNone(result["significant"])
        self.assertIn("could not be calculated", result["message"])


if __name__ == "__main__":
    unittest.main()
