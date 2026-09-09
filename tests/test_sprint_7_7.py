import unittest
from services.commercial_intelligence import _calculate_commercial_score, find_best_commercial_run, analyze_efficiency

class TestSprint77CommercialIntelligence(unittest.TestCase):
    
    def test_calculate_commercial_score_deterministic(self):
        run_mock = {
            "status": "success",
            "commercial_metrics": {"total_leads": 10, "whatsapp": 5, "email": 2, "alta_prioridade": 1, "sem_website": 4},
            "durations": {"total_duration": 9.0}
        }
        # Math: hp(5) + sw(12) + wa(10) + em(2) + leads(5) = 34
        # efficiency: 1.0 + log10(9+1) = 2.0. Score = 34 / 2.0 = 17.0
        score = _calculate_commercial_score(run_mock)
        self.assertEqual(score, 17.0)

    def test_find_best_commercial_run_ignores_failed(self):
        history = [
            {"run_id": "FAILED_RUN", "status": "failed", "commercial_metrics": {"total_leads": 1000}},
            {"run_id": "VALID_RUN", "status": "success", "commercial_metrics": {"total_leads": 5}}
        ]
        best = find_best_commercial_run(history)
        self.assertEqual(best["run_id"], "VALID_RU") # truncated to 8

    def test_analyze_efficiency_safeguard(self):
        history = [{"status": "success", "durations": {"total_duration": 0}, "commercial_metrics": {"total_leads": 10}}]
        eff = analyze_efficiency(history)
        self.assertEqual(eff, {}) # Evita division by zero

if __name__ == '__main__':
    unittest.main()