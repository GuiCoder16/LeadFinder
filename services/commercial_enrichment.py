import requests
import urllib3
import time
import re
import socket
import ipaddress
from datetime import datetime
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from models.lead import Lead

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

class CommercialEnrichmentService:
    _cache_buscas = {}
    _cache_websites = {}
    MAX_CACHE_ENTRIES = 500
    MAX_RESPONSE_SIZE = 5 * 1024 * 1024
    
    _agregadores = [
        'tripadvisor', 'ifood', 'yelp', 'facebook.com', 'instagram.com', 'duckduckgo', 
        'yahoo.com', 'google', 'youtube.com', 'linkedin.com', 'tiktok.com', 'guiamais', 
        'apontador', 'foursquare', 'solutudo', 'jusbrasil', 'reclameaqui', 'wikipedia',
        'wa.me', 'api.whatsapp', 'bing.com', 'linktr.ee'
    ]
    
    _extensoes_ignoradas = ['.pdf', '.zip', '.rar', '.jpg', '.png', '.gif', '.mp4', '.xml', '.json']

    @staticmethod
    def _classificar_resposta(html_text: str, status_code: int) -> tuple:
        text_lower = html_text.lower()
        sinais_fortes_bloqueio = [
            'verify you are human', 'security check to access', 'cloudflare-nginx', 
            'cf-browser-verification', 'please complete the security check',
            'our systems have detected unusual traffic', 'hcaptcha', 'g-recaptcha'
        ]
        if status_code in [403, 401]: return "BLOQUEIO", f"HTTP {status_code}"
        for sinal in sinais_fortes_bloqueio:
            if sinal in text_lower: return "BLOQUEIO", f"Sinal forte: '{sinal}'"
        if status_code == 202: return "INTERMEDIARIA", "HTTP 202"
        if status_code >= 500 or status_code == 429: return "ERRO_TRANSITORIO", f"HTTP {status_code}"
        if status_code == 200: return "VALIDA", "HTTP 200 OK"
        return "DESCONHECIDO", f"HTTP {status_code}"

    @staticmethod
    def _is_safe_public_url(url: str) -> bool:
        try:
            parsed = urlparse(str(url))
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return False
            hostname = parsed.hostname
            if hostname.lower() in {"localhost", "localhost.localdomain"}:
                return False
            try:
                ip = ipaddress.ip_address(hostname)
                return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
            except ValueError:
                pass
            infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
            addresses = {info[4][0] for info in infos}
            if not addresses:
                return False
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return False
            return True
        except (ValueError, TypeError, socket.gaierror, OSError):
            return False

    @staticmethod
    def _safe_request(url: str, method="GET", data=None, p_log=None, timeout=10) -> tuple:
        if not CommercialEnrichmentService._is_safe_public_url(url):
            if p_log:
                p_log("[NETWORK] URL externa rejeitada pela fronteira de segurança.")
            return None, "BLOQUEIO", "URL não permitida", 0, False

        max_retries = 2
        retries_used = 0
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        for tentativa in range(max_retries):
            try:
                if method == "POST":
                    resp = requests.post(url, data=data, headers=headers, timeout=timeout, verify=True, allow_redirects=False)
                else:
                    resp = requests.get(url, headers=headers, timeout=timeout, verify=True, allow_redirects=False)
                
                if len(getattr(resp, "content", b"")) > CommercialEnrichmentService.MAX_RESPONSE_SIZE:
                    if p_log:
                        p_log("[NETWORK] Resposta excedeu o limite de 5MB.")
                    return None, "BLOQUEIO", "Resposta excedeu limite", retries_used, False
                classificacao, motivo = CommercialEnrichmentService._classificar_resposta(resp.text, resp.status_code)
                
                if classificacao == "ERRO_TRANSITORIO" or classificacao == "INTERMEDIARIA":
                    retries_used += 1
                    if p_log: p_log(f"[RETRY] {motivo}. Tentativa {tentativa+1}/{max_retries}. Backoff: {2*(tentativa+1)}s")
                    time.sleep(2 * (tentativa + 1))
                    continue
                
                return resp, classificacao, motivo, retries_used, False
                
            except requests.exceptions.Timeout:
                retries_used += 1
                if p_log: p_log(f"[RETRY] Timeout na tentativa {tentativa+1}/{max_retries}.")
                time.sleep(1.5)
                if tentativa == max_retries - 1: return None, "TIMEOUT", "Timeout esgotado", retries_used, True
            except requests.exceptions.RequestException as e:
                retries_used += 1
                if p_log: p_log("[RETRY] Falha de rede controlada.")
                time.sleep(1.5)
                if tentativa == max_retries - 1: return None, "ERRO", "Falha de rede", retries_used, False
                
        return None, "ERRO", "Tentativas esgotadas", retries_used, False

    @staticmethod
    def validar_identidade_adaptativa(texto: str, lead: Lead) -> tuple:
        confianca = 0
        texto_lower = texto.lower()
        nome_parts = [p for p in lead.nome.lower().split() if len(p) > 2]
        matches_nome = sum(1 for p in nome_parts if p in texto_lower)
        if len(nome_parts) > 0:
            razao = matches_nome / len(nome_parts)
            if razao >= 0.8: confianca += 3
            elif razao >= 0.5: confianca += 1
            
        if confianca == 0: return 0, False, "Nome ausente. Rejeição automática."

        if lead.cidade.lower() in texto_lower: confianca += 2
        if lead.telefone != "⚠️ Não encontrado":
            tel_digits = re.sub(r'\D', '', lead.telefone)
            if len(tel_digits) > 8 and tel_digits[-8:] in texto_lower: confianca += 3
        if lead.categoria.lower() in texto_lower: confianca += 1
            
        limiar = 4 if lead.telefone == "⚠️ Não encontrado" else 6
        return min(confianca, 10), (confianca >= limiar), f"Score {confianca}/10 (Limiar: {limiar})"

    @staticmethod
    def _is_js_dependent(soup: BeautifulSoup, texto_puro: str) -> bool:
        if len(texto_puro) < 400 and soup.find('script'): return True
        if "enable javascript" in texto_puro.lower(): return True
        return False

    @staticmethod
    def _find_internal_links(soup: BeautifulSoup, base_url: str, domain: str) -> list:
        keywords = {
            'contato': ['contato', 'contact', 'fale', 'atendimento'],
            'sobre': ['sobre', 'quem-somos', 'about'],
            'localizacao': ['localizacao', 'endereco', 'onde-estamos']
        }
        found_links = {}
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')): continue
            
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            if any(full_url.lower().endswith(ext) for ext in CommercialEnrichmentService._extensoes_ignoradas): continue
            
            if parsed.netloc == domain and parsed.path != urlparse(base_url).path:
                path_lower = parsed.path.lower()
                for cat, kw_list in keywords.items():
                    if any(kw in path_lower for kw in kw_list) and cat not in found_links:
                        found_links[cat] = full_url
                        break
        
        prioridade = ['contato', 'localizacao', 'sobre']
        return [(found_links[k], k) for k in prioridade if k in found_links]

    @staticmethod
    def _extract_contacts(soup: BeautifulSoup, lead: Lead, page_type: str, source_tag: str, p_log, historico: list, metricas: dict, extraidos_sessao: dict) -> int:
        novos = 0
        
        def normalize_phone(p): return re.sub(r'\D', '', p)
        def normalize_url(u): return u.lower().split('?')[0].rstrip('/')

        if lead.email == "⚠️ Não encontrado":
            email = None
            mailto = soup.find('a', href=re.compile(r'^mailto:'))
            if mailto: email = mailto['href'].replace('mailto:', '').strip().lower()
            else:
                em_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', soup.get_text(separator=' '))
                if em_match: email = em_match.group(0).lower()
            
            if email and email not in extraidos_sessao.get("emails", set()) and not any(x in email for x in ['sentry', 'wix', 'example', 'domain', 'png', 'jpg']):
                lead.email = email
                lead.email_origem = f"Website ({page_type} {source_tag})"
                extraidos_sessao.setdefault("emails", set()).add(email)
                novos += 1
                metricas["emails_encontrados"] += 1
                p_log(f"[EXTRACTION] Email: {lead.email}")
                historico.append(f"[Extração] E-mail em {page_type} ({source_tag}).")

        if lead.whatsapp == "⚠️ Não encontrado":
            wa_a = soup.find('a', href=re.compile(r'(wa\.me|api\.whatsapp\.com/send)'))
            if wa_a:
                wa_match = re.search(r'(\d{10,13})', wa_a['href'])
                if wa_match:
                    num = normalize_phone(wa_match.group(1))
                    if num not in extraidos_sessao.get("phones", set()):
                        lead.whatsapp = f"https://wa.me/{num}"
                        lead.whatsapp_origem = f"Website ({page_type} {source_tag})"
                        lead.tipo_whatsapp = "🟢 Confirmado Web"
                        extraidos_sessao.setdefault("phones", set()).add(num)
                        novos += 1
                        metricas["wa_encontrados"] += 1
                        p_log(f"[EXTRACTION] WhatsApp: {lead.whatsapp}")
                        historico.append(f"[Extração] WhatsApp em {page_type} ({source_tag}).")

        if lead.telefone == "⚠️ Não encontrado":
            tel_a = soup.find('a', href=re.compile(r'^tel:'))
            if tel_a:
                raw_tel = tel_a['href'].replace('tel:', '').strip()
                num = normalize_phone(raw_tel)
                if num and num not in extraidos_sessao.get("phones", set()):
                    lead.telefone = raw_tel
                    lead.telefone_origem = f"Website ({page_type} {source_tag})"
                    extraidos_sessao.setdefault("phones", set()).add(num)
                    novos += 1
                    metricas["tel_encontrados"] += 1
                    p_log(f"[EXTRACTION] Telefone: {lead.telefone}")
                    historico.append(f"[Extração] Telefone em {page_type} ({source_tag}).")

        if lead.instagram == "⚠️ Não encontrado":
            ig_a = soup.find('a', href=re.compile(r'instagram\.com/((?!explore|p/|reel|accounts|direct|stories)[a-zA-Z0-9_.]+)'))
            if ig_a:
                ig_url = normalize_url(ig_a['href'].strip())
                if ig_url not in extraidos_sessao.get("socials", set()):
                    lead.instagram = ig_url
                    lead.instagram_origem = f"Website ({page_type} {source_tag})"
                    extraidos_sessao.setdefault("socials", set()).add(ig_url)
                    novos += 1
                    metricas["ig_encontrados"] += 1
                    p_log(f"[EXTRACTION] Instagram: {lead.instagram}")
                    historico.append(f"[Extração] Instagram em {page_type} ({source_tag}).")
                
        if lead.facebook == "⚠️ Não encontrado":
            fb_a = soup.find('a', href=re.compile(r'facebook\.com/((?!share|plugins|login|sharer|watch)[a-zA-Z0-9_.-]+)'))
            if fb_a:
                fb_url = normalize_url(fb_a['href'].strip())
                if fb_url not in extraidos_sessao.get("socials", set()):
                    lead.facebook = fb_url
                    lead.facebook_origem = f"Website ({page_type} {source_tag})"
                    extraidos_sessao.setdefault("socials", set()).add(fb_url)
                    novos += 1
                    metricas["fb_encontrados"] += 1
                    p_log(f"[EXTRACTION] Facebook: {lead.facebook}")
                    historico.append(f"[Extração] Facebook em {page_type} ({source_tag}).")
                
        if novos > 0: p_log(f"[DEDUP] {novos} contatos únicos verificados e extraídos.")
        return novos

    @staticmethod
    def _visitar_website_profundo(base_url: str, lead: Lead, p_log, historico: list, metricas: dict, browser_context) -> int:
        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc
        if not domain or any(x in domain.lower() for x in CommercialEnrichmentService._agregadores):
            return 0
        if not CommercialEnrichmentService._is_safe_public_url(base_url):
            p_log("[CRAWL] URL rejeitada pela fronteira de segurança.")
            return 0
        if domain in CommercialEnrichmentService._cache_websites:
            p_log("[CACHE] Website já analisado.")
            return 0

        if len(CommercialEnrichmentService._cache_websites) >= CommercialEnrichmentService.MAX_CACHE_ENTRIES:
            CommercialEnrichmentService._cache_websites.pop(next(iter(CommercialEnrichmentService._cache_websites)), None)
        CommercialEnrichmentService._cache_websites[domain] = True
        queue = [(base_url, 'homepage')]
        visited = set()
        dados_totais = 0
        extraidos_sessao = {}
        
        while queue and len(visited) < 4:
            url, page_type = queue.pop(0)
            if url in visited: continue
            visited.add(url)
            
            p_log(f"\n[CRAWL] Page: {page_type} | URL: {url}")
            metricas["paginas_visitadas"] += 1
            if page_type != 'homepage': metricas["paginas_internas_visitadas"] += 1
            
            html_content = ""
            source_tag = "static"
            
            start_nav = time.time()
            resp, classificacao, motivo, retries, is_timeout = CommercialEnrichmentService._safe_request(url, p_log=p_log)
            lead.retries_executados += retries
            
            if is_timeout:
                lead.teve_timeout = True
                metricas["timeouts"] += 1
                
            if classificacao != "VALIDA" or not resp:
                p_log(f"[NAVIGATION] Bloqueio/Erro estático: {motivo}")
                if page_type == 'homepage':
                    metricas["sites_com_erro"] += 1
                    historico.append(f"[Crawler] Acesso abortado: {motivo}")
                    break
                continue
            
            html_content = resp.content
            soup = BeautifulSoup(html_content, 'html.parser')
            texto_puro = soup.get_text(separator=' ', strip=True)
            p_log(f"[NAVIGATION] Carregada estaticamente — {(time.time() - start_nav)*1000:.0f}ms")
            
            is_js_dep = CommercialEnrichmentService._is_js_dependent(soup, texto_puro)
            p_log(f"[JS-DETECTION] Site JS-dependent: {'SIM' if is_js_dep else 'NÃO'}")
            
            if is_js_dep and browser_context:
                metricas["sites_dependentes_js"] += 1
                start_pw = time.time()
                p_log(f"[PLAYWRIGHT] Acionando fallback para {url}")
                page = None
                try:
                    page = browser_context.new_page()
                    page.set_default_timeout(15000)
                    page.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script", "xhr", "fetch"] else route.abort())
                    page.goto(url, wait_until="domcontentloaded")
                    time.sleep(2)
                    html_content = page.content()
                    soup = BeautifulSoup(html_content, 'html.parser')
                    texto_puro = soup.get_text(separator=' ', strip=True)
                    source_tag = "dynamic"
                    lead.enriquecido_via_playwright = True
                    p_log(f"[NAVIGATION] Página JS renderizada — {(time.time() - start_pw)*1000:.0f}ms")
                except PlaywrightTimeoutError:
                    p_log("[PLAYWRIGHT] Timeout ao processar DOM dinâmico.")
                    lead.teve_timeout = True
                    metricas["timeouts"] += 1
                except Exception as e:
                    p_log("[PLAYWRIGHT] Erro controlado durante navegação.")
                finally:
                    if page: page.close()
            
            if page_type == 'homepage':
                confianca, is_valid, identity_reason = CommercialEnrichmentService.validar_identidade_adaptativa(texto_puro, lead)
                if not is_valid:
                    p_log(f"[IDENTITY] Homepage incompatível. Abortando. {identity_reason}")
                    metricas["sites_rejeitados_identidade"] += 1
                    historico.append(f"[Identidade] Rejeitada ({confianca}/10).")
                    break
                    
                metricas["sites_visitados"] += 1
                internal_links = CommercialEnrichmentService._find_internal_links(soup, base_url, domain)
                p_log(f"[CRAWL] Links internos mapeados: {len(internal_links)}")
                for link, ltype in internal_links[:3]: queue.append((link, ltype))
            
            dados_totais += CommercialEnrichmentService._extract_contacts(soup, lead, page_type, source_tag, p_log, historico, metricas, extraidos_sessao)
            
        return dados_totais

    @staticmethod
    def _montar_estrategias(lead: Lead) -> list:
        nome_limpo = lead.nome.replace('"', '')
        est = [{"nome": "Busca Website", "query": f'"{nome_limpo}" {lead.cidade} site oficial', "alvo": "website"}]
        if lead.instagram == "⚠️ Não encontrado":
            est.append({"nome": "Busca Instagram", "query": f'"{nome_limpo}" {lead.cidade} instagram', "alvo": "instagram"})
        return est

    @staticmethod
    def enriquecer(leads: list, limite_opcao: str, debug_mode: bool = False, callback=None) -> tuple:
        limite = len(leads) if limite_opcao == "Todos" else min(int(limite_opcao), len(leads))
        leads_processar = leads[:limite]
        leads_restantes = leads[limite:]
        
        metricas = {
            "processados": limite, "sites_candidatos": 0, "sites_visitados": 0, "paginas_visitadas": 0,
            "paginas_internas_visitadas": 0, "tel_encontrados": 0, "wa_encontrados": 0, 
            "ig_encontrados": 0, "fb_encontrados": 0, "emails_encontrados": 0,
            "sites_com_erro": 0, "sites_dependentes_js": 0, "sites_rejeitados_identidade": 0,
            "enriquecidos_estatico": 0, "enriquecidos_playwright": 0, "sem_novos_dados": 0,
            "estrategias_executadas": 0, "bloqueios": 0, "timeouts": 0, "retries": 0, "tempo_total_ms": 0
        }

        def p_log(msg, force=False):
            if debug_mode or force: print(msg)

        playwright_instance = None
        browser = None
        browser_context = None

        if HAS_PLAYWRIGHT:
            try:
                playwright_instance = sync_playwright().start()
                browser = playwright_instance.chromium.launch(headless=True)
                browser_context = browser.new_context(user_agent="Mozilla/5.0", viewport={'width': 1280, 'height': 800})
            except Exception as e:
                p_log(f"[PLAYWRIGHT] Erro de inicialização global: {e}")

        try:
            for i, lead in enumerate(leads_processar):
                start_lead_time = time.time()
                if callback: callback(f"🔎 Avaliando lead {i+1}/{limite}: {lead.nome}...")
                p_log(f"\n[LEAD INPUT] Lead {i+1}/{limite}: {lead.nome}")
                
                for attr in ['telefone', 'whatsapp', 'instagram', 'facebook', 'email']:
                    if getattr(lead, attr, "⚠️ Não encontrado") != "⚠️ Não encontrado": setattr(lead, f"{attr}_origem", "OpenStreetMap")
                if lead.website != "⚠️ Não encontrado": lead.website_origem, lead.status_website = "OpenStreetMap", "🌐 Confirmado"
                else: lead.status_website = "❌ Não localizado"

                necessidades = {
                    "website": lead.website == "⚠️ Não encontrado",
                    "contatos": any(getattr(lead, attr) == "⚠️ Não encontrado" for attr in ['telefone', 'whatsapp', 'instagram', 'facebook', 'email'])
                }

                if not necessidades["website"] and necessidades["contatos"] and lead.status_website == "🌐 Confirmado":
                    p_log("[STRATEGY] Usando website pré-existente do OSM para crawler.")
                    metricas["sites_candidatos"] += 1
                    dados_deep = CommercialEnrichmentService._visitar_website_profundo(lead.website, lead, p_log, [], metricas, browser_context)
                    if dados_deep > 0: 
                        lead.status_enriquecimento = "📈 Enriquecido"
                        if lead.enriquecido_via_playwright: metricas["enriquecidos_playwright"] += 1
                        else: metricas["enriquecidos_estatico"] += 1
                    lead.tempo_processamento_ms = int((time.time() - start_lead_time) * 1000)
                    metricas["tempo_total_ms"] += lead.tempo_processamento_ms
                    continue

                estrategias = CommercialEnrichmentService._montar_estrategias(lead)
                estrategias_usadas, historico = [], []
                dados_deep, dados_serp = 0, 0

                for est in estrategias:
                    if not necessidades["website"] and not necessidades["contatos"]: break
                    if est["alvo"] == "website" and not necessidades["website"]: continue
                    
                    estrategias_usadas.append(est["nome"])
                    metricas["estrategias_executadas"] += 1
                    
                    cache_key = f"{est['query']}"
                    html_content, sucesso_http = "", False
                    
                    if cache_key in CommercialEnrichmentService._cache_buscas:
                        html_content = CommercialEnrichmentService._cache_buscas[cache_key]
                        sucesso_http = True
                    else:
                        resp, classificacao, motivo, retries, is_timeout = CommercialEnrichmentService._safe_request(
                            "https://html.duckduckgo.com/html/", method="POST", data={"q": est["query"]}, p_log=p_log
                        )
                        lead.retries_executados += retries
                        metricas["retries"] += retries
                        if is_timeout: 
                            lead.teve_timeout = True
                            metricas["timeouts"] += 1
                            
                        if classificacao == "VALIDA" and resp:
                            html_content = resp.text.lower()
                            sucesso_http = True
                            if len(CommercialEnrichmentService._cache_buscas) >= CommercialEnrichmentService.MAX_CACHE_ENTRIES:
                                CommercialEnrichmentService._cache_buscas.pop(next(iter(CommercialEnrichmentService._cache_buscas)), None)
                            CommercialEnrichmentService._cache_buscas[cache_key] = html_content
                        elif classificacao == "BLOQUEIO":
                            metricas["bloqueios"] += 1
                            break
                        else:
                            break

                    if sucesso_http and html_content:
                        confianca, is_valid, _ = CommercialEnrichmentService.validar_identidade_adaptativa(html_content, lead)
                        if confianca > lead.confianca_enriquecimento: lead.confianca_enriquecimento = confianca

                        if not is_valid:
                            historico.append(f"[{est['nome']}] SERP Identidade rejeitada.")
                            continue
                            
                        if necessidades["website"]:
                            regex_web = r'https?://(?:www\.)?(?!duckduckgo|google)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\'" >]*'
                            for w in re.findall(regex_web, html_content):
                                if not any(x in w.lower() for x in CommercialEnrichmentService._agregadores):
                                    lead.website = w
                                    lead.website_origem = "SERP"
                                    lead.status_website = "🔎 Website localizado"
                                    metricas["sites_candidatos"] += 1
                                    necessidades["website"] = False
                                    dados_serp += 1
                                    historico.append(f"[{est['nome']}] Domínio descoberto na SERP.")
                                    
                                    dados_deep += CommercialEnrichmentService._visitar_website_profundo(w, lead, p_log, historico, metricas, browser_context)
                                    break

                lead.estrategias_executadas = ", ".join(estrategias_usadas)
                lead.historico_estrategias = "\n".join(historico)
                
                lead.tempo_processamento_ms = int((time.time() - start_lead_time) * 1000)
                metricas["tempo_total_ms"] += lead.tempo_processamento_ms
                
                p_log("\n[DECISION]")
                p_log(f"[PERFORMANCE] Lead processado em {lead.tempo_processamento_ms}ms (Timeouts: {lead.teve_timeout} | Retries: {lead.retries_executados})")
                
                if dados_deep > 0:
                    lead.status_enriquecimento = "📈 Enriquecido"
                    lead.motivo_enriquecimento = f"Site visitado. {dados_deep} contatos incorporados."
                    if lead.enriquecido_via_playwright:
                        metricas["enriquecidos_playwright"] += 1
                        p_log(f"Resultado: ENRIQUECIDO (Playwright) | Contatos: {dados_deep}")
                    else:
                        metricas["enriquecidos_estatico"] += 1
                        p_log(f"Resultado: ENRIQUECIDO (Estático) | Contatos: {dados_deep}")
                elif dados_serp > 0:
                    lead.status_enriquecimento = "✅ Novos dados (SERP)"
                    lead.motivo_enriquecimento = f"Domínio localizado, sem contatos profundos."
                    metricas["enriquecidos_estatico"] += 1
                    if lead.status_website == "🔎 Website localizado": lead.status_website = "☑️ Site visitado — sem novos contatos"
                    p_log(f"Resultado: ENRIQUECIDO SUPERFICIALMENTE")
                elif len(estrategias_usadas) > 0:
                    lead.status_enriquecimento = "☑️ Sem novos dados"
                    lead.motivo_enriquecimento = "Buscas executadas, mas sem contatos úteis."
                    metricas["sem_novos_dados"] += 1
                    p_log("Resultado: SEM NOVOS DADOS")
                else:
                    lead.status_enriquecimento = "⚠️ Erro/Bloqueado"
                    
                lead.ultima_verificacao = datetime.now().strftime("%d/%m/%Y %H:%M")

        finally:
            if browser_context: browser_context.close()
            if browser: browser.close()
            if playwright_instance: playwright_instance.stop()

        return leads_processar + leads_restantes, metricas