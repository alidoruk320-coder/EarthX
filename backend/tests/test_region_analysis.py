import copy
import unittest
from unittest.mock import MagicMock, patch

from app.config import VARIABLES, region_config
from app.services import region_analysis


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

    def test_weighted_mean_matches_manual_numerator_over_denominator(self):
        # Two valid pixels: (10 × 1 m² + 20 × 3 m²) / 4 m² = 17.5.
        row = feature(2000, numerator=70, denominator=4, pixels=2)
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[row]):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2000)
        self.assertEqual(result["raw_series"][0]["value"], 17.5)
        self.assertEqual(result["method"], "polygon_area_weighted")

    def test_empty_polygon_years_fall_back_to_center_cell_or_return_clear_error(self):
        empty = feature(2000, numerator=None, denominator=0, center_value=None, pixels=0)
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[empty]):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2000)
        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["raw_series"], [])
        self.assertIn("No valid source pixels", result["message"])

        # Even a non-empty but sub-pixel denominator uses the requested center cell.
        center_cell = feature(2000, numerator=99, denominator=1, center_value=0.42, pixels=1, area=100)
        with patch.object(region_analysis, "_fetch_ee_features", return_value=[center_cell]):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2000)
        self.assertEqual(result["method"], "polygon_area_weighted_single_cell")
        self.assertEqual(result["raw_series"][0]["value"], 0.42)
        self.assertIn("resolution_warning", result)

    def test_low_pixel_coverage_and_short_series_warnings_are_returned(self):
        rows = [feature(year, year / 10, 1, pixels=1) for year in range(2000, 2007)]
        with patch.object(region_analysis, "_fetch_ee_features", return_value=rows):
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2006)
        self.assertEqual(result["low_coverage_years"], list(range(2000, 2007)))
        self.assertIn("short_series_warning", result)

    def test_missing_requested_year_withholds_mann_kendall_significance(self):
        rows = [feature(year, year * 2, 1) for year in range(2000, 2017) if year != 2005]
        with patch.object(region_analysis, "_fetch_ee_features", return_value=rows), \
             patch("app.services.trend_engine.mk.hamed_rao_modification_test") as mann_kendall:
            result = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2016)
        self.assertEqual(result["missing_years"], [2005])
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
            "merra2_precipitable_water",
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
        rows = [feature(2000, 50, 2, pixels=2)]
        with patch.object(region_analysis, "_fetch_ee_features", return_value=rows) as fetch:
            first = region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2000)
            second = region_analysis.analyze_region(copy.deepcopy(POLYGON), "ndvi", 2000, 2000)
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
            "merra2_precipitable_water",
            "merra2_evaporation",
            "gldas_root_moisture",
            "gldas_surface_runoff",
        ):
            with self.subTest(variable=variable):
                self.assertTrue(region_config[variable]["monthly_first"])

    def test_smap_quick_mode_weights_samples_and_marks_its_method(self):
        rows = [
            {"properties": {"year": 2018, "value": 0.2, "area_weight": 1}},
            {"properties": {"year": 2018, "value": 0.4, "area_weight": 3}},
        ]
        points = [
            {"lat": 41.0, "lon": 29.0, "weight": 1},
            {"lat": 41.1, "lon": 29.1, "weight": 3},
        ]
        with patch.object(region_analysis, "_fetch_smap_sample_features", return_value=rows):
            result = region_analysis.analyze_sampled_soil_moisture(
                POLYGON, points, 2018, 2018
            )
        self.assertEqual(result["method"], "sampled_boundary_filtered")
        self.assertAlmostEqual(result["raw_series"][0]["value"], 0.35)
        self.assertEqual(result["sample_count"], 2)

    def test_smap_quick_mode_uses_all_sixteen_supplied_boundary_points(self):
        points = [
            {"lat": 30 + index / 10, "lon": 20 + index / 10, "weight": 1}
            for index in range(16)
        ]
        rows = [
            {"properties": {
                "year": 2018,
                "value": 0.2 + index / 100,
                "area_weight": 1,
                "sample_id": index,
            }}
            for index in range(16)
        ]
        with patch.object(region_analysis, "_fetch_smap_sample_features", return_value=rows):
            result = region_analysis.analyze_sampled_soil_moisture(
                POLYGON, points, 2018, 2018
            )
        self.assertEqual(result["sample_count"], 16)

    def test_smap_quick_mode_bounds_each_year_to_one_getinfo(self):
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
        self.assertEqual(feature_collection.getInfo.call_count, 11)


if __name__ == "__main__":
    unittest.main()
