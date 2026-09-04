from dataclasses import dataclass, field
from typing import Any, List, Optional

@dataclass
class Lead:
    """Modelo de lead compatível com o pipeline LeadFinder."""
    nome: str
    categoria: str = "Não informado"
    telefone: str = "⚠️ Não encontrado"
    website: str = "⚠️ Não encontrado"
    instagram: str = "⚠️ Não encontrado"
    facebook: str = "⚠️ Não encontrado"
    email: str = "⚠️ Não encontrado"
    whatsapp: str = "⚠️ Não encontrado"
    endereco: str = "Não informado"
    cidade: str = "Não informado"
    estado: str = "Não informado"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    id_osm: str = "Não informado"
    url_osm: str = "Não informado"
    place_id: Optional[str] = None

    score_final: float = 0
    score_presenca_digital: int = 0
    score_contato: int = 0
    score_oportunidade: int = 0
    score_qualidade: int = 0
    score_proximidade: int = 0
    score_confiabilidade: int = 0
    classificacao_prioridade: str = "⚪ BAIXA PRIORIDADE"
    motivos_positivos: List[str] = field(default_factory=list)
    motivos_negativos: List[str] = field(default_factory=list)
    status_enriquecimento: str = "N/A"
    confianca_enriquecimento: int = 0
    score_version: str = "3.0.0"

    status_website: str = "N/A"
    website_origem: str = "N/A"
    whatsapp_origem: str = "N/A"
    tipo_whatsapp: str = "N/A"
    telefone_origem: str = "N/A"
    email_origem: str = "N/A"
    instagram_origem: str = "N/A"
    facebook_origem: str = "N/A"
    motivo_enriquecimento: str = ""
    estrategias_executadas: str = ""
    historico_estrategias: str = ""
    tempo_processamento_ms: int = 0
    retries_executados: int = 0
    teve_timeout: bool = False
    enriquecido_via_playwright: bool = False
    ultima_verificacao: str = ""
    id_unico: str = ""

    def __post_init__(self):
        # Compatibilidade com fontes externas que enviem None.
        if not self.nome:
            self.nome = "Empresa sem nome"
        if not self.id_unico:
            self.id_unico = self.id_osm if self.id_osm else self.nome
