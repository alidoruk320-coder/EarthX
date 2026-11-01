import unittest
from unittest.mock import patch

from scripts import benchmark_monthly_batch


class MonthlyBatchBenchmarkTests(unittest.TestCase):
    def test_fresh_benchmark_clears_analysis_cache_and_counts_area_and_series_calls(self):
        benchmark_monthly_batch.region_analysis._cache["stale"] = {"status": "ok"}
        with patch.object(benchmark_monthly_batch, "analyze_region", return_value={
            "status": "ok",
            "raw_series": [{"year": 2020, "value": 1.0}],
            "missing_months": [],
        }) as analyze:
            result = benchmark_monthly_batch.run_block({}, "merra2_t2m", 2020, 2024, 5)

        self.assertEqual(benchmark_monthly_batch.region_analysis._cache, {})
        self.assertEqual(result["requests"], 2)
        self.assertEqual(result["observations"], 1)
        analyze.assert_called_once()


if __name__ == "__main__":
    unittest.main()
