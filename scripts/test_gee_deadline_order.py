import unittest
from unittest.mock import patch

from scripts import benchmark_quick, diagnose_subsample


class DeadlineInitializationOrderTests(unittest.TestCase):
    def assert_deadline_follows_initialization(self, module):
        events = []
        with (
            patch.object(module, "GEE_PROJECT_ID", "test-project"),
            patch.object(module, "init_gee", side_effect=lambda: events.append("init") or True),
            patch.object(module, "is_gee_initialized", side_effect=lambda: events.append("initialized") or True),
            patch.object(module.ee.data, "setDeadline", side_effect=lambda _timeout: events.append("deadline")),
        ):
            self.assertTrue(module.initialize_gee_with_deadline())
        self.assertEqual(events, ["init", "initialized", "deadline"])

    def assert_no_deadline_when_initialization_fails(self, module):
        events = []
        with (
            patch.object(module, "GEE_PROJECT_ID", "test-project"),
            patch.object(module, "init_gee", side_effect=lambda: events.append("init") or False),
            patch.object(module.ee.data, "setDeadline", side_effect=lambda _timeout: events.append("deadline")),
        ):
            self.assertFalse(module.initialize_gee_with_deadline())
        self.assertEqual(events, ["init"])

    def test_diagnose_subsample_sets_deadline_after_initialization(self):
        self.assert_deadline_follows_initialization(diagnose_subsample)

    def test_diagnose_subsample_does_not_set_deadline_if_initialization_fails(self):
        self.assert_no_deadline_when_initialization_fails(diagnose_subsample)

    def test_benchmark_quick_sets_deadline_after_initialization(self):
        self.assert_deadline_follows_initialization(benchmark_quick)

    def test_benchmark_quick_does_not_set_deadline_if_initialization_fails(self):
        self.assert_no_deadline_when_initialization_fails(benchmark_quick)


if __name__ == "__main__":
    unittest.main()
