import streamlit as st
import time
import uuid
import copy
import re
import math
import os
import pandas as pd
import sys
import truststore

truststore.inject_into_ssl()

# 1. ORDEM DE INICIALIZAÇÃO CORRIGIDA (Deve ser o primeiro comando Streamlit)
st.set_page_config(page_title="LeadFinder", page_icon="🎯", layout="wide")

from services.geocoding import GeocodingService
from services.overpass import OverpassService
from services.lead_processor import LeadProcessor
from services.commercial_enrichment import CommercialEnrichmentService
from services.lead_scoring import LeadScoringService
from services.commercial_payload import CommercialPayloadService
from services.message_generator import MessageGeneratorService
from services.commercial_intelligence import build_commercial_intelligence_dashboard

# ==========================================
# HELPERS HISTÓRICOS RESTAURADOS
# ==========================================

def get_active_secrets():
    secrets = []
    for k, v in os.environ.items():
        if ("API_KEY" in k or "SECRET" in k or "TOKEN" in k) and v:
            secrets.append(v)
    return secrets

def console_log(message: str, debug_mode: bool = None):
    # Se não for passado explicitamente, herda a configuração global do módulo (app.debug_mode)
    _debug_ativo = debug_mode if debug_mode is not None else globals().get('debug_mode', False)
    
    if not _debug_ativo:
        return
    
    if isinstance(msg, BaseException):
        msg_str = msg.__class__.__name__
    else:
        msg_str = str(msg)
        
    msg_str = msg_str.replace('\r', '\\r').replace('\n', '\\n')
    msg_str = re.sub(r'sk-[A-Za-z0-9_-]{20,}', '***REDACTED_OAI***', msg_str)
    msg_str = re.sub(r'AIza[0-9A-Za-z-_]{35}', '***REDACTED_GEMINI***', msg_str)
    
    if active_secrets:
        for secret in active_secrets:
            if len(secret) > 4:
                msg_str = msg_str.replace(secret, '***REDACTED***')
                
    print(msg_str[:5000])

def sanitize_input_string(text):
    if not isinstance(text, str): return ""
    clean = text.replace('\r', '').replace('\n', ' ')
    clean = re.sub(r'<[^>]*>', '', clean)
    return clean.strip()

def escape_html_content(text):
    if not isinstance(text, str): return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def parse_safe_quantity(val):
    try:
        if isinstance(val, float) and not math.isfinite(val):
            return 50
        v = int(val)
        return max(10, min(500, v))
    except (TypeError, ValueError):
        return 50

def extract_commercial_metrics(leads):
    c_wa, c_em, c_hp, c_sw = 0, 0, 0, 0
    for lead in leads:
        ld = vars(lead) if hasattr(lead, '__dict__') else lead
        if not isinstance(ld, dict): continue
            
        wa = ld.get("whatsapp")
        if wa and str(wa).strip() and str(wa) != "⚠️ Não informado": c_wa += 1
            
        em = ld.get("email")
        if em and str(em).strip() and str(em) != "⚠️ Não informado": c_em += 1
            
        ap = ld.get("alta_prioridade")
        if ap is True or str(ap).lower() == "true": c_hp += 1
            
        ws = ld.get("website")
        if not ws or not str(ws).strip() or str(ws) == "⚠️ Não informado": c_sw += 1

    return {
        "total_leads": len(leads),
        "whatsapp": c_wa,
        "email": c_em,
        "alta_prioridade": c_hp,
        "sem_website": c_sw
    }

# ==========================================
# CACHE, LIMITS E INTEGRAÇÕES
# ==========================================

@st.cache_data(ttl=3600, max_entries=50)
def cache_geocoding(cidade, estado):
    return GeocodingService.buscar_coordenadas(cidade, estado)

@st.cache_data(ttl=3600, max_entries=50)
def cache_overpass(segmento, lat, lon, quantidade, _callback=None):
    # CORREÇÃO: Transfere o _callback do Streamlit para o keyword real do OverpassService
    return OverpassService.buscar_empresas_por_coordenadas(segmento, lat, lon, quantidade, callback=_callback)

def is_pipeline_rate_limited(now, last, cooldown):
    return (now - last) < cooldown

def regenerar_mensagem_individual(nome_lead, provider, p_log=None):
    if "lista_leads" not in st.session_state or "payloads_comerciais" not in st.session_state:
        return
        
    now = time.time()
    cooldown_key = f"last_regen_{nome_lead}"
    last_run = st.session_state.get(cooldown_key, 0)
    
    if now - last_run < 2.0:
        if p_log: p_log(f"[RATE LIMIT] Regeneração ignorada para {nome_lead}")
        return
        
    st.session_state[cooldown_key] = now
    payloads = st.session_state.get("payloads_comerciais", {})
    
    if not isinstance(payloads, dict) or nome_lead not in payloads:
        return
        
    target_payload = {nome_lead: payloads[nome_lead]}
    
    try:
        new_msg = MessageGeneratorService.gerar_mensagens_lote(target_payload, provider=provider, p_log=p_log)
        if new_msg and nome_lead in new_msg:
            mensagens = st.session_state.get("mensagens_geradas", {})
            if isinstance(mensagens, dict):
                mensagens[nome_lead] = new_msg[nome_lead]
                st.session_state["mensagens_geradas"] = mensagens
    except Exception as e:
        if p_log: p_log(e)

# ==========================================
# SESSION STATE
# ==========================================

def init_session_state():
    defaults = {
        "is_processing": False,
        "current_run_id": None,
        "last_pipeline_ts": 0.0,
        "lista_leads": [],
        "run_history": [],
        "run_metrics": {},
        "payloads_comerciais": {},
        "mensagens_geradas": {},
        "metricas_enriquecimento": {},
        "leads_objetos": []
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session_state()

# ==========================================
# UI PRINCIPAL
# ==========================================

st.title("🎯 LeadFinder Pro")

with st.sidebar:
    st.header("Parâmetros da Busca")
    segmento_raw = st.text_input("Segmento", value="Marcenaria")
    cidade_raw = st.text_input("Cidade", value="Guarulhos")
    estado_raw = st.text_input("Estado", value="SP")
    quantidade_raw = st.number_input("Quantidade Máxima", min_value=10, max_value=500, value=20)
    
    segmento = sanitize_input_string(segmento_raw)
    cidade = sanitize_input_string(cidade_raw)
    estado = sanitize_input_string(estado_raw)
    quantidade = parse_safe_quantity(quantidade_raw)
    
    enriquecer = st.checkbox("Enriquecer Oportunidades", value=True)
    selected_provider = st.selectbox("Provedor LLM", ["draft", "openai", "gemini"])
    debug_mode = st.checkbox("Modo Debug", value=False) # Seguro por padrão
    buscar_btn = st.button("🚀 Iniciar Pipeline", type="primary", use_container_width=True)

if buscar_btn and not st.session_state.is_processing:
    if not cidade or not estado or not segmento:
        st.error("Por favor, preencha Segmento, Cidade e Estado com valores válidos.")
        st.stop()

    now_ts = time.time()
    last_pipeline = st.session_state.get("last_pipeline_ts", 0)
    
    if is_pipeline_rate_limited(now_ts, last_pipeline, cooldown=5.0):
        st.warning("⏱️ Por favor, aguarde alguns segundos antes de realizar uma nova busca.")
        st.stop()
        
    st.session_state["last_pipeline_ts"] = now_ts
    st.session_state.is_processing = True
    
    run_id = str(uuid.uuid4())
    st.session_state.current_run_id = run_id
    pipeline_success = False 

    with st.status("Executando Pipeline E2E...", expanded=True) as status:
        start_time = time.time()
        active_secrets = get_active_secrets()
        console_log(f"[PIPELINE START] Run {run_id} | Segment: {segmento} | Target: {cidade}/{estado}", debug_mode, active_secrets)
        
        try:
            def atualizar_status(msg):
                try: 
                    status.update(label=str(msg))
                except Exception as ex: 
                    console_log(f"[STATUS UPDATE IGNORED] {ex}", debug_mode, active_secrets)

            status.update(label="Localizando coordenadas...")
            lat, lon = cache_geocoding(cidade, estado)

            if lat is None or lon is None:
                status.update(label="Operação interrompida.", state="error")
                st.error("Não foi possível obter as coordenadas da cidade informada. A busca não foi executada.")
                st.stop() 
            
            status.update(label="Buscando empresas no OSM...")
            dados_brutos = cache_overpass(segmento, lat, lon, quantidade, _callback=atualizar_status)

            status.update(label="Processando empresas...")
            leads = LeadProcessor.processar_osm(dados_brutos, segmento, cidade, estado)

            if leads and enriquecer:
                status.update(label="Executando enriquecimento comercial...")
                leads, _ = CommercialEnrichmentService.enriquecer(leads, 10, debug_mode, atualizar_status)

            status.update(label="Calculando Lead Scoring...")
            leads_rankeados_tmp = LeadScoringService.avaliar_lote(leads, debug_mode=debug_mode, p_log=lambda m: console_log(m, debug_mode, active_secrets))

            status.update(label="Montando Contextos Comerciais...")
            payloads_comerciais_tmp = CommercialPayloadService.gerar_payloads_lote(leads_rankeados_tmp, debug_mode=debug_mode, p_log=lambda m: console_log(m, debug_mode, active_secrets))

            status.update(label=f"Gerando Abordagens ({selected_provider})...")
            try:
                mensagens_geradas_tmp = MessageGeneratorService.gerar_mensagens_lote(payloads_comerciais_tmp, provider=selected_provider, p_log=lambda m: console_log(m, debug_mode, active_secrets))
            except Exception as llm_error:
                console_log(llm_error, debug_mode, active_secrets)
                mensagens_geradas_tmp = {}
            
            # ATOMIC COMMIT SEGURO E DINÂMICO
            if str(st.session_state.get("current_run_id")) == str(run_id):
                st.session_state["payloads_comerciais"] = copy.deepcopy(payloads_comerciais_tmp)
                st.session_state["mensagens_geradas"] = copy.deepcopy(mensagens_geradas_tmp)
                st.session_state["leads_objetos"] = copy.deepcopy(leads_rankeados_tmp)
                st.session_state["lista_leads"] = [vars(lead) if hasattr(lead, '__dict__') else lead for lead in copy.deepcopy(leads_rankeados_tmp)]
                
                metricas_comerciais = extract_commercial_metrics(leads_rankeados_tmp)

                if isinstance(st.session_state.run_history, list):
                    st.session_state.run_history.insert(0, {
                        "run_id": run_id, 
                        "timestamp": now_ts, 
                        "status": "success",
                        "provider": selected_provider,
                        "params": {"cidade": cidade, "segmento": segmento},
                        "commercial_metrics": metricas_comerciais,
                        "durations": {"total_duration": round(time.time() - start_time, 2)}
                    })
                    st.session_state.run_history = st.session_state.run_history[:20]

                duration = round(time.time() - start_time, 2)
                console_log(f"[PIPELINE SUCCESS] Run {run_id} | Leads: {len(leads_rankeados_tmp)} | T: {duration}s", debug_mode, active_secrets)
                status.update(label="Pipeline concluído com sucesso!", state="complete")
                
                pipeline_success = True 
            else:
                console_log("[PIPELINE] Stale commit rejeitado.", debug_mode, active_secrets)
                status.update(label="Execução descontinuada.", state="error")
        
        except Exception as e:
            status.update(label="Operação interrompida.", state="error")
            console_log(e, debug_mode, active_secrets)
            st.error(f"⚠️ Erro na execução do Pipeline. Detalhe preservado no log. [{type(e).__name__}]")
        
        finally:
            st.session_state.is_processing = False
            # PRESERVAÇÃO DE ESTADO: Evita o rerun e apagamento do Session em caso de erro
            if pipeline_success:
                st.rerun()

# --- ÁREA PRINCIPAL ---
if st.session_state.get("lista_leads"):
    st.subheader("Resultados da Prospecção")
    st.dataframe(pd.DataFrame(st.session_state["lista_leads"]))

    if st.session_state.get("run_history"):
        st.divider()
        st.subheader("💼 Commercial Intelligence")
        ci_data = build_commercial_intelligence_dashboard(st.session_state.run_history)
        
        if ci_data.get("sufficiency") not in ["insufficient", "limited"]:
            col1, col2, col3 = st.columns(3)
            best = ci_data.get("best_run", {})
            if best:
                col1.metric("🏆 Melhor Execução (ID)", str(best.get("run_id", ""))[:8], f"Score: {best.get('score', 0)}")
            
            trend = ci_data.get("trend")
            trend_str = "Melhorando 📈" if trend == "improving" else "Caindo 📉" if trend == "declining" else "Estável"
            col2.metric("📊 Tendência Recente", trend_str)
            
            prov = ci_data.get("provider_performance", {})
            best_prov = max(prov.items(), key=lambda x: x[1]['avg_score'], default=(None, None))[0] if prov else "N/A"
            col3.metric("🤖 Melhor Provedor", str(best_prov).upper())

            if ci_data.get("insights"):
                st.info("\n\n".join(ci_data["insights"]))
        else:
            st.info("Há dados suficientes para gerar recomendações comerciais mais confiáveis apenas após mais execuções.")