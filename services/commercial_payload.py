import copy
import json
from models.lead import Lead


class CommercialPayloadService:
    MAX_PAYLOAD_BYTES = 4000
    MAX_LIST_ITEMS = 25
    MAX_TEXT_FIELD = 500

    @staticmethod
    def _is_valid(valor) -> bool:
        if valor is None or isinstance(valor, (dict, list, set, tuple, bool)):
            return False
        try:
            text = str(valor).strip()
            return bool(text) and text.lower() not in {
                "none", "null", "n/a", "nan", "undefined",
                "não informado", "nao informado", "⚠️ não encontrado",
            } and "❌" not in text
        except Exception:
            return False

    @staticmethod
    def _limpar_valor(valor):
        if not CommercialPayloadService._is_valid(valor):
            return None
        return str(valor).strip()[:CommercialPayloadService.MAX_TEXT_FIELD]

    @staticmethod
    def _safe_attr(lead, name, default=None):
        try:
            return getattr(lead, name, default)
        except Exception:
            return default

    @staticmethod
    def _determinar_intencao(lead: Lead) -> str:
        try:
            score = float(CommercialPayloadService._safe_attr(lead, "score_final", 0) or 0)
        except (TypeError, ValueError):
            score = 0

        classificacao = CommercialPayloadService._safe_attr(
            lead, "classificacao_prioridade", "⚪ BAIXA PRIORIDADE"
        )
        website = CommercialPayloadService._safe_attr(lead, "website")
        whatsapp = CommercialPayloadService._safe_attr(lead, "whatsapp")
        telefone = CommercialPayloadService._safe_attr(lead, "telefone")
        instagram = CommercialPayloadService._safe_attr(lead, "instagram")
        facebook = CommercialPayloadService._safe_attr(lead, "facebook")

        has_site = CommercialPayloadService._is_valid(website)
        has_wa = CommercialPayloadService._is_valid(whatsapp)
        has_phone = CommercialPayloadService._is_valid(telefone)
        has_ig = CommercialPayloadService._is_valid(instagram)
        has_fb = CommercialPayloadService._is_valid(facebook)

        if classificacao == "⚪ BAIXA PRIORIDADE" or score < 30:
            return "BAIXA_OPORTUNIDADE"
        if not has_site and (has_wa or has_ig or has_phone):
            return "CRIACAO_WEBSITE"
        if has_site and has_wa and has_ig and has_fb:
            return "PRESENCA_DIGITAL_COMPLETA"
        if has_site and (not has_wa or not has_ig or not has_fb):
            return "MELHORIA_PRESENCA_DIGITAL"
        return "BAIXA_OPORTUNIDADE"

    @staticmethod
    def _gerar_contexto_texto(lead: Lead, intencao: str) -> str:
        categoria = CommercialPayloadService._limpar_valor(
            CommercialPayloadService._safe_attr(lead, "categoria")
        ) or "seu segmento"
        cidade = CommercialPayloadService._limpar_valor(
            CommercialPayloadService._safe_attr(lead, "cidade")
        ) or "sua região"
        estado = CommercialPayloadService._limpar_valor(
            CommercialPayloadService._safe_attr(lead, "estado")
        ) or ""

        contatos = []
        if CommercialPayloadService._is_valid(CommercialPayloadService._safe_attr(lead, "whatsapp")):
            contatos.append("WhatsApp confirmado")
        elif CommercialPayloadService._is_valid(CommercialPayloadService._safe_attr(lead, "telefone")):
            contatos.append("telefone disponível")
        if CommercialPayloadService._is_valid(CommercialPayloadService._safe_attr(lead, "email")):
            contatos.append("e-mail listado")

        texto = f"Empresa do segmento {categoria} localizada em {cidade}"
        if estado:
            texto += f" - {estado}"
        texto += ". "
        texto += ("Possui " + " e ".join(contatos) + ". ") if contatos else \
                 "Não possui contatos diretos validados de forma pública. "

        if intencao == "CRIACAO_WEBSITE":
            texto += "Não foi identificado website próprio. Alta oportunidade para criação de presença digital estruturada."
        elif intencao == "MELHORIA_PRESENCA_DIGITAL":
            texto += "Possui website, mas a presença digital e conexões sociais estão incompletas ou desconectadas."
        elif intencao == "PRESENCA_DIGITAL_COMPLETA":
            texto += "Possui website e presença ativa nas redes sociais. A abordagem comercial pode focar em automação, tráfego ou performance."
        else:
            texto += "Baixa relevância comercial devido à escassez de dados para validação."
        return texto[:1200].strip()

    @staticmethod
    def _derivar_oportunidades(lead: Lead, intencao: str) -> list:
        ops = []
        if intencao == "CRIACAO_WEBSITE":
            ops.append("Oferecer Landing Page ou Site Institucional.")
        elif intencao == "MELHORIA_PRESENCA_DIGITAL":
            if not CommercialPayloadService._is_valid(CommercialPayloadService._safe_attr(lead, "instagram")):
                ops.append("Integração ou criação de canais de Redes Sociais.")
            if not CommercialPayloadService._is_valid(CommercialPayloadService._safe_attr(lead, "whatsapp")):
                ops.append("Melhorar o canal de contato via WhatsApp.")
        elif intencao == "PRESENCA_DIGITAL_COMPLETA":
            ops.append("Oferecer serviços de gestão de tráfego, SEO avançado ou chatbot para WhatsApp.")

        motivos = CommercialPayloadService._safe_attr(lead, "motivos_positivos", [])
        if isinstance(motivos, list):
            for motivo in motivos[:CommercialPayloadService.MAX_LIST_ITEMS]:
                if isinstance(motivo, str) and "oportunidade" in motivo.lower() and motivo not in ops:
                    ops.append(motivo[:250])
        return ops[:CommercialPayloadService.MAX_LIST_ITEMS]

    @classmethod
    def _build_payload(cls, lead: Lead) -> dict:
        intencao = cls._determinar_intencao(lead)
        return {
            "empresa": {
                "nome": cls._limpar_valor(cls._safe_attr(lead, "nome")),
                "categoria": cls._limpar_valor(cls._safe_attr(lead, "categoria")),
                "cidade": cls._limpar_valor(cls._safe_attr(lead, "cidade")),
                "estado": cls._limpar_valor(cls._safe_attr(lead, "estado")),
            },
            "contato": {
                "whatsapp": cls._limpar_valor(cls._safe_attr(lead, "whatsapp")),
                "telefone": cls._limpar_valor(cls._safe_attr(lead, "telefone")),
                "instagram": cls._limpar_valor(cls._safe_attr(lead, "instagram")),
                "facebook": cls._limpar_valor(cls._safe_attr(lead, "facebook")),
                "email": cls._limpar_valor(cls._safe_attr(lead, "email")),
            },
            "presenca_digital": {
                "website": cls._limpar_valor(cls._safe_attr(lead, "website")),
                "tem_website": cls._is_valid(cls._safe_attr(lead, "website")),
                "tem_instagram": cls._is_valid(cls._safe_attr(lead, "instagram")),
                "tem_facebook": cls._is_valid(cls._safe_attr(lead, "facebook")),
                "tem_whatsapp": cls._is_valid(cls._safe_attr(lead, "whatsapp")),
            },
            "scoring": {
                "score_final": cls._safe_attr(lead, "score_final", 0),
                "prioridade": cls._safe_attr(lead, "classificacao_prioridade", "⚪ BAIXA PRIORIDADE"),
                "oportunidade": cls._safe_attr(lead, "score_oportunidade", 0),
                "canais_contato": cls._safe_attr(lead, "score_contato", 0),
                "presenca_digital": cls._safe_attr(lead, "score_presenca_digital", 0),
                "confiabilidade": cls._safe_attr(lead, "score_confiabilidade", 0),
                "qualidade_dados": cls._safe_attr(lead, "score_qualidade", 0),
                "proximidade": cls._safe_attr(lead, "score_proximidade", 0),
            },
            "contexto_comercial": {
                "intencao": intencao,
                "contexto_texto": cls._gerar_contexto_texto(lead, intencao),
                "motivos_positivos": copy.deepcopy(
                    cls._safe_attr(lead, "motivos_positivos", [])[:cls.MAX_LIST_ITEMS]
                    if isinstance(cls._safe_attr(lead, "motivos_positivos", []), list) else []
                ),
                "oportunidades": cls._derivar_oportunidades(lead, intencao),
            },
        }

    @classmethod
    def _enforce_size_limit(cls, payload: dict) -> tuple[dict, int]:
        """Reduz conteúdo opcional até o JSON ficar dentro do contrato de 4 KB."""
        payload = copy.deepcopy(payload)

        def serialized_size():
            return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        size = serialized_size()
        if size <= cls.MAX_PAYLOAD_BYTES:
            return payload, size

        contexto = payload.get("contexto_comercial", {})
        if isinstance(contexto, dict):
            contexto["motivos_positivos"] = []
            contexto["oportunidades"] = []
            size = serialized_size()

        if size > cls.MAX_PAYLOAD_BYTES and isinstance(contexto, dict):
            contexto["contexto_texto"] = str(contexto.get("contexto_texto", ""))[:400]
            size = serialized_size()

        if size > cls.MAX_PAYLOAD_BYTES:
            empresa = payload.get("empresa", {})
            if isinstance(empresa, dict):
                for key in ("nome", "categoria", "cidade", "estado"):
                    if key in empresa and isinstance(empresa[key], str):
                        empresa[key] = empresa[key][:100]
            contato = payload.get("contato", {})
            if isinstance(contato, dict):
                for key, value in list(contato.items()):
                    if isinstance(value, str):
                        contato[key] = value[:120]
            size = serialized_size()

        # Último fallback: manter um payload contratual mínimo, ainda JSON válido.
        if size > cls.MAX_PAYLOAD_BYTES:
            payload = {
                "empresa": {"nome": cls._limpar_valor(cls._safe_attr(payload.get("_lead", None), "nome")) if False else None},
                "contato": {},
                "presenca_digital": {},
                "scoring": {},
                "contexto_comercial": {
                    "intencao": "BAIXA_OPORTUNIDADE",
                    "contexto_texto": "Payload reduzido por limite de segurança.",
                    "motivos_positivos": [],
                    "oportunidades": [],
                },
            }
            size = serialized_size()
        return payload, size

    @classmethod
    def gerar_payload(cls, lead: Lead) -> tuple:
        if lead is None or isinstance(lead, (dict, list, tuple, set, str, int, float, bool)):
            raise TypeError("Lead inválido para geração de payload.")
        payload = cls._build_payload(lead)
        return cls._enforce_size_limit(payload)

    @classmethod
    def gerar_payloads_lote(cls, leads_rankeados: list, debug_mode: bool = False, p_log=None) -> dict:
        if not isinstance(leads_rankeados, list):
            if p_log:
                p_log("[PAYLOAD ERROR] Entrada não é uma lista válida.")
            return {}

        payloads = {}
        for lead in leads_rankeados:
            if lead is None or isinstance(lead, (dict, list, tuple, set, str, int, float, bool)):
                continue
            nome = cls._safe_attr(lead, "nome")
            if not isinstance(nome, str) or not nome.strip():
                continue
            try:
                payload, size = cls.gerar_payload(lead)
                # Deep copy no limite da camada para impedir referências cruzadas.
                payloads[nome] = {"payload": copy.deepcopy(payload), "size": size}
            except Exception as e:
                if p_log:
                    p_log(f"[PAYLOAD ERROR] Lead rejeitado: {e.__class__.__name__}")
        return payloads
