import unittest
from unittest.mock import patch
from urllib.error import URLError

from app.services import biodiversity


class BiodiversityServiceTests(unittest.TestCase):
    def setUp(self):
        with biodiversity._cache_lock:
            biodiversity._cache.clear()

    def test_context_counts_unique_species_groups_and_threatened_taxa(self):
        def fetch(params):
            if isinstance(params["facet"], list):
                return {
                    "count": 100,
                    "facets": [
                        {
                            "field": "SPECIES_KEY",
                            "counts": [{"name": "10"}, {"name": "11"}],
                        },
                        {
                            "field": "CLASS_KEY",
                            "counts": [
                                {"name": "212", "count": 20},
                                {"name": "359", "count": 30},
                                {"name": "358", "count": 5},
                                {"name": "131", "count": 4},
                                {"name": "204", "count": 6},
                                {"name": "216", "count": 10},
                            ],
                        },
                    ],
                }

            threatened_keys = {
                "VU": {"10", "11"},
                "EN": {"11", "12"},
                "CR": {"13"},
            }[params["iucnRedListCategory"]]
            return {
                "facets": [{
                    "field": "SPECIES_KEY",
                    "counts": [{"name": key} for key in threatened_keys],
                }]
            }

        with patch.object(biodiversity, "_fetch_gbif", side_effect=fetch) as fetch_mock:
            result = biodiversity.get_biodiversity_context(39.1234, 32.4567, 50)

        self.assertTrue(result["available"])
        self.assertEqual(result["species_count"], 2)
        self.assertEqual(result["threatened_species_count"], 4)
        self.assertEqual(result["group_record_counts"]["birds"], 20)
        self.assertEqual(result["group_record_counts"]["mammals"], 30)
        self.assertEqual(result["group_record_counts"]["other_or_unclassified"], 25)
        self.assertEqual(fetch_mock.call_count, 4)

    def test_rounded_coordinates_and_radius_are_used_for_cache_key(self):
        with patch.object(
            biodiversity,
            "_load_context",
            return_value={"available": True, "species_count": 7},
        ) as load_mock:
            first = biodiversity.get_biodiversity_context(39.12341, 32.45671, 50.04)
            second = biodiversity.get_biodiversity_context(39.12344, 32.45674, 50.03)

        self.assertEqual(first, second)
        load_mock.assert_called_once_with(39.123, 32.457, 50.0)

    def test_region_filter_uses_gbif_coordinate_range_parameter_names(self):
        params = biodiversity._build_region_params(39, 32, 50)

        self.assertIn("decimalLatitude", params)
        self.assertIn("decimalLongitude", params)
        self.assertEqual(params["kingdomKey"], "1")
        self.assertNotIn("latitude", params)
        self.assertNotIn("longitude", params)

    def test_upstream_failure_returns_friendly_unavailable_result(self):
        with patch.object(biodiversity, "_fetch_gbif", side_effect=URLError("offline")):
            result = biodiversity.get_biodiversity_context(39, 32, 50)

        self.assertFalse(result["available"])
        self.assertIsNone(result["species_count"])
        self.assertTrue(result["message"])


if __name__ == "__main__":
    unittest.main()
