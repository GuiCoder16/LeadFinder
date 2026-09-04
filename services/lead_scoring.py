import math


class LeadScoringService:
    VERSION = "3.0.1"

    PESOS = {
        "PRESENCA_DIGITAL": 15,
        "CANAIS_CONTATO": 25,
        "OPORTUNIDADE": 30,
        "QUALIDADE_DADOS": 10,
        "PROXIMIDADE": 5,
        "CONFIABILIDADE": 15,
    }

    @classmethod
    def validar_pesos(cls) -> bool:
        return sum(cls.PESOS.values()) == 100

    @staticmethod
    def _is_valid(valor) -> bool:
        if valor is None or isinstance(valor, (bool, list, dict, set, tuple)):
            return False
        try:
            if isinstance(valor, float) and not math.isfinite(valor):
                return False
            value = str(valor).strip().lower()
            return value not in {
                "", "não informado", "nao informado", "none",
                "null", "nan", "undefined", "n/a", "⚠️ não encontrado",
            }
        except Exception:
            return False

    @staticmethod
    def _safe_log(msg, p_log):
        if p_log is None:
            return
        try:
            if isinstance(msg, BaseException):
                p_log(f"[SCORING EXCEPTION] {msg.__class__.__name__}")
            else:
                # Logs de scoring nunca recebem objetos arbitrariamente grandes.
                p_log(str(msg)[:5000].replace("\n", "\\n").replace("\r", "\\r"))
        except Exception:
            pass

    @staticmethod
    def _clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> int:
        try:
            value = float(value)
            if not math.isfinite(value):
                return int(min_val)
            return max(int(min_val), min(int(max_val), int(value)))
        except (ValueError, TypeError, OverflowError):
            return int(min_val)

    @staticmethod
    def _safe_attr(obj, name, default=None):
        try:
            return getattr(obj, name, default)
        except Exception:
            return default

    @classmethod
    def avaliar_lead(cls, lead, debug_mode: bool = False, p_log=None):
        if lead is None or isinstance(lead, (str, int, float, bool, list, dict, set, tuple)):
            cls._safe_log("[SCORING] Objeto inválido rejeitado.", p_log)
            return None

        nome = cls._safe_attr(lead, "nome", "Desconhecido")
        website = cls._safe_attr(lead, "website", "Não informado")
        instagram = cls._safe_attr(lead, "instagram", "Não informado")
        facebook = cls._safe_attr(lead, "facebook", "Não informado")
        telefone = cls._safe_attr(lead, "telefone", "Não informado")
        whatsapp = cls._safe_attr(lead, "whatsapp", "Não informado")
        email = cls._safe_attr(lead, "email", "Não informado")
        endereco = cls._safe_attr(lead, "endereco", "Não informado")
        cidade = cls._safe_attr(lead, "cidade", "Não informado")
        estado = cls._safe_attr(lead, "estado", "Não informado")
        latitude = cls._safe_attr(lead, "latitude", None)
        longitude = cls._safe_attr(lead, "longitude", None)
        status_enriquecimento = cls._safe_attr(lead, "status_enriquecimento", "N/A")
        confianca_enriquecimento = cls._safe_attr(lead, "confianca_enriquecimento", 0)

        motivos_positivos = []
        motivos_negativos = []

        try:
            score_presenca = (
                (34 if cls._is_valid(website) else 0)
                + (33 if cls._is_valid(instagram) else 0)
                + (33 if cls._is_valid(facebook) else 0)
            )
            score_presenca = cls._clamp(score_presenca)

            score_contato = 0
            if cls._is_valid(telefone):
                score_contato += 30
                motivos_positivos.append("Telefone disponível")
            if cls._is_valid(whatsapp):
                score_contato += 40
                motivos_positivos.append("WhatsApp disponível")
            if cls._is_valid(email):
                score_contato += 30
                motivos_positivos.append("E-mail disponível")
            if score_contato == 0:
                motivos_negativos.append("Nenhum canal de contato direto")
            score_contato = cls._clamp(score_contato)

            has_website = cls._is_valid(website)
            has_social = cls._is_valid(instagram) or cls._is_valid(facebook)
            score_oportunidade = 0
            if not has_website:
                score_oportunidade += 60
                motivos_positivos.append("Oportunidade: Não possui website profissional")
            else:
                motivos_negativos.append("Já possui website estruturado")
            if not has_social:
                score_oportunidade += 40
                motivos_positivos.append("Oportunidade: Baixa presença em redes sociais")
            score_oportunidade = cls._clamp(score_oportunidade)

            score_qualidade = sum([
                25 if cls._is_valid(nome) else 0,
                25 if cls._is_valid(endereco) else 0,
                25 if cls._is_valid(cidade) else 0,
                25 if cls._is_valid(estado) else 0,
            ])
            score_qualidade = cls._clamp(score_qualidade)

            score_proximidade = 0
            lat_ok = cls._is_valid(latitude)
            lon_ok = cls._is_valid(longitude)
            if lat_ok and lon_ok:
                try:
                    if math.isfinite(float(latitude)) and math.isfinite(float(longitude)):
                        score_proximidade = 100
                        motivos_positivos.append("Localização mapeada no GPS")
                except (ValueError, TypeError, OverflowError):
                    pass
            if score_proximidade == 0:
                motivos_negativos.append("Sem coordenadas geográficas exatas")
            score_proximidade = cls._clamp(score_proximidade)

            safe_status = str(status_enriquecimento).strip().lower() if cls._is_valid(status_enriquecimento) else ""
            score_confiabilidade = 0
            if safe_status in {"sucesso", "enriquecido", "validado", "📈 enriquecido", "✅ novos dados (serp)"}:
                score_confiabilidade += 50
                motivos_positivos.append("Identidade comercial validada")

            try:
                conf_float = float(confianca_enriquecimento)
                safe_confianca = int(conf_float) if math.isfinite(conf_float) else 0
            except (ValueError, TypeError, OverflowError):
                safe_confianca = 0

            if safe_confianca >= 6:
                score_confiabilidade += 50
            elif safe_confianca > 0:
                score_confiabilidade += 20
                motivos_negativos.append("Validação comercial parcial/incompleta")
            score_confiabilidade = cls._clamp(score_confiabilidade)

            score_final = (
                score_presenca * cls.PESOS["PRESENCA_DIGITAL"]
                + score_contato * cls.PESOS["CANAIS_CONTATO"]
                + score_oportunidade * cls.PESOS["OPORTUNIDADE"]
                + score_qualidade * cls.PESOS["QUALIDADE_DADOS"]
                + score_proximidade * cls.PESOS["PROXIMIDADE"]
                + score_confiabilidade * cls.PESOS["CONFIABILIDADE"]
            ) / 100.0
            score_final = max(0, min(100, float(score_final))) if math.isfinite(score_final) else 0

            if score_final >= 80:
                classificacao = "🔥 PRIORIDADE MÁXIMA"
            elif score_final >= 60:
                classificacao = "🟢 ALTA PRIORIDADE"
            elif score_final >= 30:
                classificacao = "🟡 MÉDIA PRIORIDADE"
            else:
                classificacao = "⚪ BAIXA PRIORIDADE"

            for attr, value in {
                "score_presenca_digital": score_presenca,
                "score_contato": score_contato,
                "score_oportunidade": score_oportunidade,
                "score_qualidade": score_qualidade,
                "score_proximidade": score_proximidade,
                "score_confiabilidade": score_confiabilidade,
                "motivos_positivos": motivos_positivos[:50],
                "motivos_negativos": motivos_negativos[:50],
                "score_final": score_final,
                "classificacao_prioridade": classificacao,
                "score_version": cls.VERSION,
            }.items():
                setattr(lead, attr, value)

            if debug_mode:
                cls._safe_log(
                    f"[SCORING] {str(nome)[:100]} -> Score: {score_final:.0f} | Classe: {classificacao}",
                    p_log,
                )
            return lead

        except Exception as e:
            cls._safe_log(e, p_log)
            return lead

    @classmethod
    def avaliar_lote(cls, leads: list, debug_mode: bool = False, p_log=None) -> list:
        if not isinstance(leads, list):
            cls._safe_log("[SCORING ERROR] Entrada do lote não é uma lista.", p_log)
            return []
        if not leads or not cls.validar_pesos():
            return []

        resultados = []
        for obj_lead in leads:
            try:
                resultado = cls.avaliar_lead(obj_lead, debug_mode=debug_mode, p_log=p_log)
                if resultado is not None:
                    resultados.append(resultado)
            except Exception as e:
                cls._safe_log(e, p_log)
        return resultados
