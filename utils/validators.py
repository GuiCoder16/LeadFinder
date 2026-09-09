import re
from urllib.parse import urlparse

def e_website_comercial_valido(url: str) -> bool:
    """
    Valida se uma URL representa um website comercial legítimo.
    Rejeita DTDs, esquemas XML, recursos estáticos e especificações técnicas.
    """
    if not url or not isinstance(url, str):
        return False
    
    clean_url = url.strip().lower()
    
    # 1. Exige protocolo HTTP ou HTTPS
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        return False

    try:
        parsed = urlparse(clean_url)
        netloc = parsed.netloc
        path = parsed.path
        
        if not netloc:
            return False

        # 2. Rejeita domínios de padronização, esquemas XML e namespaces
        dominios_estruturais = {
            "w3.org", "www.w3.org", 
            "schema.org", "www.schema.org", 
            "xmlns.com", "xml.org"
        }
        if netloc in dominios_estruturais or any(netloc.endswith("." + d) for d in dominios_estruturais):
            return False

        # 3. Rejeita caminhos de DTDs, especificações XHTML ou esquemas
        caminho_completo = f"{parsed.path}?{parsed.query}"
        if any(p in caminho_completo for p in ["/dtd/", "/tr/xhtml", "/xml/", "/schema/"]):
            return False

        # 4. Rejeita extensões de arquivos estáticos e recursos não navegáveis
        extensoes_invalidas = (
            ".dtd", ".xml", ".xsd", ".pdf", ".jpg", ".jpeg", 
            ".png", ".gif", ".svg", ".css", ".js", ".zip", ".ico"
        )
        if any(path.endswith(ext) for ext in extensoes_invalidas):
            return False

        # 5. Exige estrutura básica de hostname comercial (presença de TLD)
        if "." not in netloc:
            return False

        return True

    except Exception:
        return False