import os
import threading
import unittest

from app.client import analysis
from app.server import make_server
from app.store import load_case


@unittest.skipUnless(os.environ.get('RUN_ACCEPTANCE') == '1', 'new analysis feature not enabled')
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

    def test_result_has_consumer_fields_and_provenance(self):
        result = analysis(self.base)
        self.assertEqual(result['snapshot'], load_case('standard')['_snapshot'])
        for field in ['marginal', 'joint', 'alternatives', 'diagnostics']:
            self.assertIn(field, result)
        self.assertTrue(result['diagnostics'])

    def test_edge_case_is_not_silently_treated_as_standard(self):
        standard = analysis(self.base)
        edge = analysis(self.base, 'edge')
        self.assertNotEqual(standard['snapshot'], edge['snapshot'])
        self.assertTrue(edge['diagnostics'])

    def test_probability_intervals_are_ordered(self):
        result = analysis(self.base)
        interval = result['joint']['any_late']
        self.assertLessEqual(0.0, interval['lower'])
        self.assertLessEqual(interval['lower'], interval['upper'])
        self.assertLessEqual(interval['upper'], 1.0)

    def test_zero_hour_promise_cannot_be_reported_as_on_time(self):
        result = analysis(self.base, thresholds={'east': 0, 'south': 0, 'north': 0})
        interval = result['joint']['any_late']
        self.assertAlmostEqual(interval['lower'], 1.0, places=7)
        self.assertAlmostEqual(interval['upper'], 1.0, places=7)
