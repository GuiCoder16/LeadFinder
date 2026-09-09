import unittest
import copy
from services.commercial_intelligence import (
    analyze_parameter_performance, 
    calculate_commercial_trend, 
    analyze_provider_performance,
    build_commercial_intelligence_dashboard
)

class TestSprint771Hardening(unittest.TestCase):

    def test_parameter_analysis_deterministic_combo(self):
        history = [
            {"status": "success", "params": {"cidade": "SP", "segmento": "Tech"}, "commercial_metrics": {"total_leads": 10}},
            {"status": "success", "params": {"segmento": "Tech", "cidade": "SP"}, "commercial_metrics": {"total_leads": 10}}
        ]
        res = analyze_parameter_performance(history)
        # Ambas execuções devem convergir para a mesma combo independente da ordem original das chaves
        self.assertEqual(len(res["combinations"]), 1)
        self.assertTrue("cidade:SP | segmento:Tech" in res["best_combination"])

    def test_trend_temporal_order_real(self):
        history = [
            {"status": "success", "timestamp": 300, "commercial_metrics": {"total_leads": 100}}, # newer, better
            {"status": "success", "timestamp": 100, "commercial_metrics": {"total_leads": 1}},   # older, worse
            {"status": "success", "timestamp": 400, "commercial_metrics": {"total_leads": 100}}, # newer, better
            {"status": "success", "timestamp": 200, "commercial_metrics": {"total_leads": 1}}    # older, worse
        ]
        # Embaralhados temporalmente. A função deve ordenar: 100, 200, 300, 400 e acusar melhora.
        trend = calculate_commercial_trend(history)
        self.assertEqual(trend, "improving")

    def test_severely_malformed_history_zero_crash(self):
        corrupt_history = [
            None,
            [],
            {"status": "success", "params": "lixo", "durations": [], "commercial_metrics": 123},
            {"status": "success", "provider": ["not_a_string"]}
        ]
        # Deve processar graciosamente devolvendo dictionaries vazios ou 0s
        dash = build_commercial_intelligence_dashboard(corrupt_history)
        self.assertTrue(isinstance(dash, dict))

    def test_analytics_deep_copy_isolation(self):
        history = [{"status": "success", "params": {"cidade": "A"}}]
        snapshot = copy.deepcopy(history)
        build_commercial_intelligence_dashboard(history)
        # Garante a imutabilidade do History original
        self.assertEqual(history, snapshot)

    def test_provider_normalization(self):
        history = [{"status": "success", "provider": " OPeNaI "}, {"status": "success", "provider": "alien"}]
        res = analyze_provider_performance(history)
        self.assertIn("openai", res)
        self.assertIn("unknown", res)

if __name__ == '__main__':
    unittest.main()