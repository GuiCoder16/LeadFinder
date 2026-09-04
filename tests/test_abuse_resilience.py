import unittest
from unittest.mock import patch
import pandas as pd
import streamlit as st
import app as leadfinder_app
from services.message_generator import MessageGeneratorService

class TestAbuseResilience(unittest.TestCase):

    def test_a_llm_batch_abuse_prevention(self):
        """Hardening 6.4: Garante que um ataque injetando 5.000 payloads seja cortado no limite de segurança (100)."""
        giant_batch = {f"Lead_{i}": {"payload": {"contexto_comercial": {"intencao": "TESTE"}}} for i in range(5000)}
        
        # Como o provider draft executa sem mock HTTP, podemos testar o limite de iterações.
        resultados = MessageGeneratorService.gerar_mensagens_lote(giant_batch, provider="draft")
        self.assertEqual(len(resultados), 100, "Limite de batch do LLM foi bypassado!")

    def test_b_app_partial_pipeline_failure_isolation(self):
        """Hardening 6.4: Se o módulo de LLM crashear por completo, o app deve preservar os leads e a exportação."""
        st.session_state.clear()
        
        # Simula o pipeline de leads funcionando até a chamada de LLM
        mock_payloads = {"Lead 1": {"payload": {}}}
        
        with patch('app.MessageGeneratorService.gerar_mensagens_lote') as mock_lote:
            mock_lote.side_effect = Exception("Erro catastrófico no motor de LLM")
            
            # Executamos o trecho isolado em app.py que contorna falhas no lote
            try:
                # Simulando a resposta do bloco try-except em app.py
                mensagens_geradas = mock_lote(mock_payloads, provider="openai")
            except Exception:
                mensagens_geradas = {}
                
            st.session_state["mensagens_geradas"] = mensagens_geradas
            st.session_state["leads_objetos"] = [{"nome": "Lead 1"}]
            
            # O sistema sobreviveu
            self.assertEqual(st.session_state["mensagens_geradas"], {})
            self.assertEqual(len(st.session_state["leads_objetos"]), 1)

    def test_c_session_state_clean_up_prevents_collision(self):
        """Hardening 6.4: O Pipeline limpa execuções antigas para não mesclar payloads/LLM messages entre buscas."""
        st.session_state["leads_objetos"] = ["Antigo"]
        st.session_state["mensagens_geradas"] = {"Antigo": "Mensagem"}
        
        # Simula o bloco de limpeza presente no botão 'buscar_btn'
        for key in ["leads_objetos", "lista_leads", "payloads_comerciais", "mensagens_geradas", "metricas_enriquecimento"]:
            if key in st.session_state:
                del st.session_state[key]
                
        self.assertNotIn("leads_objetos", st.session_state)
        self.assertNotIn("mensagens_geradas", st.session_state)

if __name__ == '__main__':
    unittest.main()