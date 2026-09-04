import unittest
import os
import ast
import time
import requests
import pandas as pd
from unittest.mock import patch, MagicMock

import app as leadfinder_app
from services.overpass import OverpassService
from services.geocoding import GeocodingService
from services.export_service import ExportService

class TestSprint7Hardening(unittest.TestCase):

    # ==========================================
    # NETWORK TIMEOUTS & EXCEPTIONS
    # ==========================================
    @patch('requests.post')
    def test_overpass_timeout_config_is_explicit(self, mock_post):
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"{}"]
        mock_post.return_value = mock_response
        OverpassService.buscar_empresas_por_coordenadas("Barbearia", 1.0, 1.0, 10)
        
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs.get('timeout'), 30)
        self.assertEqual(kwargs.get('stream'), True)

    @patch('requests.get')
    def test_geocoding_timeout_config_is_explicit(self, mock_get):
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"[]"]
        mock_get.return_value = mock_response
        GeocodingService.buscar_coordenadas("SP", "SP")
        
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs.get('timeout'), 15)
        self.assertEqual(kwargs.get('stream'), True)

    @patch('requests.post')
    def test_overpass_timeout_is_fail_closed(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Timeout real simulado")
        res = OverpassService.buscar_empresas_por_coordenadas("Barbearia", 1.0, 1.0, 10)
        self.assertEqual(res, [])

    @patch('requests.post')
    def test_overpass_http_500_fail_closed(self, mock_post):
        """[Sprint 7.2] Prova proteção contra falhas genéricas (HTTP 502/503)"""
        mock_post.side_effect = requests.exceptions.HTTPError("502 Bad Gateway")
        res = OverpassService.buscar_empresas_por_coordenadas("Restaurante", 1.0, 1.0, 10)
        self.assertEqual(res, []) # Isolamento absoluto contra instabilidade de Upstream.

    # ==========================================
    # RESPONSE BOMB (OOM PREVENTION EFICIENTE)
    # ==========================================
    @patch('requests.post')
    def test_response_bomb_overpass_aborts(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"A" * (1024 * 1024)] * 6
        mock_post.return_value = mock_resp
        res = OverpassService.buscar_empresas_por_coordenadas("Restaurante", 0, 0, 10)
        self.assertEqual(res, [])

    @patch('requests.get')
    def test_response_bomb_geocoding_aborts(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [b"A" * (1024 * 1024)] * 6
        mock_get.return_value = mock_resp
        lat, lon = GeocodingService.buscar_coordenadas("SP", "SP")
        self.assertIsNone(lat)
        self.assertIsNone(lon)

    # ==========================================
    # RATE LIMITING PURE FUNCTIONS
    # ==========================================
    def test_pipeline_rate_limit_blocks_burst(self):
        now = time.time()
        self.assertTrue(leadfinder_app.is_pipeline_rate_limited(now, now - 2.0, 5.0))
        self.assertFalse(leadfinder_app.is_pipeline_rate_limited(now, now - 6.0, 5.0))
        self.assertTrue(leadfinder_app.is_pipeline_rate_limited(now, now, 5.0))

    @patch('app.MessageGeneratorService.gerar_mensagem')
    @patch('app.st.warning')
    def test_rate_limit_regeneracao_individual(self, mock_warning, mock_gerar):
        import app
        app.st.session_state.clear()
        app.st.session_state["payloads_comerciais"] = {
            "LeadX": {"payload": {}}, 
            "LeadY": {"payload": {}}
        }
        logs = []
        mock_gerar.return_value = {"status": "ok"}
        
        app.regenerar_mensagem_individual("LeadX", "draft", logs.append)
        self.assertEqual(mock_gerar.call_count, 1)
        
        app.regenerar_mensagem_individual("LeadX", "draft", logs.append)
        self.assertEqual(mock_gerar.call_count, 1) # Bloqueado
        self.assertIn("[RATE LIMIT]", logs[-1])
        
        app.regenerar_mensagem_individual("LeadY", "draft", logs.append)
        self.assertEqual(mock_gerar.call_count, 2)

    # ==========================================
    # SESSION STATE CORRUPTION (SPRINT 7.2)
    # ==========================================
    @patch('app.MessageGeneratorService.gerar_mensagem')
    @patch('app.st.warning')
    def test_regenerar_mensagem_handles_corrupt_state(self, mock_warning, mock_gerar):
        """[Sprint 7.2] Callbacks ignoram RAM corrompida sem causar crash de thread."""
        import app
        app.st.session_state.clear()
        
        logs = []
        # Injeção de Tipo Incorreto (Lista invés de Dict)
        app.st.session_state["payloads_comerciais"] = ["LeadX", "LeadY"] 
        app.regenerar_mensagem_individual("LeadX", "draft", logs.append)
        self.assertEqual(mock_gerar.call_count, 0)
        
        # Injeção de Dicionário Sem "payload" key
        app.st.session_state["payloads_comerciais"] = {"LeadX": {"broken_data": 123}}
        app.regenerar_mensagem_individual("LeadX", "draft", logs.append)
        self.assertEqual(mock_gerar.call_count, 0)

    # ==========================================
    # LOGGING E DATA REDACTION
    # ==========================================
    @patch('builtins.print')
    def test_console_log_redaction_and_masking(self, mock_print):
        import app
        fake_secrets = ["sk-12345678901234567890123456", "super_secret_env"]
        
        app.console_log("Minha key OpenAI sk-12345678901234567890123456", debug_mode=True, active_secrets=fake_secrets)
        output = mock_print.call_args[0][0]
        self.assertNotIn("sk-123456", output)
        self.assertIn("***REDACTED_OAI***", output)
        
        ex = ValueError("TELEFONE: 11999999999")
        app.console_log(ex, debug_mode=True)
        output_exc = mock_print.call_args[0][0]
        
        self.assertEqual(output_exc, "ValueError") 
        self.assertNotIn("119", output_exc)
        
        mock_print.reset_mock()
        app.console_log("Should Not Show", debug_mode=False)
        mock_print.assert_not_called()

    # ==========================================
    # EXPORT INTEGRITY & DDE INJECTION (SPRINT 7.2)
    # ==========================================
    def test_export_formula_injection_protection(self):
        """[Sprint 7.2] CSV/XLSX DDE (Macro) Injection é castrada com apóstrofo."""
        leads_maliciosos = [
            {"nome": "=CMD|' /C calc'!A0", "telefone": "+1-555-0199"},
            {"nome": "@SUM(A1:A10)", "endereco": "-AlgumaRua"},
            {"nome": "Empresa Limpa", "website": "https://ok.com"}
        ]
        
        df = ExportService.gerar_dataframe_comercial(leads_maliciosos)
        
        self.assertEqual(df.iloc[0]["nome"], "'=CMD|' /C calc'!A0")
        self.assertEqual(df.iloc[0]["telefone"], "'+1-555-0199")
        self.assertEqual(df.iloc[1]["nome"], "'@SUM(A1:A10)")
        self.assertEqual(df.iloc[1]["endereco"], "'-AlgumaRua")
        
        # Registros sadios são intocados
        self.assertEqual(df.iloc[2]["nome"], "Empresa Limpa")
        self.assertEqual(df.iloc[2]["website"], "https://ok.com")

    def test_export_maintains_28_column_contract(self):
        """[Sprint 7.2] Exportações com exceções e dados falhos mantêm 28 colunas exatas."""
        # Dicionário sub-alimentado (Falta a maioria das chaves)
        leads_incompletos = [{"nome": "Apenas Nome", "id_osm": 1234}]
        
        df = ExportService.gerar_dataframe_comercial(leads_incompletos)
        self.assertEqual(len(df.columns), 28)
        self.assertEqual(ExportService.EXPECTED_COLUMNS, 28)
        
        # Fallback preenche valores de chaves inexistentes graciosamente
        self.assertEqual(df.iloc[0]["telefone"], "⚠️ Não informado")

    # ==========================================
    # RESOURCE LIMITS E TYPE BOUNDS
    # ==========================================
    def test_resource_limits_clamps_abnormal_inputs(self):
        import app
        self.assertEqual(app.parse_safe_quantity(-50), 10)
        self.assertEqual(app.parse_safe_quantity(9999), 500)
        self.assertEqual(app.parse_safe_quantity(float('inf')), 50)
        self.assertEqual(app.parse_safe_quantity(float('nan')), 50)

    # ==========================================
    # DEPENDENCY/SUPPLY CHAIN A.S.T
    # ==========================================
    def test_no_unsafe_dynamic_execution_exists(self):
        banned = {'eval', 'exec', 'pickle'}
        found = []
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        for root, dirs, files in os.walk(project_root):
            if any(ign in root for ign in ['.venv', 'venv', '.git', '__pycache__']):
                continue
                
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf-8') as f:
                        try:
                            tree = ast.parse(f.read())
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in banned:
                                    found.append(f"{file}:{getattr(node.func, 'id', '')}")
                        except SyntaxError:
                            self.fail(f"FALHA ESTRITA: Erro de sintaxe inaceitável no arquivo {file}. Supply chain comprometido.")
                        except UnicodeDecodeError:
                            self.fail(f"FALHA ESTRITA: Arquivo binário mascarado de .py {file}.")
                            
        self.assertEqual(len(found), 0, f"Found unsafe execution: {found}")

if __name__ == '__main__':
    unittest.main()