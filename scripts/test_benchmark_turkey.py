import unittest

from scripts.benchmark_turkey import source_configuration_note
from app.config import region_config


class BenchmarkSourceNoteTests(unittest.TestCase):
    def test_large_region_ndvi_note_reports_selected_mod13a3_product(self):
        note = source_configuration_note(
            {
                "source_used": "MODIS/061/MOD13A3",
                "dataset_id": "MODIS/061/MOD13A3",
            },
            region_config["ndvi"],
        )

        self.assertEqual(
            note,
            "MODIS/061/MOD13A3 (selected; base MODIS/061/MOD13Q1)",
        )


if __name__ == "__main__":
    unittest.main()
