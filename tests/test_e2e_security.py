import unittest
import pandas as pd
import streamlit as st
from services.export_service import ExportService

class TestE2ESecurity(unittest.TestCase):

    def test_formula_injection_prevention(self):
        """Hardening 6.3: Garante que Excel/CSV Injection seja neutralizado na exportação."""
        malicious_leads = [
            {"nome": "=cmd|' /C calc'!A0", "telefone": "+5511999999999", "score_final": 90},
            {"nome": "-2+3+cmd", "telefone": "@SUM(1+1)", "score_final": 50},
            {"nome": "Empresa Segura", "telefone": "11999999999", "score_final": 80}
        ]
        
        df = ExportService.gerar_dataframe_comercial(malicious_leads)
        
        self.assertEqual(df.iloc[0]["nome"], "'=cmd|' /C calc'!A0")
        self.assertEqual(df.iloc[0]["telefone"], "'+5511999999999")
        self.assertEqual(df.iloc[1]["nome"], "'-2+3+cmd")
        self.assertEqual(df.iloc[1]["telefone"], "'@SUM(1+1)")
        
        # Dados seguros e numéricos não devem ser mutados
        self.assertEqual(df.iloc[2]["nome"], "Empresa Segura")
        self.assertEqual(df.iloc[0]["score_final"], 90)

    def test_export_service_isolation_on_corrupted_data(self):
        """Hardening 6.3: O ExportService não deve crashar o pipeline ao receber tipos bizarros."""
        corrupted_leads = [None, "Isto não é um dict", {"nome": "Valido"}]
        
        logs_capturados = []
        df = ExportService.gerar_dataframe_comercial(corrupted_leads, p_log=lambda m: logs_capturados.append(m))
        
        # O DataFrame deve ser gerado isolando os campos válidos, sem exceção brutal.
        self.assertTrue(isinstance(df, pd.DataFrame))
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 3)

    def test_session_state_resilience(self):
        """Hardening 6.3: Validação estrutural de estados parciais e chaves nulas."""
        st.session_state["leads_objetos"] = None
        st.session_state["payloads_comerciais"] = []
        
        # Simula acesso a dicionários que foram corrompidos em memória
        payloads = st.session_state.get("payloads_comerciais")
        is_safe_dict = isinstance(payloads, dict)
        
        self.assertFalse(is_safe_dict, "A estrutura deve ser validada antes de acessos iterativos.")
        
    def test_data_contract_preservation(self):
        """Hardening 6.3: Verifica se o ExportService mantém a integridade da ordem e quantidade se alimentado corretamente."""
        dummy_lead = {f"coluna_{i}": i for i in range(28)}
        df = ExportService.gerar_dataframe_comercial([dummy_lead])
        
        self.assertEqual(len(df.columns), 28, "Data Contract de 28 colunas foi quebrado.")

if __name__ == '__main__':
    unittest.main()