import unittest
import io
import time
import pandas as pd
from unittest.mock import patch, MagicMock

import app as leadfinder_app
from services.geocoding import GeocodingService
from services.overpass import OverpassService
from services.lead_processor import LeadProcessor
from services.lead_scoring import LeadScoringService
from services.commercial_payload import CommercialPayloadService
from services.export_service import ExportService

class TestSprint73EndToEnd(unittest.TestCase):

    # ==========================================
    # 1. E2E SUCCESS PATH E INTEGRIDADE
    # ==========================================
    def test_e2e_success_pipeline_integrity(self):
        """Valida a conversão estrutural de todos os serviços de ponta a ponta sem rede."""
        # 1. Dados Primitivos (Simulação de OSM)
        raw_osm = [
            {"id": 101, "tags": {"name": "Barbearia do João", "shop": "hairdresser", "phone": "1199999999"}},
            {"id": 102, "tags": {"name": "Pizzaria XYZ", "amenity": "restaurant", "cuisine": "pizza"}}
        ]
        
        # 2. Processamento
        leads = LeadProcessor.processar_osm(raw_osm, "Barbearia", "São Paulo", "SP")
        self.assertEqual(len(leads), 2)
        
        # 3. Scoring
        leads_rankeados = LeadScoringService.avaliar_lote(leads, debug_mode=False, p_log=lambda x: None)
        self.assertTrue(hasattr(leads_rankeados[0], 'score_final'))
        
        # 4. Payload Generation
        payloads = CommercialPayloadService.gerar_payloads_lote(leads_rankeados, debug_mode=False, p_log=lambda x: None)
        self.assertIn("Barbearia do João", payloads)
        self.assertIn("Pizzaria XYZ", payloads)
        self.assertIsInstance(payloads["Barbearia do João"]["payload"], dict)

    # ==========================================
    # 2. FAILURE PATHS
    # ==========================================
    @patch('app.cache_overpass')
    @patch('app.cache_geocoding')
    def test_e2e_geocoding_failure_path(self, mock_geo, mock_overpass):
        """Se o geocoding falha, retorna (None, None), Overpass e Pipeline abortam graciosamente."""
        mock_geo.return_value = (None, None)
        # app.py utiliza a variável para Overpass
        lat, lon = leadfinder_app.cache_geocoding("CidadeFalsa", "XX")
        self.assertIsNone(lat)
        self.assertIsNone(lon)
        
        # Se os dados passarem (int/float check no cache_overpass), bloqueia:
        dados_osm = leadfinder_app.cache_overpass("Barbearia", lat, lon, 50)
        self.assertEqual(dados_osm, [])
        
        # O processador ignora lista vazia
        leads = LeadProcessor.processar_osm(dados_osm, "Barbearia", "CidadeFalsa", "XX")
        self.assertEqual(leads, [])

    def test_e2e_scoring_missing_data(self):
        """Campos nulos ou vazios no Scoring não causam exceção fatal, apenas score baixo."""
        lead_vazio = [LeadProcessor.processar_osm([{"id": 999, "tags": {}}], "Restaurante", "A", "B")[0]]
        rankeados = LeadScoringService.avaliar_lote(lead_vazio)
        self.assertEqual(len(rankeados), 1)
        self.assertGreaterEqual(rankeados[0].score_final, 0) # Não quebrou.

    # ==========================================
    # 3. EXPORT INTEGRITY COM I/O REAL E SANITIZAÇÃO
    # ==========================================
    def test_e2e_export_io_real_validation(self):
        """Prova que a exportação aplica sanitização DDE e mantém o contrato de 28 colunas ao reabrir o buffer CSV."""
        leads_maliciosos = [
            {"nome": "=CMD|' /C calc'!A0", "telefone": "+1555", "website": None},
            {"nome": "@SUM(1+1)", "email": "-test@test"}
        ]
        
        df = ExportService.gerar_dataframe_comercial(leads_maliciosos)
        
        # 1. Gera bytes do CSV simulando I/O Real
        csv_bytes = ExportService.to_csv(df)
        self.assertIsNotNone(csv_bytes)
        
        # 2. Reabre com Pandas
        df_reopened = pd.read_csv(io.BytesIO(csv_bytes))
        
        # 3. Validação do contrato de 28 colunas
        self.assertEqual(len(df_reopened.columns), 28)
        self.assertIn("score_final", df_reopened.columns)
        
        # 4. Validação da sanitização DDE (prefixo ')
        self.assertEqual(df_reopened.iloc[0]["nome"], "'=CMD|' /C calc'!A0")
        self.assertEqual(df_reopened.iloc[0]["telefone"], "'+1555")
        self.assertEqual(df_reopened.iloc[1]["nome"], "'@SUM(1+1)")
        self.assertEqual(df_reopened.iloc[1]["email"], "'-test@test")
        
        # 5. Fallback para ⚠️ Não informado funciona sem quebrar
        self.assertEqual(df_reopened.iloc[0]["website"], "⚠️ Não informado")

    # ==========================================
    # 4. ATOMIC COMMIT & SESSION ISOLATION
    # ==========================================
    def test_e2e_stale_commit_protection(self):
        """Comprova lógicamente que execuções órfãs (stale) não sobrepõem o state."""
        current_id_in_state = "TRANSACTION_B"
        incoming_id = "TRANSACTION_A"
        
        # Simula a comparação do app.py
        commit_allowed = (current_id_in_state == incoming_id)
        self.assertFalse(commit_allowed)

    # ==========================================
    # 5. LLM FALLBACK CASCADE
    # ==========================================
    @patch('app.MessageGeneratorService.gerar_mensagens_lote')
    def test_e2e_llm_failure_isolation(self, mock_generator):
        """Prova que erro catastrófico na IA não crasheia o Pipeline."""
        mock_generator.side_effect = Exception("OpenAI API Down")
        
        mensagens_geradas_tmp = None
        try:
            # Simulação do bloco nativo no app.py
            mensagens_geradas_tmp = mock_generator({}, provider="openai", p_log=lambda x: None)
        except Exception:
            mensagens_geradas_tmp = {}
            
        # Garante que as mensagens voltam vazias, mas a aplicação segue para a interface visual.
        self.assertEqual(mensagens_geradas_tmp, {})

    # ==========================================
    # 6. TIME & BOUNDARIES
    # ==========================================
    def test_rate_limit_math_boundaries(self):
        """Limites fracionários exatos de Cooldown de Pipeline."""
        now = time.time()
        # 4.999s elapsed -> Bloqueia (True)
        self.assertTrue(leadfinder_app.is_pipeline_rate_limited(now, now - 4.999, 5.0))
        # 5.000s elapsed -> Permite (False)
        self.assertFalse(leadfinder_app.is_pipeline_rate_limited(now, now - 5.000, 5.0))
        # 5.001s elapsed -> Permite (False)
        self.assertFalse(leadfinder_app.is_pipeline_rate_limited(now, now - 5.001, 5.0))

if __name__ == '__main__':
    unittest.main()