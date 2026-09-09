# tests/test_commercial_enrichment_regression.py
import pytest
from utils.validators import e_website_comercial_valido

def simular_extracao_pipeline(html_content):
    import re
    # Simula a regex descrita na auditoria para encontrar todas as URLs
    urls_candidatas = re.findall(r'https?://[^\s<">]+', html_content)
    
    # Aplica o validador para encontrar a primeira URL comercialmente válida
    for url in urls_candidatas:
        if e_website_comercial_valido(url):
            return url
            
    return "⚠️ Não encontrado"

def test_rejeita_w3c_e_aceita_comercial():
    html_misto = """
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html>
    <body>
        <a href="https://www.marcenariaguarulhos.com.br">Site Oficial</a>
    </body>
    </html>
    """
    resultado = simular_extracao_pipeline(html_misto)
    assert resultado == "https://www.marcenariaguarulhos.com.br"
    assert resultado != "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"

def test_somente_w3c_retorna_fallback():
    html_vazio = """
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html><body>Empresa sem site comercial</body></html>
    """
    resultado = simular_extracao_pipeline(html_vazio)
    assert resultado == "⚠️ Não encontrado"