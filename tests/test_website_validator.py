from utils.validators import e_website_comercial_valido

def test_validacao_website_comercial():
    # A) Websites comerciais legítimos (devem passar)
    assert e_website_comercial_valido("https://www.marcenariaguarulhos.com.br") is True
    assert e_website_comercial_valido("http://barbeariasilva.com") is True
    assert e_website_comercial_valido("https://loja.com.br/contato") is True

    # B) DTD do W3C (deve ser rejeitado)
    assert e_website_comercial_valido("http://www.w3.org/tr/xhtml1/dtd/xhtml1-transitional.dtd") is False
    assert e_website_comercial_valido("http://www.w3.org/TR/html4/loose.dtd") is False

    # C) URLs de documentação / schema (devem ser rejeitadas)
    assert e_website_comercial_valido("http://schema.org/LocalBusiness") is False
    assert e_website_comercial_valido("http://xmlns.com/foaf/0.1/") is False

    # D) Recursos estáticos (devem ser rejeitados)
    assert e_website_comercial_valido("https://empresa.com.br/logo.png") is False
    assert e_website_comercial_valido("https://empresa.com.br/estilo.css") is False
    assert e_website_comercial_valido("https://empresa.com.br/catalogo.pdf") is False

    # E) URLs malformadas ou sem protocolo (devem ser rejeitadas)
    assert e_website_comercial_valido("not_a_url") is False
    assert e_website_comercial_valido("ftp://servidor.com/arquivo") is False
    assert e_website_comercial_valido(None) is False

    print("✅ Todos os testes comportamentais do Patch 06A passaram com sucesso!")

if __name__ == "__main__":
    test_validacao_website_comercial()