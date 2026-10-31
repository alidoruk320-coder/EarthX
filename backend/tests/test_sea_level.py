import unittest
from unittest.mock import MagicMock, patch

from app.services import sea_level


class SeaLevelTests(unittest.TestCase):
    def test_availability_uses_finite_noaa_grid_value(self):
        row = {
            "latitude (degrees_north)": "43.125",
            "longitude (degrees_east)": "35.125",
            "sla (m)": "-0.0177",
        }
        with patch.object(sea_level, "_read_noaa_rows", return_value=[row]):
            result = sea_level.check_sea_level_availability(43.0, 35.0)
        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["dataset_id"], "noaacwBLENDEDsshDaily")

    def test_availability_treats_noaa_nan_as_land_or_missing_ocean_cell(self):
        with patch.object(
            sea_level, "_read_noaa_rows", return_value=[{"sla (m)": "NaN"}]
        ):
            result = sea_level.check_sea_level_availability(39.0, 35.0)
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "land_or_no_ocean_cell")

    def test_noaa_annual_series_averages_daily_altimetry_observations(self):
        rows = [
            {"time (UTC)": "2017-02-13T00:00:00Z", "sla (m)": "0.2"},
            {"time (UTC)": "2017-03-01T00:00:00Z", "sla (m)": "0.4"},
            {"time (UTC)": "2018-01-01T00:00:00Z", "sla (m)": "NaN"},
            {"time (UTC)": "2018-01-02T00:00:00Z", "sla (m)": "0.3"},
        ]
        with patch.object(sea_level, "_read_noaa_rows", return_value=rows):
            result = sea_level.analyze_sea_level(43.0, 35.0, 2017, 2018)

        self.assertEqual(result["source"], "NOAA CoastWatch blended satellite altimetry")
        self.assertEqual(result["dataset_id"], "noaacwBLENDEDsshDaily")
        self.assertEqual(result["raw_series"], [
            {"date": "2017-01-01", "year": 2017, "value": 0.3},
            {"date": "2018-01-01", "year": 2018, "value": 0.3},
        ])

    def test_noaa_land_cell_does_not_fall_back_to_hycom(self):
        with patch.object(
            sea_level, "_read_noaa_rows", return_value=[{"sla (m)": "NaN"}]
        ), patch.object(sea_level, "_analyze_hycom_fallback") as hycom:
            with self.assertRaisesRegex(ValueError, "select a point over open water"):
                sea_level.analyze_sea_level(39.0, 35.0, 2017, 2020)
        hycom.assert_not_called()

    def test_hycom_fallback_hides_significance_and_warns_about_model_steps(self):
        fake_ee = MagicMock()
        fake_ee.FeatureCollection.return_value.getInfo.return_value = {
            "features": [
                {"properties": {"year": year, "value": value}}
                for year, value in [
                    (2017, 0.0), (2018, 0.0), (2019, 0.0),
                    (2020, 100.0), (2021, 100.0), (2022, 100.0), (2023, 100.0),
                ]
            ],
        }
        with patch.object(sea_level, "ee", fake_ee):
            result = sea_level._analyze_hycom_fallback(
                43.0, 35.0, 2017, 2023, "NOAA unavailable"
            )

        self.assertTrue(result["model_output"])
        self.assertEqual(result["step_change_year"], 2020)
        self.assertIsNone(result["z_score"])
        self.assertIsNone(result["p_value"])
        self.assertIsNone(result["significant"])
        self.assertEqual(result["test_status"], "not_applicable_model")
        self.assertIn("model/version transitions", result["fallback_warning"])

    def test_step_detection_ignores_smooth_linear_trend(self):
        series = [(year, (year - 2000) * 2.0) for year in range(2000, 2010)]
        self.assertIsNone(sea_level._detect_step_change(series))


if __name__ == "__main__":
    unittest.main()
