import copy
import unittest
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config import VARIABLES, region_config
from app.services import region_analysis

SUBSAMPLE_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "diagnose_subsample.py"
_spec = importlib.util.spec_from_file_location("diagnose_subsample", SUBSAMPLE_SCRIPT)
diagnose_subsample = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diagnose_subsample)


POLYGON = {
    "type": "Polygon",
    "coordinates": [[[29.0, 41.0], [29.2, 41.0], [29.2, 41.2], [29.0, 41.2], [29.0, 41.0]]],
}


def feature(year, numerator, denominator, center_value=None, pixels=4, area=1_000_000_000):
    return {"properties": {
        "year": year,
        "numerator": numerator,
        "denominator": denominator,
        "center_value": center_value,
        "valid_pixel_count": pixels,
        "area_m2": area,
    }}


class RegionAnalysisTests(unittest.TestCase):
    def setUp(self):
        with region_analysis._cache_lock:
            region_analysis._cache.clear()

    def test_geometry_collection_is_reduced_to_polygon_members(self):
        second = {
            "type": "Polygon",
            "coordinates": [[[30, 41], [30.2, 41], [30.2, 41.2], [30, 41.2], [30, 41]]],
        }
        collection = {
            "type": "GeometryCollection",
            "geometries": [
                POLYGON,
                {"type": "Point", "coordinates": [99, 99]},
                {"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                {"type": "MultiPolygon", "coordinates": [second["coordinates"]]},
            ],
        }
        normalized = region_analysis._normalize_geometry(collection)
        self.assertEqual(normalized["type"], "MultiPolygon")
        self.assertEqual(normalized["coordinates"], [POLYGON["coordinates"], second["coordinates"]])

    def test_single_polygon_geometry_collection_remains_polygon(self):
        collection = {
            "type": "GeometryCollection",
            "geometries": [POLYGON, {"type": "Point", "coordinates": [0, 0]}],
        }
        self.assertEqual(region_analysis._normalize_geometry(collection), POLYGON)

    def test_weighted_mean_matches_manual_numerator_over_denominator(self):
        # Two valid pixels: (10 × 1 m² + 20 × 3 m²) / 4 m² = 17.5.
        row = feature(2001, numerator=70, denominator=4, pixels=2)
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[row]):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2001)
        self.assertEqual(result["raw_series"][0]["value"], 17.5)
        self.assertEqual(result["method"], "polygon_area_weighted")
        self.assertEqual(result["partial_year_excluded"], [2000])

    def test_analyze_region_normalizes_geometry_collection_before_fetch(self):
        collection = {"type": "GeometryCollection", "geometries": [POLYGON]}
        row = feature(2001, 1, 1)
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[row]) as fetch:
            result = region_analysis.analyze_region(collection, "ndvi", 2000, 2001)
        self.assertEqual(fetch.call_args.args[0], POLYGON)
        self.assertEqual(result["raw_series"][0]["year"], 2001)

    def test_monthly_server_batch_annualizes_complete_months(self):
        months = [{"properties": {
            "year": 2020, "month": month, "numerator": month * 2,
            "denominator": 2, "valid_pixel_count": 9,
        }} for month in range(1, 13)]
        annual, missing = region_analysis._annualize_month_features(
            months, region_analysis.region_config["merra2_t2m"], 2020, 2020,
        )
        self.assertEqual(missing, [])
        self.assertEqual(annual[0]["properties"]["numerator"], 6.5)
        self.assertEqual(annual[0]["properties"]["valid_pixel_count"], 9)

    def test_monthly_server_batch_missing_month_excludes_annual_observation(self):
        months = [{"properties": {
            "year": 2020, "month": month, "numerator": 10,
            "denominator": 1, "valid_pixel_count": 9,
        }} for month in range(1, 13) if month != 7]
        annual, missing = region_analysis._annualize_month_features(
            months, region_analysis.region_config["merra2_t2m"], 2020, 2020,
        )
        self.assertEqual(missing, ["2020-07"])
        self.assertIsNone(annual[0]["properties"]["numerator"])

    def test_one_year_server_month_batch_wraps_flattened_features_correctly(self):
        fake_ee = MagicMock()
        fake_ee.Geometry.return_value.area.return_value.getInfo.return_value = 10_000_000_000
        fake_ee.FeatureCollection.return_value.getInfo.return_value = {"features": []}
        fake_ee.List.return_value.flatten.return_value.flatten.return_value = "flat-features"
        with patch.object(region_analysis, "ee", fake_ee):
            rows = region_analysis._fetch_server_month_features(
                POLYGON, copy.deepcopy(region_config["merra2_t2m"]), 2020, 2020, 1,
            )
        self.assertEqual(rows, [])
        self.assertEqual(fake_ee.FeatureCollection.call_args.args[0], "flat-features")
        self.assertEqual(fake_ee.FeatureCollection.return_value.getInfo.call_count, 1)
        fake_ee.FeatureCollection.return_value.flatten.assert_not_called()
        self.assertEqual(fake_ee.Geometry.return_value.area.return_value.getInfo.call_count, 1)

    def test_monthly_server_batch_path_is_explicit_and_preserves_annual_path(self):
        monthly_rows = [{"properties": {
            "year": 2020, "month": month, "numerator": 7,
            "denominator": 1, "valid_pixel_count": 12,
        }} for month in range(1, 13)]
        with patch.object(region_analysis, "_fetch_server_month_features", return_value=monthly_rows) as fetch:
            result = region_analysis.analyze_region(
                POLYGON, "merra2_t2m", 2020, 2020,
                aggregation_mode="monthly_server_batch", batch_years=5,
            )
        self.assertEqual(fetch.call_args.args[2:], (2020, 2020, 5))
        self.assertEqual(result["aggregation_mode"], "monthly_server_batch")
        self.assertEqual(result["raw_series"][0]["value"], 7)
        with self.assertRaisesRegex(ValueError, "supported only"):
            region_analysis.analyze_region(POLYGON, "ndvi", 2020, 2020, aggregation_mode="monthly_server_batch")

    def test_smap_subsampling_selects_existing_timestamps_per_day(self):
        def millis(day, hour, minute=30):
            return int(datetime(2024, 7, day, hour, minute, tzinfo=timezone.utc).timestamp() * 1000)
        available = [millis(1, hour) for hour in (2, 5, 11, 14, 20)]
        twice = diagnose_subsample.select_available_timestamps(available, (0, 12))
        once = diagnose_subsample.select_available_timestamps(available, (0,))
        self.assertEqual(twice, [millis(1, 2), millis(1, 11)])
        self.assertEqual(once, [millis(1, 2)])
        self.assertTrue(set(twice).issubset(set(available)))

    def test_smap_subsampling_reports_empty_timestamp_query_clearly(self):
        fake_ee = MagicMock()
        collection = MagicMock()
        fake_ee.ImageCollection.return_value.filterDate.return_value.select.return_value = collection
        collection.aggregate_array.return_value.getInfo.return_value = []
        with patch.object(diagnose_subsample, "ee", fake_ee):
            with self.assertRaisesRegex(ValueError, "No SMAP images exist for 2024-07"):
                diagnose_subsample.variant_collection("soil_moisture", 2024, 7, "smap_1_per_day")

    def test_empty_polygon_years_fall_back_to_center_cell_or_return_clear_error(self):
        empty = feature(2001, numerator=None, denominator=0, center_value=None, pixels=0)
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[empty]):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2001, 2001)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["raw_series"], [])
        self.assertIn("No valid source pixels", result["message"])

        # Even a non-empty but sub-pixel denominator uses the requested center cell.
        center_cell = feature(2001, numerator=99, denominator=1, center_value=0.42, pixels=1, area=100)
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[center_cell]):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2001, 2001)
        self.assertEqual(result["method"], "polygon_area_weighted_single_cell")
        self.assertEqual(result["raw_series"][0]["value"], 0.42)
        self.assertIn("resolution_warning", result)

    def test_low_pixel_coverage_and_short_series_warnings_are_returned(self):
        rows = [feature(year, year / 10, 1, pixels=1) for year in range(2001, 2008)]
        with patch.object(region_analysis, "_fetch_ee_features", return_value=rows):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2001, 2007)
        self.assertEqual(result["low_coverage_years"], list(range(2001, 2008)))
        self.assertIn("short_series_warning", result)

    def test_missing_requested_year_withholds_mann_kendall_significance(self):
        rows = [feature(year, year * 2, 1) for year in range(2001, 2018) if year != 2006]
        with patch.object(region_analysis, "_fetch_ee_features", return_value=rows), \
             patch("app.services.trend_engine.mk.hamed_rao_modification_test") as mann_kendall:
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2001, 2017)
        self.assertEqual(result["missing_years"], [2006])
        self.assertIsNone(result["p_value"])
        self.assertFalse(result["significant"])
        self.assertTrue(result["significance_withheld"])
        self.assertIn("missing_year_warning", result)
        mann_kendall.assert_not_called()

    def test_scale_targets_about_one_million_pixels_without_going_below_native(self):
        self.assertEqual(region_analysis._scale_for_region(1_000_000_000_000, 250), 1000)
        self.assertEqual(region_analysis._scale_for_region(100_000, 250), 250)

    def test_adaptive_output_scale_does_not_trigger_single_cell_fallback(self):
        cfg = copy.deepcopy(region_config["ndvi"])
        cfg.update({
            "scale": 1000,
            "scale_used": 1000,
            "native_scale_meters": 250,
            "nominal_cell_area_m2": 62_500,
            "source_used": "MODIS/061/MOD13Q1",
        })
        row = feature(2000, numerator=70, denominator=4, center_value=99, pixels=2, area=100_000)

        result = region_analysis._build_result(
            [row], POLYGON, "ndvi", cfg, 2000, 2000, 0.1
        )

        self.assertEqual(result["method"], "polygon_area_weighted")
        self.assertEqual(result["raw_series"][0]["value"], 17.5)

    def test_large_ndvi_polygon_uses_monthly_one_kilometer_product(self):
        fake_ee = MagicMock()
        fake_ee.Geometry.return_value.area.return_value.getInfo.return_value = 200_000_000_000
        collection = MagicMock()
        fake_ee.ImageCollection.return_value.filterBounds.return_value = collection
        collection.map.return_value = collection
        collection.select.return_value = collection
        feature_collection = MagicMock()
        feature_collection.getInfo.return_value = {"features": []}
        fake_ee.FeatureCollection.return_value = feature_collection
        fake_ee.List.sequence.return_value.map.return_value = object()
        cfg = copy.deepcopy(region_config["ndvi"])

        with patch.object(region_analysis, "ee", fake_ee):
            region_analysis._fetch_ee_features(POLYGON, cfg, 2002, 2002)

        self.assertEqual(cfg["collection"], "MODIS/061/MOD13A3")
        self.assertEqual(cfg["band"], "NDVI")
        self.assertEqual(cfg["scale_used"], 1000)
        self.assertEqual(cfg["source_used"], "MODIS/061/MOD13A3")
        fake_ee.ImageCollection.assert_called_once_with("MODIS/061/MOD13A3")

    def test_region_products_declare_equal_area_behavior(self):
        self.assertTrue(region_config["ndvi"]["equal_area"])
        self.assertTrue(VARIABLES["temperature"]["equal_area"])
        for variable in (
            "merra2_t2m",
            "merra2_evaporation",
            "gldas_root_moisture",
            "gldas_surface_runoff",
            "soil_moisture",
        ):
            with self.subTest(variable=variable):
                self.assertFalse(region_config[variable]["equal_area"])

    def test_polygon_reductions_are_fetched_in_bounded_sequential_batches(self):
        fake_ee = MagicMock()
        fake_ee.Geometry.return_value.area.return_value.getInfo.return_value = 1_000_000_000
        collection = MagicMock()
        fake_ee.ImageCollection.return_value.filterBounds.return_value = collection
        collection.map.return_value = collection
        collection.select.return_value = collection
        feature_collection = MagicMock()
        feature_collection.getInfo.return_value = {"features": []}
        fake_ee.FeatureCollection.return_value = feature_collection
        fake_ee.List.sequence.return_value.map.return_value = object()

        with patch.object(region_analysis, "ee", fake_ee):
            region_analysis._fetch_ee_features(POLYGON, region_config["ndvi"], 2000, 2020)

        self.assertEqual(
            feature_collection.getInfo.call_count,
            5,
            "21 years should be split into sequential batches of at most five years",
        )

    def test_memory_limited_products_fetch_one_year_per_sequential_request(self):
        for variable in sorted(region_analysis.MEMORY_LIMITED_REGION_VARIABLES):
            with self.subTest(variable=variable):
                fake_ee = MagicMock()
                fake_ee.Geometry.return_value.area.return_value.getInfo.return_value = 1_000_000_000_000
                collection = MagicMock()
                fake_ee.ImageCollection.return_value.filterBounds.return_value = collection
                collection.map.return_value = collection
                collection.select.return_value = collection
                feature_collection = MagicMock()
                feature_collection.getInfo.return_value = {"features": []}
                fake_ee.FeatureCollection.return_value = feature_collection
                fake_ee.List.sequence.return_value.map.return_value = object()
                cfg = copy.deepcopy(region_config[variable])

                with patch.object(region_analysis, "ee", fake_ee):
                    region_analysis._fetch_ee_features(POLYGON, cfg, 2018, 2020)

                self.assertEqual(feature_collection.getInfo.call_count, 3)

    def test_concurrent_aggregation_error_retries_batch_one_year_at_a_time(self):
        fake_ee = MagicMock()
        fake_ee.Geometry.return_value.area.return_value.getInfo.return_value = 1_000_000_000
        collection = MagicMock()
        fake_ee.ImageCollection.return_value.filterBounds.return_value = collection
        collection.map.return_value = collection
        collection.select.return_value = collection
        feature_collection = MagicMock()
        feature_collection.getInfo.side_effect = [
            region_analysis.EEException("Too many concurrent aggregations."),
            {"features": [{"properties": {"year": 2000, "numerator": 1, "denominator": 1}}]},
            {"features": [{"properties": {"year": 2001, "numerator": 1, "denominator": 1}}]},
        ]
        fake_ee.FeatureCollection.return_value = feature_collection
        fake_ee.List.sequence.return_value.map.return_value = object()

        with patch.object(region_analysis, "ee", fake_ee):
            rows = region_analysis._fetch_ee_features(
                POLYGON, region_config["ndvi"], 2000, 2001
            )

        self.assertEqual([row["properties"]["year"] for row in rows], [2000, 2001])
        self.assertEqual(feature_collection.getInfo.call_count, 3)

    def test_identical_region_request_uses_cache(self):
        rows = [feature(2001, 50, 2, pixels=2)]
        with patch.object(region_analysis, "_fetch_ee_features", return_value=rows) as fetch:
            first = region_analysis.analyze_region(POLYGON, "ndvi", 2001, 2001)
            second = region_analysis.analyze_region(copy.deepcopy(POLYGON), "ndvi", 2001, 2001)
        fetch.assert_called_once()
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])

    def test_runoff_unit_is_reported_as_annual_total(self):
        self.assertEqual(region_config["gldas_surface_runoff"]["aggregate"], "sum")
        self.assertIn("annual total", region_config["gldas_surface_runoff"]["unit"])

    def test_high_frequency_products_use_monthly_first_aggregation(self):
        for variable in (
            "soil_moisture",
            "merra2_t2m",
            "merra2_evaporation",
            "gldas_root_moisture",
            "gldas_surface_runoff",
        ):
            with self.subTest(variable=variable):
                self.assertTrue(region_config[variable]["monthly_first"])

    def test_soil_moisture_sampled_region_mode_is_explicitly_disabled(self):
        points = [
            {"lat": 41.0, "lon": 29.0, "weight": 1},
            {"lat": 41.1, "lon": 29.1, "weight": 3},
        ]
        with self.assertRaisesRegex(ValueError, "SMAP soil moisture sampled region mode is disabled"):
            region_analysis.analyze_sampled_soil_moisture(POLYGON, points, 2018, 2018)

    def test_quick_sample_retry_sizes_descend_without_parallel_fanout(self):
        self.assertEqual(region_analysis._quick_point_attempt_sizes(16), [16, 8, 4])
        self.assertEqual(region_analysis._quick_point_attempt_sizes(12), [12, 8, 4])
        self.assertEqual(region_analysis._quick_point_attempt_sizes(8), [8, 4])
        self.assertEqual(region_analysis._quick_point_attempt_sizes(6), [6, 4])
        self.assertEqual(region_analysis._quick_point_attempt_sizes(3), [3])

    def test_soil_moisture_quick_path_is_rejected_before_fetching_any_samples(self):
        points = [{"lat": 41 + index / 10, "lon": 29 + index / 10, "weight": 1} for index in range(8)]
        with patch.object(region_analysis, "_fetch_smap_sample_features") as fetch:
            with self.assertRaisesRegex(ValueError, "SMAP soil moisture sampled region mode is disabled"):
                region_analysis.analyze_sampled_soil_moisture(POLYGON, points, 2018, 2019)
        fetch.assert_not_called()

    def test_soil_moisture_sampled_region_mode_reports_clear_memory_limit_reason(self):
        points = [{"lat": 41, "lon": 29, "weight": 1}]
        with self.assertRaisesRegex(ValueError, "Google Earth Engine exceeds the user memory limit"):
            region_analysis.analyze_sampled_soil_moisture(POLYGON, points, 2018, 2018)

    def test_soil_moisture_sampled_region_mode_uses_no_boundary_sample_fetch(self):
        points = [
            {"lat": 30 + index / 10, "lon": 20 + index / 10, "weight": 1}
            for index in range(16)
        ]
        with patch.object(region_analysis, "_fetch_smap_sample_features") as fetch:
            with self.assertRaisesRegex(ValueError, "sampled region mode is disabled"):
                region_analysis.analyze_sampled_soil_moisture(POLYGON, points, 2018, 2018)
        fetch.assert_not_called()

    def test_smap_quick_mode_uses_one_getinfo_for_monthly_composites(self):
        fake_ee = MagicMock()
        image_collection = MagicMock()
        image_collection.filterBounds.return_value = image_collection
        image_collection.map.return_value = image_collection
        image_collection.select.return_value = image_collection
        feature_collection = MagicMock()
        feature_collection.geometry.return_value = MagicMock()
        feature_collection.flatten.return_value = feature_collection
        feature_collection.getInfo.return_value = {"features": []}
        fake_ee.FeatureCollection.return_value = feature_collection
        fake_ee.ImageCollection.return_value = image_collection
        fake_ee.List.sequence.return_value.map.return_value = object()

        points = [{"lat": 41, "lon": 29, "weight": 1}]
        with patch.object(region_analysis, "ee", fake_ee):
            region_analysis._fetch_smap_sample_features(
                points, region_config["soil_moisture"], 2015, 2025
            )
        self.assertEqual(feature_collection.getInfo.call_count, 1)

    def test_smap_quick_memory_error_retries_with_fewer_points_and_continues_years(self):
        fake_ee = MagicMock()
        collection = MagicMock()
        collection.filterBounds.return_value = collection
        collection.filterDate.return_value = collection
        collection.map.return_value = collection
        collection.select.return_value = collection
        collection.size.return_value.getInfo.return_value = 100
        collection.first.return_value.select.return_value.projection.return_value = "projection"
        image = MagicMock()
        image.rename.return_value = image
        image.updateMask.return_value = image
        image.setDefaultProjection.return_value = image
        fake_ee.Image.constant.return_value = image
        monthly = MagicMock()
        monthly.reduce.return_value.rename.return_value = image
        fake_ee.ImageCollection.fromImages.return_value.mean.return_value.multiply.return_value.add.return_value = image
        image.sampleRegions.return_value.map.return_value = "rows"
        feature_collection = MagicMock()
        feature_collection.geometry.return_value.buffer.return_value = "buffer"
        feature_collection.flatten.return_value = feature_collection
        feature_collection.getInfo.side_effect = [
            RuntimeError("User memory limit exceeded"),
            {"features": []},
            {"features": []},
        ]
        fake_ee.FeatureCollection.return_value = feature_collection
        fake_ee.ImageCollection.return_value = collection
        fake_ee.List.sequence.return_value.map.return_value = "mapped"
        points = [{"lat": 41 + index / 10, "lon": 29 + index / 10, "weight": 1} for index in range(16)]

        with patch.object(region_analysis, "ee", fake_ee):
            features, failed, used_by_year, image_count, request_count = region_analysis._fetch_smap_sample_features(
                points, region_config["soil_moisture"], 2018, 2019,
            )

        self.assertEqual(features, [])
        self.assertEqual(failed, [])
        self.assertEqual(used_by_year, {2018: 8, 2019: 8})
        self.assertIsNone(image_count)
        self.assertEqual(request_count, 2)
        self.assertEqual(feature_collection.getInfo.call_count, 2)


if __name__ == "__main__":
    unittest.main()
