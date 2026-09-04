import unittest
import json
from models.lead import Lead
from services.commercial_payload import CommercialPayloadService

class TestCommercialPayloadValidation(unittest.TestCase):

    def setUp(self):
        # Base limpa para cada teste
        self.lead_base = Lead(
            nome="Empresa Teste", categoria="Mecânica", cidade="Guarulhos", estado="SP"
        )
        self.lead_base.score_final = 80
        self.lead_base.classificacao_prioridade = "🔥 PRIORIDADE MÁXIMA"

    def test_a_criacao_website(self):
        """TESTE A: Lead sem site, com WhatsApp -> CRIACAO_WEBSITE"""
        self.lead_base.website = "⚠️ Não encontrado"
        self.lead_base.whatsapp = "https://wa.me/5511999999999"
        self.lead_base.motivos_positivos = ["🚀 ALTA Oportunidade: Sem website."]
        
        payload, _ = CommercialPayloadService.gerar_payload(self.lead_base)
        
        self.assertEqual(payload["contexto_comercial"]["intencao"], "CRIACAO_WEBSITE")
        self.assertIn("Landing Page ou Site Institucional", " ".join(payload["contexto_comercial"]["oportunidades"]))
        self.assertFalse(payload["presenca_digital"]["tem_website"])
        self.assertTrue(payload["presenca_digital"]["tem_whatsapp"])

    def test_b_melhoria_presenca_digital(self):
        """TESTE B: Site existe, WA existe, sem Redes Sociais -> MELHORIA_PRESENCA_DIGITAL"""
        self.lead_base.website = "https://empresa.com"
        self.lead_base.whatsapp = "https://wa.me/5511999999999"
        self.lead_base.instagram = "⚠️ Não encontrado"
        
        payload, _ = CommercialPayloadService.gerar_payload(self.lead_base)
        
        self.assertEqual(payload["contexto_comercial"]["intencao"], "MELHORIA_PRESENCA_DIGITAL")

    def test_c_presenca_digital_completa(self):
        """TESTE C: Todos os canais presentes -> PRESENCA_DIGITAL_COMPLETA"""
        self.lead_base.website = "https://empresa.com"
        self.lead_base.whatsapp = "https://wa.me/5511999999999"
        self.lead_base.instagram = "https://instagram.com/empresa"
        self.lead_base.facebook = "https://facebook.com/empresa"
        
        payload, _ = CommercialPayloadService.gerar_payload(self.lead_base)
        
        self.assertEqual(payload["contexto_comercial"]["intencao"], "PRESENCA_DIGITAL_COMPLETA")
        self.assertIn("gestão de tráfego", " ".join(payload["contexto_comercial"]["oportunidades"]))

    def test_d_baixa_oportunidade(self):
        """TESTE D: Score muito baixo -> BAIXA_OPORTUNIDADE"""
        self.lead_base.score_final = 25
        self.lead_base.classificacao_prioridade = "⚪ BAIXA PRIORIDADE"
        self.lead_base.website = "⚠️ Não encontrado"
        self.lead_base.whatsapp = "⚠️ Não encontrado"
        
        payload, _ = CommercialPayloadService.gerar_payload(self.lead_base)
        
        self.assertEqual(payload["contexto_comercial"]["intencao"], "BAIXA_OPORTUNIDADE")

    def test_limpeza_de_dados(self):
        """TESTE LIMPEZA: '⚠️ Não encontrado' e inválidos devem virar None"""
        self.lead_base.website = "⚠️ Não encontrado"
        self.lead_base.facebook = "❌ Falha"
        self.lead_base.instagram = ""
        
        payload, _ = CommercialPayloadService.gerar_payload(self.lead_base)
        
        self.assertIsNone(payload["presenca_digital"]["website"])
        self.assertIsNone(payload["contato"]["facebook"])
        self.assertIsNone(payload["contato"]["instagram"])

    def test_serializacao(self):
        """TESTE SERIALIZAÇÃO: O payload deve ser convertível em JSON sem quebrar (UTF-8, None, etc)"""
        self.lead_base.nome = "Maçã & Açaí 🚀" # Teste de acentos e emojis
        self.lead_base.website = "⚠️ Não encontrado"
        
        payload, size = CommercialPayloadService.gerar_payload(self.lead_base)
        
        try:
            json_str = json.dumps(payload, ensure_ascii=False)
            self.assertTrue(isinstance(json_str, str))
            self.assertGreater(size, 0)
        except Exception as e:
            self.fail(f"Falha na serialização JSON: {e}")

    def test_isolamento_referencias(self):
        """TESTE ISOLAMENTO: Payload A não pode vazar dados pro Payload B"""
        lead_a = Lead(nome="Empresa A", categoria="Mecânica")
        lead_a.motivos_positivos = ["Motivo A"]
        
        lead_b = Lead(nome="Empresa B", categoria="Restaurante")
        lead_b.motivos_positivos = ["Motivo B"]
        
        payload_a, _ = CommercialPayloadService.gerar_payload(lead_a)
        payload_b, _ = CommercialPayloadService.gerar_payload(lead_b)
        
        self.assertNotEqual(payload_a["empresa"]["nome"], payload_b["empresa"]["nome"])
        self.assertIn("Motivo A", payload_a["contexto_comercial"]["motivos_positivos"])
        self.assertNotIn("Motivo B", payload_a["contexto_comercial"]["motivos_positivos"])

    def test_exclusao_dados_tecnicos(self):
        """TESTE EXCLUSÃO: Dados como latitude e osm_id não devem existir no payload"""
        self.lead_base.latitude = -23.5505
        self.lead_base.osm_id = "node/123456"
        self.lead_base.tempo_processamento_ms = 1500
        
        payload, _ = CommercialPayloadService.gerar_payload(self.lead_base)
        
        payload_str = json.dumps(payload)
        self.assertNotIn("latitude", payload_str)
        self.assertNotIn("osm_id", payload_str)
        self.assertNotIn("tempo_processamento", payload_str)

    def test_geracao_em_lote(self):
        """TESTE BATCH: Testar processamento de lote sem erros"""
        lote = [
            Lead(nome="Lead 1", categoria="A"),
            Lead(nome="Lead 2", categoria="B"),
            Lead(nome="Lead 3", categoria="C"),
            Lead(nome="Lead 4", categoria="D")
        ]
        
        payloads_lote = CommercialPayloadService.gerar_payloads_lote(lote, debug_mode=False)
        self.assertEqual(len(payloads_lote), 4)
        self.assertIn("Lead 1", payloads_lote)
        self.assertIn("payload", payloads_lote["Lead 1"])
        self.assertIn("size", payloads_lote["Lead 1"])

if __name__ == '__main__':
    unittest.main()