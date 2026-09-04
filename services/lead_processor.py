import hashlib
import math
from models.lead import Lead


class LeadProcessor:
    """Converte respostas do OSM em objetos Lead sem deixar dados malformados derrubarem o lote."""

    @staticmethod
    def _safe_float(value, default=None):
        try:
            number = float(value)
            if not math.isfinite(number):
                return default
            return number
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_text(value, default="Não informado", max_length=500):
        if value is None:
            return default
        try:
            text = str(value).strip()
        except Exception:
            return default
        if not text or text.lower() in {"none", "null", "nan"}:
            return default
        return text[:max_length]

    @staticmethod
    def processar_osm(dados_brutos: list, categoria: str, cidade: str, estado: str) -> list:
        if not isinstance(dados_brutos, list):
            return []

        leads = []
        ids_processados = set()
        identities = set()
        nomes_vistos = set()

        for elemento in dados_brutos:
            if not isinstance(elemento, dict):
                continue

            tags = elemento.get("tags", {})
            if not isinstance(tags, dict):
                continue

            nome = LeadProcessor._safe_text(tags.get("name"), default="")
            if not nome:
                continue

            raw_id = elemento.get("id")
            id_osm = LeadProcessor._safe_text(
                raw_id,
                default=f"no_id_{len(leads)}",
                max_length=100,
            )
            if id_osm in ids_processados:
                continue
            ids_processados.add(id_osm)

            center = elemento.get("center", {})
            if not isinstance(center, dict):
                center = {}

            lat = LeadProcessor._safe_float(elemento.get("lat", center.get("lat")))
            lon = LeadProcessor._safe_float(elemento.get("lon", center.get("lon")))

            # Identidade determinística independente do nome exibido.
            identity_source = f"{nome}|{lat}|{lon}|{id_osm}".encode("utf-8", errors="replace")
            id_unico = hashlib.sha256(identity_source).hexdigest()

            # Colisão lógica extrema: preserva o nome natural para o primeiro
            # e cria um sufixo somente quando duas identidades realmente colidem.
            nome_exibicao = nome
            if nome in nomes_vistos:
                nome_exibicao = f"{nome} #{id_unico[:10]}"
            if id_unico in identities:
                id_unico = hashlib.sha256(
                    f"{identity_source.decode('utf-8', errors='replace')}|{len(leads)}".encode("utf-8")
                ).hexdigest()
                nome_exibicao = f"{nome} #{id_unico[:10]}"
            identities.add(id_unico)
            nomes_vistos.add(nome)

            rua = LeadProcessor._safe_text(tags.get("addr:street"), default="")
            numero = LeadProcessor._safe_text(tags.get("addr:housenumber"), default="")
            endereco = f"{rua}, {numero}".strip(" ,") if rua else "Não informado"

            telefone = LeadProcessor._safe_text(
                tags.get("contact:phone", tags.get("phone")),
                default="⚠️ Não encontrado",
            )
            website = LeadProcessor._safe_text(
                tags.get("contact:website", tags.get("website")),
                default="⚠️ Não encontrado",
            )
            instagram = LeadProcessor._safe_text(
                tags.get("contact:instagram"),
                default="⚠️ Não encontrado",
            )
            facebook = LeadProcessor._safe_text(
                tags.get("contact:facebook"),
                default="⚠️ Não encontrado",
            )

            tipo = elemento.get("type")
            url_osm = (
                f"https://www.openstreetmap.org/{str(tipo)}/{id_osm}"
                if tipo in {"node", "way", "relation"} and id_osm
                else "Não informado"
            )

            try:
                lead = Lead(
                    nome=nome_exibicao,
                    categoria=LeadProcessor._safe_text(categoria),
                    telefone=telefone,
                    website=website,
                    instagram=instagram,
                    facebook=facebook,
                    endereco=endereco,
                    cidade=LeadProcessor._safe_text(cidade),
                    estado=LeadProcessor._safe_text(estado, max_length=10).upper(),
                    latitude=lat,
                    longitude=lon,
                    id_osm=id_osm,
                    url_osm=url_osm,
                )
                # Compatível mesmo se o modelo externo ainda não declarar o campo.
                setattr(lead, "id_unico", id_unico)
                leads.append(lead)
            except (TypeError, ValueError, AttributeError):
                # Um registro corrompido não derruba os demais.
                continue

        return leads
