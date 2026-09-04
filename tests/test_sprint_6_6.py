import unittest
import requests
from unittest.mock import patch, MagicMock
from services.overpass import OverpassService

class TestSprint66ProductionSecurity(unittest.TestCase):

    @patch("requests.Session.post")
    def test_b_external_url_cannot_be_controlled(self, mock_post):
        """Impede que manipulação de entradas redirecione a URL fixa do serviço (SSRF)."""
        OverpassService.buscar_empresas_por_coordenadas("restaurante", -23.5, -46.6, 10)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://overpass-api.de/api/interpreter")
        self.assertFalse(kwargs.get("allow_redirects", True))

    @patch("requests.Session.post")
    def test_e_large_collection_resource_limit(self, mock_post):
        """Garante que respostas acima de 5MB sejam rejeitadas antes de estourar a memória (JSON Bomb)."""
        mock_response = MagicMock()
        mock_response.content = b"x" * (6 * 1024 * 1024)  # 6MB
        mock_post.return_value = mock_response

        resultados = OverpassService.buscar_empresas_por_coordenadas("restaurante", -23.5, -46.6, 10)
        self.assertEqual(len(resultados), 0)

if __name__ == '__main__':
    unittest.main()