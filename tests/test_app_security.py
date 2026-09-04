import unittest
from unittest.mock import patch
import os
import streamlit as st
import app as leadfinder_app

class TestAppSecurityV2(unittest.TestCase):

    def test_escape_html_content_prevents_xss(self):
        """Hardening 6.2: Garante que XSS e quebra de layout HTML sejam evitados em Markdown."""
        xss_payload = "<script>alert('XSS!')</script> <img src=x onerror=alert(1)>"
        safe_output = leadfinder_app.escape_html_content(xss_payload)
        self.assertNotIn("<script>", safe_output)
        self.assertNotIn("<img", safe_output)
        self.assertEqual(safe_output, "&lt;script&gt;alert(&#x27;XSS!&#x27;)&lt;/script&gt; &lt;img src=x onerror=alert(1)&gt;")

    def test_regenerar_mensagem_invalid_provider_fallback(self):
        """Hardening 6.2: Garante que provider injetado caia nativamente no draft."""
        logs_capturados = []
        def mock_logger(msg): logs_capturados.append(msg)
        
        st.session_state["payloads_comerciais"] = {"Empresa X": {"payload": {}}}
        
        with patch('app.MessageGeneratorService.gerar_mensagem') as mock_gerar:
            leadfinder_app.regenerar_mensagem_individual("Empresa X", "HACK_PROVIDER", mock_logger)
            args, kwargs = mock_gerar.call_args
            self.assertEqual(kwargs.get("provider"), "draft")

    def test_regenerar_mensagem_corrupted_session_state(self):
        """Hardening 6.2: Impede crash ao tentar regenerar com Session State corrompido."""
        logs_capturados = []
        def mock_logger(msg): logs_capturados.append(msg)
        
        st.session_state["payloads_comerciais"] = [] # Incorreto, deveria ser dict
        leadfinder_app.regenerar_mensagem_individual("Empresa X", "openai", mock_logger)
        
        self.assertTrue(any("não encontrado no payload" in log for log in logs_capturados))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-secret-1234"})
    def test_console_log_secret_redaction(self):
        """Hardening 6.2: Garante ofuscação de credenciais nos logs."""
        logs_capturados = []
        with patch('builtins.print') as mock_print:
            # Ativa manual o debug mode local
            leadfinder_app.debug_mode = True 
            leadfinder_app.console_log("Erro de timeout na chave sk-secret-1234")
            
            printed_val = mock_print.call_args[0][0]
            self.assertNotIn("sk-secret-1234", printed_val)
            self.assertIn("***REDACTED***", printed_val)

if __name__ == '__main__':
    unittest.main()