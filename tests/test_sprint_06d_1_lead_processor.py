import unittest

from services.lead_processor import LeadProcessor


class TestSprint06D1LeadProcessorDiscoveryQuality(unittest.TestCase):
    def processar(self, dados):
        return LeadProcessor.processar_osm(dados, "Barbearia", "Sao Paulo", "SP")

    def test_nome_valido_e_preservado_com_whitespace_minimo(self):
        leads = self.processar([
            {"id": 123, "type": "node", "tags": {"name": "  O Carpinteiro  "}},
        ])

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].nome, "O Carpinteiro")
        self.assertEqual(leads[0].id_osm, "123")

    def test_nomes_ausentes_vazios_whitespace_e_sentinelas_sao_ignorados(self):
        dados = [
            {"id": 1, "tags": {}},
            {"id": 2, "tags": {"name": ""}},
            {"id": 3, "tags": {"name": "   "}},
            {"id": 4, "tags": {"name": None}},
            {"id": 5, "tags": {"name": "None"}},
            {"id": 6, "tags": {"name": "null"}},
            {"id": 7, "tags": {"name": "nan"}},
        ]

        self.assertEqual(self.processar(dados), [])

    def test_nomes_iguais_com_ids_osm_diferentes_permanecem_sem_hash(self):
        dados = [
            {"id": 100, "type": "node", "lat": 1.0, "lon": 1.0, "tags": {"name": "Barbearia Central"}},
            {"id": 200, "type": "node", "lat": 2.0, "lon": 2.0, "tags": {"name": "Barbearia Central"}},
        ]

        leads = self.processar(dados)

        self.assertEqual(len(leads), 2)
        self.assertEqual([lead.nome for lead in leads], ["Barbearia Central", "Barbearia Central"])
        self.assertEqual([lead.id_osm for lead in leads], ["100", "200"])
        self.assertNotIn("#", leads[0].nome)
        self.assertNotIn("#", leads[1].nome)
        self.assertNotEqual(leads[0].id_unico, leads[1].id_unico)

    def test_mesmo_id_osm_continua_sendo_deduplicado(self):
        dados = [
            {"id": 100, "type": "node", "tags": {"name": "Barbearia Central"}},
            {"id": 100, "type": "node", "tags": {"name": "Barbearia Central Filial"}},
        ]

        leads = self.processar(dados)

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].nome, "Barbearia Central")
        self.assertEqual(leads[0].id_osm, "100")


if __name__ == "__main__":
    unittest.main()
