import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.models.schemas import SwotLakeAnalysisRequest
from app.routers.swot import analyze_swot_lake_endpoint
from app.services.swot_lakes import (
    SwotCacheUnavailableError,
    analyze_swot_lake,
    parse_hydrocron_csv,
)


class SwotLakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temporary_directory.name) / "swot.json"
        self.cache_path.write_text(json.dumps({
            "updated_at": "2026-11-12T12:00:00Z",
            "lakes": {
                "large_aral": {
                    "lake_id": "4610055052",
                    "observations": [
                        {
                            "date": "2023-04-01T20:21:07Z",
                            "wse": 31.25,
                            "quality_f": "1",
                            "area_total_km2": 5200.0,
                        },
                        {
                            "date": "2024-05-01T20:21:07Z",
                            "wse": 31.5,
                            "quality_f": "2",
                            "area_total_km2": 5100.0,
                        },
                    ],
                },
                "lake_chad": {
                    "lake_id": "1620031382",
                    "observations": [
                        {
                            "date": "2024-06-01T10:00:00Z",
                            "wse": 280.0,
                            "quality_f": "1",
                        },
                    ],
                },
            },
        }), encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_parser_discards_no_data_fill_and_other_lake_rows_but_preserves_flags(self):
        content = (
            "lake_id,time_str,wse,wse_u,wse_std,area_total,area_detct,quality_f,ice_clim_f,ice_dyn_f,lake_name\n"
            "4610055052,2023-04-01T20:21:07Z,31.25,0.2,0.3,5200,5000,1,0,0,LARGE ARAL SEA\n"
            "4610055052,no_data,-999999999999.0,,,,,,,,\n"
            "4610055052,2023-04-02T20:21:07Z,-999999999999.0,,,,,,,,\n"
            "1620031382,2023-04-03T20:21:07Z,280,,,,,1,0,0,CHAD\n"
        )

        observations = parse_hydrocron_csv(content, "4610055052")

        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0]["wse"], 31.25)
        self.assertEqual(observations[0]["quality_f"], "1")
        self.assertEqual(observations[0]["area_total_km2"], 5200.0)

    def test_analysis_returns_descriptive_sen_slope_without_significance_statistics(self):
        result = analyze_swot_lake(45.2, 59.6, 2023, 2024, self.cache_path)

        self.assertEqual(result["lake_name"], "Large Aral Sea")
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(result["raw_series"][0]["date"], "2023-04-01T20:21:07Z")
        self.assertEqual(result["stats"]["trend"], "descriptive_increasing")
        self.assertAlmostEqual(result["stats"]["sen_slope"], 0.25 / (396 / 365.2425), places=6)
        self.assertIsNotNone(result["stats"]["trendline_start_value"])
        self.assertIsNotNone(result["stats"]["trendline_end_value"])
        self.assertEqual(result["stats"]["test_status"], "not_applicable")
        self.assertIsNone(result["stats"]["z_score"])
        self.assertIsNone(result["stats"]["p_value"])
        self.assertIsNone(result["stats"]["significant"])

    def test_analysis_filters_requested_observation_years(self):
        result = analyze_swot_lake(45.2, 59.6, 2024, 2024, self.cache_path)

        self.assertEqual(result["observation_count"], 1)
        self.assertEqual(result["raw_series"][0]["value"], 31.5)
        self.assertIsNone(result["stats"]["sen_slope"])
        self.assertEqual(result["stats"]["trend"], "descriptive_insufficient_data")

    def test_analysis_rejects_coordinates_outside_supported_lake_areas(self):
        with self.assertRaisesRegex(ValueError, "only near the Large Aral Sea and Lake Chad"):
            analyze_swot_lake(0, 0, 2023, 2024, self.cache_path)

    def test_analysis_reports_missing_cache_as_unavailable(self):
        with self.assertRaises(SwotCacheUnavailableError):
            analyze_swot_lake(45.2, 59.6, 2023, 2024, Path(self.temporary_directory.name) / "missing.json")

    def test_endpoint_maps_cache_errors_to_service_unavailable(self):
        request = SwotLakeAnalysisRequest(lat=45.2, lon=59.6, start_year=2023, end_year=2024)
        with patch(
            "app.routers.swot.analyze_swot_lake",
            side_effect=SwotCacheUnavailableError("cache is unavailable"),
        ), self.assertRaises(HTTPException) as raised:
            analyze_swot_lake_endpoint(request)

        self.assertEqual(raised.exception.status_code, 503)

    def test_endpoint_returns_scoped_cached_data(self):
        request = SwotLakeAnalysisRequest(lat=45.2, lon=59.6, start_year=2023, end_year=2024)

        expected = {"status": "ok", "lake_name": "Large Aral Sea"}
        with patch("app.routers.swot.analyze_swot_lake", return_value=expected) as analyze:
            result = analyze_swot_lake_endpoint(request)

        self.assertEqual(result, expected)
        analyze.assert_called_once_with(45.2, 59.6, 2023, 2024)

    def test_request_schema_rejects_years_before_swot_observations(self):
        with self.assertRaises(ValueError):
            SwotLakeAnalysisRequest(lat=45, lon=59, start_year=2022, end_year=2024)

    def test_endpoint_maps_unsupported_coordinates_to_unprocessable_entity(self):
        request = SwotLakeAnalysisRequest(lat=0, lon=0, start_year=2023, end_year=2024)
        with self.assertRaises(HTTPException) as raised:
            analyze_swot_lake_endpoint(request)

        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
