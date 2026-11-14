import copy
import unittest
from app.study import preview, validate, current_transfers, owner_flows
from app.study_store import load_case, names
from app.study_schema import probability, positive_integer


class StudyDomainTests(unittest.TestCase):
    def test_baseline_projection(self):
        case = load_case('standard')
        self.assertEqual(len(current_transfers(case)), 192)
        self.assertTrue(all(key[1] != key[2] for key in owner_flows(case)))

    def test_all_cases_have_finite_serializable_previews(self):
        import json
        for name in names():
            case = load_case(name)
            result = preview(case)
            self.assertEqual(result['snapshot'], case['_snapshot'])
            self.assertTrue(result['descriptive_only'])
            json.dumps(result, allow_nan=False)

    def test_numeric_contracts_reject_invalid_inputs(self):
        for value in [True, float('nan'), -1, 2]:
            with self.assertRaises(ValueError):
                probability(value)
        with self.assertRaises(ValueError):
            positive_integer(0)

    def test_unknown_case_is_not_a_path(self):
        with self.assertRaises(ValueError):
            load_case('../standard')
