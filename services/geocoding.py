import requests
import time
import json
import urllib.parse

class GeocodingService:
    BASE_URL = "https://nominatim.openstreetmap.org/search"
    
    # Restrições de Produção / Sprint 7
    TIMEOUT_SECONDS = 15
    MAX_RETRIES = 3
    MAX_RESPONSE_SIZE = 5 * 1024 * 1024 # 5MB Hard Limit
    
    @staticmethod
    def buscar_coordenadas(cidade: str, estado: str) -> tuple:
        if not isinstance(cidade, str) or not isinstance(estado, str):
            return None, None
            
        clean_cidade = cidade.strip()
        clean_estado = estado.strip()
        if not clean_cidade or not clean_estado:
            return None, None
            
        query = f"{clean_cidade}, {clean_estado}, Brazil"
        params = {
            "q": query,
            "format": "json",
            "limit": 1
        }
        
        headers = {
            "User-Agent": "LeadFinder/2.0 (MVP Comercial - Geocoding Safe)"
        }
        
        for tentativa in range(1, GeocodingService.MAX_RETRIES + 1):
            try:
                response = requests.get(
                    GeocodingService.BASE_URL, 
                    params=params, 
                    headers=headers, 
                    timeout=GeocodingService.TIMEOUT_SECONDS,
                    allow_redirects=False,
                    stream=True
                )
                response.raise_for_status()
                
                # Sprint 7: Bounded Efficient Buffering (Prevenção OOM)
                chunks = []
                total_size = 0
                for chunk in response.iter_content(chunk_size=4096):
                    total_size += len(chunk)
                    if total_size > GeocodingService.MAX_RESPONSE_SIZE:
                        return None, None # Fail gracefully (Resource Limit excedido)
                    chunks.append(chunk)
                        
                raw_data = b"".join(chunks)
                dados = json.loads(raw_data)
                
                if dados and isinstance(dados, list) and len(dados) > 0:
                    try:
                        lat = float(dados[0].get("lat", 0))
                        lon = float(dados[0].get("lon", 0))
                        return lat, lon
                    except (ValueError, TypeError):
                        pass
                return None, None
                
            except requests.exceptions.Timeout:
                if tentativa == GeocodingService.MAX_RETRIES: return None, None
            except requests.exceptions.RequestException:
                if tentativa == GeocodingService.MAX_RETRIES: return None, None
            except json.JSONDecodeError:
                return None, None
                
            time.sleep(1) # Linear backoff
            
        return None, None