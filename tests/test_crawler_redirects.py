import pytest
from unittest.mock import patch, ANY
from services.commercial_enrichment import CommercialEnrichmentService

class MockResponse:
    def __init__(self, status_code, headers=None, text="", content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.content = content

@pytest.fixture
def mock_get():
    with patch("services.commercial_enrichment.requests.get") as m:
        yield m

def test_1_301_seguro_200(mock_get):
    mock_get.side_effect = [
        MockResponse(301, {"Location": "https://site.com/novo"}),
        MockResponse(200, text="Sucesso")
    ]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 2
    assert classif == "VALIDA"
    assert resp.status_code == 200

def test_2_302_seguro_200(mock_get):
    mock_get.side_effect = [
        MockResponse(302, {"Location": "https://site.com/novo"}),
        MockResponse(200)
    ]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 2
    assert classif == "VALIDA"

def test_3_303_seguro_200(mock_get):
    mock_get.side_effect = [
        MockResponse(303, {"Location": "https://site.com/novo"}),
        MockResponse(200)
    ]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert classif == "VALIDA"

def test_4_307_seguro_200(mock_get):
    mock_get.side_effect = [
        MockResponse(307, {"Location": "https://site.com/novo"}),
        MockResponse(200)
    ]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert classif == "VALIDA"

def test_5_308_seguro_200(mock_get):
    mock_get.side_effect = [
        MockResponse(308, {"Location": "https://site.com/novo"}),
        MockResponse(200)
    ]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert classif == "VALIDA"

def test_6_redirect_relativo(mock_get):
    mock_get.side_effect = [
        MockResponse(301, {"Location": "/pagina-contato"}),
        MockResponse(200)
    ]
    CommercialEnrichmentService._safe_request("http://site.com")
    mock_get.assert_called_with("http://site.com/pagina-contato", headers=ANY, timeout=ANY, verify=True, allow_redirects=False)

def test_7_redirect_para_localhost(mock_get):
    mock_get.side_effect = [MockResponse(301, {"Location": "http://localhost:8080/"})]
    resp, classif, motivo, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 1 # Segunda chamada bloqueada por _is_safe_public_url
    assert classif == "BLOQUEIO"

def test_8_redirect_para_127_0_0_1(mock_get):
    mock_get.side_effect = [MockResponse(301, {"Location": "http://127.0.0.1/"})]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 1
    assert classif == "BLOQUEIO"

def test_9_redirect_para_ip_privado(mock_get):
    mock_get.side_effect = [MockResponse(301, {"Location": "http://192.168.1.1/"})]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 1
    assert classif == "BLOQUEIO"

def test_10_redirect_para_metadata(mock_get):
    mock_get.side_effect = [MockResponse(301, {"Location": "http://169.254.169.254/latest/meta-data/"})]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 1
    assert classif == "BLOQUEIO"

def test_11_redirect_dominio_externo(mock_get):
    mock_get.side_effect = [MockResponse(301, {"Location": "https://malicioso.com/"})]
    resp, classif, motivo, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 1
    assert classif == "BLOQUEIO"
    assert "fora do trust boundary" in motivo

def test_12_falso_dominio(mock_get):
    mock_get.side_effect = [MockResponse(301, {"Location": "https://site.com.evil.com/"})]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 1
    assert classif == "BLOQUEIO"

def test_13_open_redirect(mock_get):
    mock_get.side_effect = [
        MockResponse(301, {"Location": "https://site.com/redirect"}),
        MockResponse(302, {"Location": "https://malicioso.com"}),
        MockResponse(200) # Nunca deve alcançar
    ]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 2 # Faz a requisição pro redirect interno, mas bloqueia o malicioso
    assert classif == "BLOQUEIO"

def test_14_loop(mock_get):
    mock_get.side_effect = [
        MockResponse(301, {"Location": "https://site.com/b"}),
        MockResponse(301, {"Location": "http://site.com"})
    ]
    resp, classif, motivo, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert classif == "BLOQUEIO"
    assert "Loop de redirecionamento" in motivo  # CORREÇÃO: Ajustado de "Loop detectado" para corresponder à implementação real.

def test_15_limite_3_redirects(mock_get):
    mock_get.side_effect = [
        MockResponse(301, {"Location": "https://site.com/1"}),
        MockResponse(301, {"Location": "https://site.com/2"}),
        MockResponse(301, {"Location": "https://site.com/3"}),
        MockResponse(301, {"Location": "https://site.com/4"}),
        MockResponse(200) # D falha antes de ser chamado
    ]
    resp, classif, motivo, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 4 # Original + 3 redirects, falha antes de pedir o 4º redirecionamento
    assert classif == "BLOQUEIO"
    assert "Limite" in motivo

def test_16_location_ausente(mock_get):
    mock_get.side_effect = [MockResponse(301, {})]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert mock_get.call_count == 1
    assert classif == "BLOQUEIO"

def test_17_http_https_mesmo_hostname(mock_get):
    mock_get.side_effect = [
        MockResponse(301, {"Location": "https://www.site.com/"}),
        MockResponse(200)
    ]
    resp, classif, _, _, _ = CommercialEnrichmentService._safe_request("http://site.com")
    assert classif == "VALIDA"