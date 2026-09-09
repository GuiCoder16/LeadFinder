import pytest
from unittest.mock import patch
from models.lead import Lead
from services.commercial_enrichment import CommercialEnrichmentService

@pytest.fixture
def mock_safe_request():
    """
    Mock isolado da camada HTTP. 
    Intercepta apenas as requisições externas para devolver HTML controlado 
    ou simular falhas, evitando tráfego de rede e garantindo determinismo.
    """
    with patch("services.commercial_enrichment.CommercialEnrichmentService._safe_request") as mock_req:
        yield mock_req

@pytest.fixture
def disable_playwright():
    """
    Desabilita a inicialização do Playwright para que o teste foque 
    apenas na extração estática da SERP, não gastando tempo abrindo browsers reais.
    """
    with patch("services.commercial_enrichment.HAS_PLAYWRIGHT", False):
        yield

def test_pipeline_rejeita_w3c_dtd_e_aceita_website_valido(mock_safe_request, disable_playwright):
    """
    Simula uma resposta HTML real da SERP contendo:
    1. Uma URL W3C estrutural (que deve ser ignorada com 'continue').
    2. Uma URL comercial válida (que deve ser aceita, acionando o 'break').
    3. Uma terceira URL válida (que não deve ser atingida, pois o loop quebrou).
    """
    
    # SETUP: Um lead com website ausente para acionar o motor de busca
    lead = Lead(
        nome="Marcenaria Guarulhos",
        cidade="Guarulhos",
        estado="SP",
        website="⚠️ Não encontrado",
        telefone="⚠️ Não encontrado" # Necessidades = True
    )

    # RESPOSTA SIMULADA DA SERP (DuckDuckGo)
    html_serp_simulado = """
    <html><body>
        <div class="result">
            <!-- W3C DTD: O regex vai capturar, mas o validador deve rejeitar -->
            <a href="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">W3C Spec</a>
        </div>
        <div class="result">
            <!-- Site correto: Deve ser aceito e parar a busca -->
            <a href="https://www.marcenariaguarulhos.com.br">Marcenaria Oficial</a>
        </div>
        <div class="result">
            <!-- Nunca deve ser alcançado devido ao break -->
            <a href="https://www.naodevechegaraqui.com.br">Concorrente</a>
        </div>
    </body></html>
    """

    class DummyResponse:
        def __init__(self, text):
            self.text = text
            self.content = text.encode('utf-8')
            self.status_code = 200

    def mock_request_side_effect(url, *args, **kwargs):
        if "duckduckgo.com" in url:
            # Entrega o HTML da SERP forjado para a extração do regex
            return (DummyResponse(html_serp_simulado), "VALIDA", "HTTP 200", 0, False)
        else:
            # Simula que o site final falhou ao ser aberto para não triggar extração profunda
            return (None, "BLOQUEIO", "Navegação profunda cancelada no teste", 0, False)

    mock_safe_request.side_effect = mock_request_side_effect

    # EXECUÇÃO: Roda o pipeline REAL de enriquecimento
    leads_processados, metricas = CommercialEnrichmentService.enriquecer(
        leads=[lead],
        limite_opcao="Todos",
        debug_mode=True
    )
    
    lead_resultado = leads_processados[0]

    # VALIDAÇÕES (Asserts)
    # 1. A URL do W3C foi ignorada e o site legítimo foi atribuído.
    assert lead_resultado.website == "https://www.marcenariaguarulhos.com.br", "O DTD do W3C foi atribuído erroneamente ou o site válido foi ignorado."
    
    # 2. Confirma que a origem da atribuição veio do pipeline da SERP.
    assert lead_resultado.website_origem == "SERP", "O status do website não foi atualizado pela extração da SERP."
    assert "Website localizado" in lead_resultado.status_website or "Site visitado" in lead_resultado.status_website