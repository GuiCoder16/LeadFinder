import requests
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def executar_diagnostico():
    print("="*50)
    print("INICIANDO DIAGNÓSTICO DE REDE - LEADFINDER (FASE 2.1)")
    print("="*50)
    
    print("\n[TESTE 1] Nominatim (Geocodificação)")
    url_nominatim = "https://nominatim.openstreetmap.org/search"
    params_nom = {"q": "Guarulhos, SP, Brasil", "format": "json", "limit": 1}
    headers = {"User-Agent": "LeadFinder_MVP/1.0"}
    
    lat, lon = None, None
    t0 = time.time()
    
    try:
        resp = requests.get(url_nominatim, params=params_nom, headers=headers, timeout=15, verify=False)
        print(f"Status HTTP: {resp.status_code}\nTempo: {time.time() - t0:.2f}s")
        if resp.status_code == 200 and (data := resp.json()):
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            print(f"Resultado: SUCESSO - Lat: {lat}, Lon: {lon}")
        else:
            print("Resultado: FALHA")
    except Exception as e:
        print(f"Erro: {e}")

    if not lat or not lon:
        print("\n[AVISO] Abortando testes do Overpass por falta de coordenadas.")
        return

    tags, raio = '["shop"="car_repair"]', 15000
    query = f"[out:json][timeout:25];(node{tags}(around:{raio},{lat},{lon});way{tags}(around:{raio},{lat},{lon});relation{tags}(around:{raio},{lat},{lon}););out center 10;"

    for nome_servidor, url_overpass in [("Principal", "https://overpass-api.de/api/interpreter"), ("Alternativo", "https://overpass.kumi.systems/api/interpreter")]:
        print(f"\n[TESTE] Overpass API - Servidor {nome_servidor}")
        t0 = time.time()
        try:
            resp = requests.post(url_overpass, data={'data': query}, headers=headers, timeout=30, verify=False)
            print(f"Status HTTP: {resp.status_code}\nTempo: {time.time() - t0:.2f}s")
            if resp.status_code == 200:
                print(f"Resultado: SUCESSO - {len(resp.json().get('elements', []))} estabelecimentos.")
            else:
                print("Resultado: FALHA na consulta.")
        except Exception as e:
            print(f"Erro de Conexão: {e}")

if __name__ == "__main__":
    executar_diagnostico()