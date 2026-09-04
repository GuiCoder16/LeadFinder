import requests
import json
import time

class OverpassService:
    BASE_URL = "https://overpass-api.de/api/interpreter"
    
    # Restrições de Produção / Sprint 7 (Operational Security)
    TIMEOUT_SECONDS = 30
    MAX_RETRIES = 3
    MAX_RESPONSE_SIZE = 5 * 1024 * 1024 # 5MB Hard Limit
    
    CATEGORIAS = {
        "Barbearia": "node['shop'='hairdresser']",
        "Salão de beleza": "node['shop'='beauty']",
        "Oficina mecânica": "node['shop'='car_repair']",
        "Restaurante": "node['amenity'='restaurant']",
        "Pizzaria": "node['amenity'='restaurant']['cuisine'='pizza']",
        "Academia": "node['leisure'='fitness_centre']",
        "Pet shop": "node['shop'='pet']",
        "Marcenaria": "node['craft'='carpenter']",
        "Vidraçaria": "node['craft'='glazier']"
    }

    @staticmethod
    def get_categorias():
        return list(OverpassService.CATEGORIAS.keys())

    @staticmethod
    def _safe_post_request(query: str, callback=None) -> list:
        """Executa a request com limites estritos de Memória, Timeout e Retries."""
        headers = {
            "User-Agent": "LeadFinder/2.0 (MVP Comercial - SafeMode)"
        }
        
        for tentativa in range(1, OverpassService.MAX_RETRIES + 1):
            try:
                if callback: callback(f"Conectando ao Overpass (Tentativa {tentativa}/{OverpassService.MAX_RETRIES})...")
                
                response = requests.post(
                    OverpassService.BASE_URL, 
                    data=query, 
                    headers=headers, 
                    timeout=OverpassService.TIMEOUT_SECONDS,
                    allow_redirects=False,
                    stream=True
                )
                response.raise_for_status()
                
                # Sprint 7: Bounded Efficient Buffering (Prevenção OOM e Response Bomb)
                chunks = []
                total_size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    total_size += len(chunk)
                    if total_size > OverpassService.MAX_RESPONSE_SIZE:
                        if callback: callback("[!] Resposta excedeu 5MB. Proteção de memória ativada.")
                        return [] # Fail closed imediato
                    chunks.append(chunk)
                        
                raw_data = b"".join(chunks)
                dados = json.loads(raw_data)
                return dados.get("elements", [])
                
            except requests.exceptions.Timeout:
                if tentativa == OverpassService.MAX_RETRIES: return []
            except requests.exceptions.RequestException:
                if tentativa == OverpassService.MAX_RETRIES: return []
            except json.JSONDecodeError:
                return []
            
            time.sleep(1.5 * tentativa) # Backoff
            
        return []

    @staticmethod
    def buscar_empresas_por_coordenadas(categoria: str, lat: float, lon: float, quantidade: int = 50, callback=None) -> list:
        if categoria not in OverpassService.CATEGORIAS:
            return []

        # Clamp quantity against input bypass
        try: safe_qtd = max(10, min(500, int(quantidade)))
        except (ValueError, TypeError): safe_qtd = 50

        tag_query = OverpassService.CATEGORIAS[categoria]
        
        # Boundary limit around coordinates (~10km box)
        query = f"""
        [out:json][timeout:25];
        (
          {tag_query}(around:10000, {lat}, {lon});
        );
        out center {safe_qtd};
        """
        
        return OverpassService._safe_post_request(query, callback)