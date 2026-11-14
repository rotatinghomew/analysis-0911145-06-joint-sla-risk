import unittest
from app.lanes import duration_evidence, promise_status
from app.calendar import environment_groups
from app.store import load_case


class LaneTests(unittest.TestCase):
    def test_unfinished_journey_is_not_on_time(self):
        row = {'duration_lower': 10, 'duration_upper': None, 'complete': False}
        self.assertEqual(promise_status(row, 24), 'unknown')
        self.assertEqual(promise_status(row, 8), 'late')

    def test_shared_environment_is_not_independent_days(self):
        groups = environment_groups(load_case('standard')['shipments'])
        self.assertEqual(len(groups), 36)
        self.assertGreater(len(groups['day0']), 3)

    def test_exact_time_contract(self):
        with self.assertRaises(ValueError):
            duration_evidence({'duration_lower': 5, 'duration_upper': None, 'complete': True})
