import copy
import unittest
from unittest.mock import MagicMock, patch

from app.config import region_config
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
            with self.assertRaisesRegex(ValueError, "No valid source pixels or center-cell"):
                region_analysis.analyze_region(POLYGON, "ndvi", 2000, 2000)

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

    def test_yearly_features_are_fetched_with_one_getinfo_call(self):
        fake_ee = MagicMock()
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

        feature_collection.getInfo.assert_called_once_with()

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


if __name__ == "__main__":
    unittest.main()
