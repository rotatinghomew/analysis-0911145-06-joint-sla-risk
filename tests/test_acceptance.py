import json
import os
import threading
import unittest
from app.client import analysis
from app.server import make_server
from app.study_store import load_case


@unittest.skipUnless(os.environ.get('RUN_ACCEPTANCE') == '1', '分析消费接口尚未接入')
class AnalysisContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server()
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.worker.join(timeout=3)
        cls.server.server_close()

    def test_consumer_contract_and_provenance(self):
        result = analysis(self.base)
        self.assertEqual(result['snapshot'], load_case('standard')['_snapshot'])
        for field in ['reference', 'structures', 'multiplicity', 'validation', 'diagnostics']:
            self.assertIn(field, result)
        json.dumps(result, allow_nan=False)

    def test_information_limits_are_visible(self):
        result = analysis(self.base, 'edge')
        self.assertEqual(result['snapshot'], load_case('edge')['_snapshot'])
        self.assertTrue(result['diagnostics'])

    def test_a_fully_fixed_network_is_not_given_a_fake_significance(self):
        result = analysis(self.base, 'fixed')
        self.assertFalse(result['reference']['variable'])
        self.assertTrue(all(row['p_value'] is None for row in result['structures']))

    def test_finite_probability_or_explicitly_unavailable(self):
        result = analysis(self.base)
        for row in result['structures']:
            if row['p_value'] is not None:
                self.assertLessEqual(0, row['p_value'])
                self.assertLessEqual(row['p_value'], 1)
