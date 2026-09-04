import ast
import os
import unittest
import copy
import pandas as pd

from models.lead import Lead
from services.lead_processor import LeadProcessor
from services.lead_scoring import LeadScoringService
from services.commercial_payload import CommercialPayloadService
from services.message_generator import MessageGeneratorService
from services.export_service import ExportService
from services.overpass import OverpassService
from services.geocoding import GeocodingService


class TestSprint691ProductionHardening(unittest.TestCase):

    def test_a_dependency_surface_is_safe(self):
        banned = {"eval", "exec"}
        found = []
        for root, _, files in os.walk("."):
            for name in files:
                if not name.endswith(".py") or name.startswith("test_"):
                    continue
                path = os.path.join(root, name)
                try:
                    tree = ast.parse(open(path, encoding="utf-8").read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in banned:
                            found.append(f"{node.func.id}:{path}")
                except (OSError, SyntaxError):
                    continue
        self.assertEqual(found, [])

    def test_b_no_unsafe_dynamic_execution(self):
        for path in ["app.py", "services/lead_processor.py", "services/lead_scoring.py",
                     "services/commercial_payload.py", "services/message_generator.py"]:
            text = open(path, encoding="utf-8").read()
            self.assertNotIn("pickle", text)
            self.assertNotIn("os.system(", text)
            self.assertNotIn("subprocess.", text)

    def test_c_cross_layer_invalid_dict_is_rejected(self):
        self.assertEqual(LeadScoringService.avaliar_lote({"bad": 1}), [])

    def test_d_cross_layer_invalid_list_items_are_isolated(self):
        valid_a = Lead("A")
        valid_b = Lead("B")
        result = LeadScoringService.avaliar_lote([valid_a, "bad", None, valid_b])
        self.assertEqual(len(result), 2)

    def test_e_cross_layer_none_is_rejected(self):
        self.assertEqual(CommercialPayloadService.gerar_payloads_lote(None), {})

    def test_f_identity_collision_isolated(self):
        data = [
            {"id": "1", "type": "node", "lat": 1, "lon": 1, "tags": {"name": "Loja"}},
            {"id": "2", "type": "node", "lat": 1.0001, "lon": 1.0001, "tags": {"name": "Loja"}},
        ]
        leads = LeadProcessor.processar_osm(data, "Mecânica", "Guarulhos", "SP")
        self.assertEqual(len(leads), 2)
        self.assertNotEqual(leads[0].id_unico, leads[1].id_unico)
        self.assertNotEqual(leads[0].nome, leads[1].nome)

    def test_g_identity_is_deterministic(self):
        data = [{"id": "10", "type": "node", "lat": 1.2, "lon": 3.4, "tags": {"name": "Loja"}}]
        a = LeadProcessor.processar_osm(data, "X", "C", "SP")[0]
        b = LeadProcessor.processar_osm(data, "X", "C", "SP")[0]
        self.assertEqual(a.id_unico, b.id_unico)

    def test_h_malformed_coordinates_do_not_crash(self):
        data = [{"id": "1", "tags": {"name": "Loja", "phone": "123"}, "lat": "NaN", "lon": "Infinity"}]
        leads = LeadProcessor.processar_osm(data, "X", "C", "SP")
        self.assertEqual(len(leads), 1)
        self.assertIsNone(leads[0].latitude)
        self.assertIsNone(leads[0].longitude)

    def test_i_payload_isolated_from_lead_mutation(self):
        lead = Lead("Empresa")
        lead.score_final = 80
        lead.classificacao_prioridade = "🔥 PRIORIDADE MÁXIMA"
        lead.motivos_positivos = ["A"]
        payload, _ = CommercialPayloadService.gerar_payload(lead)
        lead.motivos_positivos.append("B")
        self.assertEqual(payload["contexto_comercial"]["motivos_positivos"], ["A"])

    def test_j_payload_size_is_bounded(self):
        lead = Lead("X" * 1000, categoria="Y" * 1000, cidade="Z" * 1000, estado="SP")
        lead.score_final = 80
        lead.classificacao_prioridade = "🔥 PRIORIDADE MÁXIMA"
        lead.motivos_positivos = ["M" * 1000] * 100
        payload, size = CommercialPayloadService.gerar_payload(lead)
        self.assertLessEqual(size, CommercialPayloadService.MAX_PAYLOAD_BYTES)
        self.assertIsInstance(payload, dict)

    def test_k_failed_scoring_does_not_escape_exception(self):
        class Broken:
            nome = "A"
            website = property(lambda self: 1 / 0)
        result = LeadScoringService.avaliar_lote([Broken()])
        self.assertEqual(len(result), 1)

    def test_l_failed_payload_generation_isolated(self):
        class Broken:
            nome = None
        self.assertEqual(CommercialPayloadService.gerar_payloads_lote([Broken()]), {})

    def test_m_provider_boundary_normalizes_invalid_values(self):
        self.assertEqual(MessageGeneratorService._normalize_provider("hacker"), "draft")
        self.assertEqual(MessageGeneratorService._normalize_provider(None), "draft")
        self.assertEqual(MessageGeneratorService._normalize_provider("OPENAI"), "openai")

    def test_n_message_rejects_invalid_payload(self):
        result = MessageGeneratorService.gerar_mensagem(None, provider="openai")
        self.assertEqual(result["status"], "error")
        self.assertTrue(result["fallback"])

    def test_o_message_error_does_not_leak_exception_text(self):
        error = Exception("EMAIL=secret@example.com Bearer sk-secret")
        safe = MessageGeneratorService._get_safe_error_msg(error, "openai")
        self.assertNotIn("secret@example.com", safe)
        self.assertNotIn("sk-secret", safe)

    def test_p_export_exactly_28_columns(self):
        df = ExportService.gerar_dataframe_comercial([{"nome": "A", "malicious": "x"}])
        self.assertEqual(len(df.columns), 28)
        self.assertNotIn("malicious", df.columns)

    def test_q_export_does_not_mutate_input(self):
        leads = [{"nome": "A", "motivos_positivos": ["x"]}]
        original = copy.deepcopy(leads)
        ExportService.gerar_dataframe_comercial(leads)
        self.assertEqual(leads, original)

    def test_r_export_formula_injection_is_blocked(self):
        df = ExportService.gerar_dataframe_comercial([{"nome": "=CMD()", "telefone": "@SUM(1+1)"}])
        self.assertEqual(df.iloc[0]["nome"], "'=CMD()")
        self.assertEqual(df.iloc[0]["telefone"], "'@SUM(1+1)")

    def test_s_external_boundaries_are_immutable(self):
        self.assertEqual(OverpassService.BASE_URL, "https://overpass-api.de/api/interpreter")
        self.assertEqual(GeocodingService.BASE_URL, "https://nominatim.openstreetmap.org/search")

    def test_t_resource_limits_are_present(self):
        self.assertEqual(OverpassService.MAX_RESPONSE_SIZE, 5 * 1024 * 1024)
        self.assertEqual(GeocodingService.MAX_RESPONSE_SIZE, 5 * 1024 * 1024)
        self.assertEqual(MessageGeneratorService.MAX_RESPONSE_BYTES, 5 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
