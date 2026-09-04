import os
import math
import googlemaps
from dotenv import load_dotenv
from models.lead import Lead

load_dotenv()


class GooglePlacesService:
    MAX_RESULTS = 100

    def __init__(self):
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY_MISSING")
        self.client = googlemaps.Client(key=api_key)

    @staticmethod
    def _safe_text(value, default="Não informado", limit=500):
        if value is None:
            return default
        try:
            text = str(value).strip()
        except Exception:
            return default
        return text[:limit] if text else default

    def buscar_empresas(self, segmento, localizacao, quantidade=20):
        try:
            quantidade = int(float(quantidade))
            if not math.isfinite(float(quantidade)):
                quantidade = 20
        except (TypeError, ValueError, OverflowError):
            quantidade = 20
        quantidade = max(1, min(quantidade, self.MAX_RESULTS))

        segmento = self._safe_text(segmento, "empresa", 100)
        localizacao = self._safe_text(localizacao, "Brasil", 150)
        consulta = f"{segmento} em {localizacao}"

        try:
            resposta = self.client.places(query=consulta, language="pt-BR")
        except Exception:
            return []

        resultados = resposta.get("results", []) if isinstance(resposta, dict) else []
        if not isinstance(resultados, list):
            return []

        leads = []
        for empresa in resultados[:quantidade]:
            if not isinstance(empresa, dict):
                continue

            place_id = empresa.get("place_id")
            detalhes = {}
            if isinstance(place_id, str) and place_id:
                try:
                    detalhes_resposta = self.client.place(
                        place_id=place_id,
                        fields=[
                            "name", "formatted_address",
                            "formatted_phone_number", "website", "types"
                        ],
                        language="pt-BR",
                    )
                    if isinstance(detalhes_resposta, dict):
                        detalhes = detalhes_resposta.get("result", {}) or {}
                except Exception:
                    # Não vaza PII/argumentos da exceção para stdout.
                    detalhes = {}

            nome = self._safe_text(detalhes.get("name", empresa.get("name")), "Nome desconhecido")
            endereco = self._safe_text(
                detalhes.get("formatted_address", empresa.get("formatted_address")),
                "Não informado",
            )
            telefone = self._safe_text(
                detalhes.get("formatted_phone_number"),
                "⚠️ Não encontrado",
            )
            website = self._safe_text(
                detalhes.get("website"),
                "⚠️ Não encontrado",
            )
            tipos = detalhes.get("types", empresa.get("types", []))
            if not isinstance(tipos, list):
                tipos = []
            categoria = self._safe_text(tipos[0] if tipos else segmento, segmento, 100)

            try:
                lead = Lead(
                    nome=nome,
                    categoria=categoria,
                    endereco=endereco,
                    telefone=telefone,
                    website=website,
                    place_id=place_id,
                )
                leads.append(lead)
            except (TypeError, ValueError):
                continue

        return leads
