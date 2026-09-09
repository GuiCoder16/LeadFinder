import sys
import unittest
import importlib
from unittest.mock import patch, MagicMock

# Classe para emular perfeitamente o comportamento do Streamlit session_state (Acessível via dict e atributo)
class FakeSessionState(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        raise AttributeError(f"No attribute {key}")
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, key):
        if key in self:
            del self[key]
        else:
            raise AttributeError(f"No attribute {key}")

class TestSprint772PipelineBehavior(unittest.TestCase):
    
    def setUp(self):
        self.mock_st = MagicMock()
        self.mock_st.session_state = FakeSessionState()
        self.mock_st.session_state.is_processing = False
        self.mock_st.session_state.current_run_id = None
        self.mock_st.session_state.last_pipeline_ts = 0.0
        self.mock_st.session_state.lista_leads = []
        self.mock_st.session_state.run_history = []
        
        sys.modules['streamlit'] = self.mock_st

    def test_extract_commercial_metrics_behavior(self):
        """Valida que as métricas comerciais são lidas rigorosamente dos dados reais, sem hardcode."""
        import app
        
        leads_mistos = [
            {"whatsapp": "119999", "email": "a@a.com", "alta_prioridade": True, "website": "x.com"},
            {"whatsapp": "⚠️ Não informado", "email": "⚠️ Não informado", "alta_prioridade": False, "website": "⚠️ Não informado"},
            {"whatsapp": None, "email": "", "alta_prioridade": "true", "website": None},
        ]
        
        metricas = app.extract_commercial_metrics(leads_mistos)
        
        self.assertEqual(metricas["total_leads"], 3)
        self.assertEqual(metricas["whatsapp"], 1) # Só o primeiro é válido
        self.assertEqual(metricas["email"], 1) # Só o primeiro é válido
        self.assertEqual(metricas["alta_prioridade"], 2) # O primeiro (True) e o terceiro ("true")
        self.assertEqual(metricas["sem_website"], 2) # O segundo (placeholder) e o terceiro (None)

    @patch('app.LeadScoringService')
    @patch('app.CommercialPayloadService')
    @patch('app.MessageGeneratorService')
    @patch('app.LeadProcessor')
    @patch('app.OverpassService')
    @patch('app.GeocodingService')
    def test_pipeline_success_commits_and_reruns(self, mock_geo, mock_over, mock_proc, mock_msg, mock_pay, mock_score):
        """Valida a progressão linear do pipeline, gravação real do commit e chamada autorizada de rerun."""
        self.mock_st.sidebar.button.return_value = True
        
        mock_geo.buscar_coordenadas.return_value = (-23.0, -46.0)
        mock_over.buscar_empresas_por_coordenadas.return_value = [{"id": 1}]
        
        fake_lead = {"nome": "Empresa X", "whatsapp": "1199"}
        mock_proc.processar_osm.return_value = [fake_lead]
        mock_score.avaliar_lote.return_value = [fake_lead]
        mock_pay.gerar_payloads_lote.return_value = {"payload": 1}
        mock_msg.gerar_mensagens_lote.return_value = {"msg": 1}
        
        import app
        importlib.reload(app)
        
        # O Commit Atômico ocorreu
        self.assertEqual(len(self.mock_st.session_state.lista_leads), 1)
        self.assertEqual(len(self.mock_st.session_state.run_history), 1)
        self.assertFalse(self.mock_st.session_state.is_processing)
        
        # O pipeline_success acionou o rerun condicional
        self.mock_st.rerun.assert_called_once()

    @patch('app.GeocodingService')
    def test_pipeline_failure_preserves_state(self, mock_geo):
        """Valida que o State anterior não é destruído e o usuário vê o st.error real (sem Rerun)."""
        self.mock_st.sidebar.button.return_value = True
        
        # Popula um estado anterior sadio
        self.mock_st.session_state.lista_leads = [{"nome": "Sadio"}]
        self.mock_st.session_state.run_history = [{"run_id": "velho"}]
        
        # Força pane crítica na rede
        mock_geo.buscar_coordenadas.side_effect = ValueError("Simulação de Falha Externa")
        
        import app
        importlib.reload(app)
        
        # Verifica a preservação do Estado e falha elegante
        self.mock_st.error.assert_called_once()
        self.mock_st.rerun.assert_not_called()
        self.assertFalse(self.mock_st.session_state.is_processing)
        self.assertEqual(len(self.mock_st.session_state.lista_leads), 1) # Estado Sadio preservado
        self.assertEqual(self.mock_st.session_state.lista_leads[0]["nome"], "Sadio")

    @patch('app.GeocodingService')
    def test_stale_run_rejects_commit(self, mock_geo):
        """Valida o descarte atômico caso um processo fantasma tente gravar."""
        self.mock_st.sidebar.button.return_value = True
        
        # Engana o Atomic Commit simulando a transição de um current_run_id por outro processo
        def fake_geo(*args, **kwargs):
            self.mock_st.session_state.current_run_id = "ID_SOBREPOSTO_FANTASMA"
            return (-23.0, -46.0)
            
        mock_geo.buscar_coordenadas.side_effect = fake_geo
        
        import app
        importlib.reload(app)
        
        # Commit Rejeitado, Success=False, Rerun barrado
        self.assertEqual(len(self.mock_st.session_state.lista_leads), 0)
        self.assertEqual(len(self.mock_st.session_state.run_history), 0)
        self.assertFalse(self.mock_st.session_state.is_processing)
        self.mock_st.rerun.assert_not_called()

if __name__ == '__main__':
    unittest.main()