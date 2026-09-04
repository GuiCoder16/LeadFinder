import streamlit as st
import pandas as pd
import os
import re
import html
import math
import uuid
import copy
import time

from services.geocoding import GeocodingService
from services.overpass import OverpassService
from services.lead_processor import LeadProcessor
from services.commercial_enrichment import CommercialEnrichmentService
from services.lead_scoring import LeadScoringService
from services.commercial_payload import CommercialPayloadService
from services.export_service import ExportService
from services.message_generator import MessageGeneratorService

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

def sanitize_filename(name: str) -> str:
    if not name: return "export"
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', str(name))[:50]

def sanitize_input_string(value: str, max_length: int = 100) -> str:
    if value is None: return ""
    return str(value).strip()[:max_length]

def escape_html_content(value: str) -> str:
    if value is None: return ""
    return html.escape(str(value))

def get_active_secrets() -> list:
    secrets = []
    for k in ["OPENAI_API_KEY", "GEMINI_API_KEY"]:
        val = os.getenv(k)
        if val and len(val) > 4: secrets.append(val)
    return secrets

def parse_safe_quantity(raw_value) -> int:
    try:
        val = float(raw_value)
        if math.isnan(val) or math.isinf(val):
            return 50
        return max(10, min(int(val), 500))
    except (ValueError, TypeError):
        return 50

def regenerar_mensagem_individual(nome_lead: str, provider_to_use: str, log_fn):
    ALLOWED_PROVIDERS = {"draft", "openai", "gemini"}
    safe_provider = str(provider_to_use).strip().lower()
    if safe_provider not in ALLOWED_PROVIDERS:
        safe_provider = "draft"

    # Sprint 7: Cooldown INDIVIDUAL estrito de 2 segundos
    now = time.time()
    last_regen = st.session_state.get(f"last_regen_{nome_lead}", 0)
    if now - last_regen < 2:
        log_fn(f"[RATE LIMIT] Regeneração bloqueada para {nome_lead}. Cooldown ativo.")
        st.warning("⏱️ Por favor, aguarde alguns segundos antes de gerar uma nova abordagem para este lead.")
        return
    st.session_state[f"last_regen_{nome_lead}"] = now

    payloads = st.session_state.get("payloads_comerciais")
    if not isinstance(payloads, dict) or not isinstance(nome_lead, str) or nome_lead not in payloads:
        log_fn(f"[UI CALLBACK] Lead não encontrado ou session state corrompido. Abortando.")
        return

    lead_data = payloads[nome_lead]
    if not isinstance(lead_data, dict) or "payload" not in lead_data or not isinstance(lead_data["payload"], dict):
        log_fn("[UI CALLBACK] Payload corrompido ou malformado. Abortando.")
        return

    try:
        with st.spinner("Gerando nova abordagem..."):
            nova_msg = MessageGeneratorService.gerar_mensagem(
                copy.deepcopy(lead_data["payload"]), 
                provider=safe_provider, 
                p_log=log_fn
            )
            if "mensagens_geradas" not in st.session_state or not isinstance(st.session_state["mensagens_geradas"], dict):
                st.session_state["mensagens_geradas"] = {}
            st.session_state["mensagens_geradas"][nome_lead] = nova_msg
    except Exception as e:
        log_fn(e)

# Limite de crescimentoda RAM no cache
@st.cache_data(ttl=3600, max_entries=50, show_spinner=False)
def cache_geocoding(cid, est):
    if not isinstance(cid, str) or not isinstance(est, str): return None, None
    return GeocodingService.buscar_coordenadas(cid, est)

@st.cache_data(ttl=3600, max_entries=50, show_spinner=False)
def cache_overpass(seg, lat, lon, qtd, _callback=None):
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)): return []
    return OverpassService.buscar_empresas_por_coordenadas(seg, lat, lon, qtd, callback=_callback)

def main():
    st.set_page_config(page_title="LeadFinder", page_icon="🎯", layout="wide")
    st.markdown("<style>.main { padding-top: 1.5rem; } .stButton > button { font-weight: bold; border-radius: 6px; }</style>", unsafe_allow_html=True)

    st.title("🎯 LeadFinder | FASE 7 (Production Ready)")

    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False

    with st.sidebar:
        st.header("Configuração da Busca")
        segmento_raw = st.selectbox("Ramo de atuação", options=OverpassService.get_categorias(), disabled=st.session_state.is_processing)
        cidade_raw = st.text_input("Cidade", value="Guarulhos", disabled=st.session_state.is_processing)
        estado_raw = st.text_input("Estado (Sigla)", value="SP", max_chars=2, disabled=st.session_state.is_processing)
        
        quantidade = parse_safe_quantity(st.number_input("Quantidade (Overpass)", min_value=10, max_value=200, value=50, step=10, disabled=st.session_state.is_processing))
        segmento = sanitize_input_string(segmento_raw)
        cidade = sanitize_input_string(cidade_raw, max_length=50)
        estado = sanitize_input_string(estado_raw, max_length=2).upper()
        
        st.divider()
        enriquecer = st.checkbox("Ativar Busca Multiestratégia", value=True, disabled=st.session_state.is_processing)
        max_enriquecer = st.selectbox("Leads a processar", ["Todos", "10", "20", "50"], index=0, disabled=st.session_state.is_processing)
        
        st.divider()
        st.header("🤖 Provedor de IA")
        ai_provider = st.radio("Mecanismo de Geração", options=["Draft Offline", "OpenAI", "Gemini"], index=0, disabled=st.session_state.is_processing)
        
        provider_map = {"Draft Offline": "draft", "OpenAI": "openai", "Gemini": "gemini"}
        selected_provider = provider_map.get(ai_provider, "draft") 
        
        if selected_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            st.warning("⚠️ OPENAI_API_KEY não configurada. Fallback para Draft Offline.")
        elif selected_provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
            st.warning("⚠️ GEMINI_API_KEY não configurada. Fallback para Draft Offline.")

        debug_mode = st.checkbox("☑️ Modo Debug / Logs Detalhados", value=False, disabled=st.session_state.is_processing)
        st.divider()
        buscar_btn = st.button("🚀 Iniciar Pipeline", width="stretch", disabled=st.session_state.is_processing)

    def console_log(msg):
        if debug_mode:
            # Mask Object leak
            if isinstance(msg, BaseException):
                safe_msg = msg.__class__.__name__
            else:
                safe_msg = str(msg)[:5000].replace('\n', '\\n').replace('\r', '\\r')
                
            safe_msg = re.sub(r'(sk-[a-zA-Z0-9]{20,})', '***REDACTED_OAI***', safe_msg)
            safe_msg = re.sub(r'(AIza[a-zA-Z0-9\-_]{30,})', '***REDACTED_GEM***', safe_msg)
            for secret in get_active_secrets():
                safe_msg = safe_msg.replace(secret, "***REDACTED***")
            print(safe_msg)

    if buscar_btn and not st.session_state.is_processing:
        if not cidade or not estado:
            st.error("Por favor, preencha a Cidade e o Estado com valores válidos.")
            st.stop()

        # Sprint 7: Pipeline Rate Limiting GLOBAL de 5 segundos
        now_ts = time.time()
        last_pipeline = st.session_state.get("last_pipeline_ts", 0)
        if now_ts - last_pipeline < 5:
            st.warning("⏱️ Por favor, aguarde alguns segundos antes de realizar uma nova busca intensiva.")
            st.stop()
            
        st.session_state["last_pipeline_ts"] = now_ts
        st.session_state.is_processing = True
        run_id = str(uuid.uuid4())
        st.session_state.current_run_id = run_id

        for key in ["leads_objetos", "lista_leads", "payloads_comerciais", "mensagens_geradas", "metricas_enriquecimento"]:
            if key in st.session_state:
                del st.session_state[key]

        with st.status("Executando Pipeline E2E...", expanded=True) as status:
            start_time = time.time()
            console_log(f"[PIPELINE START] Run {run_id} | Segment: {segmento} | Target: {cidade}/{estado}")
            
            try:
                def atualizar_status(msg):
                    try: status.update(label=str(msg))
                    except Exception: pass

                status.update(label="Localizando cidade...")
                lat, lon = cache_geocoding(cidade, estado)

                status.update(label="Buscando empresas no OpenStreetMap...")
                dados_brutos = cache_overpass(segmento, lat, lon, quantidade, _callback=atualizar_status)

                status.update(label="Processando empresas encontradas...")
                leads = LeadProcessor.processar_osm(dados_brutos, segmento, cidade, estado)

                if leads and enriquecer:
                    status.update(label="Executando enriquecimento comercial...")
                    leads, metricas_enr_tmp = CommercialEnrichmentService.enriquecer(leads, max_enriquecer, debug_mode, atualizar_status)
                else:
                    metricas_enr_tmp = {}

                status.update(label="Calculando Lead Scoring de Oportunidades...")
                leads_rankeados_tmp = LeadScoringService.avaliar_lote(leads, debug_mode=debug_mode, p_log=console_log)

                status.update(label="Montando Contextos Comerciais para IA...")
                payloads_comerciais_tmp = CommercialPayloadService.gerar_payloads_lote(leads_rankeados_tmp, debug_mode=debug_mode, p_log=console_log)

                status.update(label=f"Gerando Abordagens Comerciais ({ai_provider})...")
                try:
                    mensagens_geradas_tmp = MessageGeneratorService.gerar_mensagens_lote(payloads_comerciais_tmp, provider=selected_provider, p_log=console_log)
                except Exception as llm_error:
                    console_log(llm_error)
                    mensagens_geradas_tmp = {}
                
                # Atomic Commit
                if st.session_state.get("current_run_id") == run_id:
                    st.session_state["metricas_enriquecimento"] = copy.deepcopy(metricas_enr_tmp)
                    st.session_state["payloads_comerciais"] = copy.deepcopy(payloads_comerciais_tmp)
                    st.session_state["mensagens_geradas"] = copy.deepcopy(mensagens_geradas_tmp)
                    st.session_state["leads_objetos"] = copy.deepcopy(leads_rankeados_tmp)
                    st.session_state["lista_leads"] = [vars(lead) for lead in copy.deepcopy(leads_rankeados_tmp)]
                    
                    duration = round(time.time() - start_time, 2)
                    console_log(f"[PIPELINE SUCCESS] Run {run_id} | Leads: {len(leads_rankeados_tmp)} | T: {duration}s")
                    status.update(label="Pipeline concluído com sucesso!", state="complete")
                else:
                    console_log("[PIPELINE] Stale commit rejeitado. Outra execução sobrepôs a sessão.")
                    status.update(label="Execução descontinuada.", state="error")
            
            except Exception as e:
                status.update(label="Operação interrompida.", state="error")
                console_log(e)
                st.error("Erro interno sistêmico na execução do Pipeline. A operação foi interrompida de forma segura.")
            finally:
                st.session_state.is_processing = False
                st.rerun()

    lista_leads_state = st.session_state.get("lista_leads")
    if isinstance(lista_leads_state, list) and len(lista_leads_state) > 0:
        if all(isinstance(l, dict) for l in lista_leads_state):
            df = pd.DataFrame(lista_leads_state)
            
            if "score_final" in df.columns and "classificacao_prioridade" in df.columns:
                avg_score = df["score_final"].mean()
                tot_maxima = len(df[df["classificacao_prioridade"] == "🔥 PRIORIDADE MÁXIMA"])
                tot_alta = len(df[df["classificacao_prioridade"] == "🟢 ALTA PRIORIDADE"])
                tot_media = len(df[df["classificacao_prioridade"] == "🟡 MÉDIA PRIORIDADE"])
                tot_baixa = len(df[df["classificacao_prioridade"] == "⚪ BAIXA PRIORIDADE"])

                st.divider()
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Empresas Avaliadas", len(df))
                c2.metric("🎯 Score Médio", f"{avg_score:.0f}/100" if not pd.isna(avg_score) else "N/A")
                c3.metric("🔥 Prioridade MÁXIMA", tot_maxima)
                c4.metric("🟢 Prioridade ALTA", tot_alta)
                c5.metric("🟡/⚪ Média/Baixa", tot_media + tot_baixa)

                st.subheader("Filtros Comerciais")
                col_f1, col_f2, col_f3, col_f4 = st.columns(4)

                with col_f1: f_min_score = st.slider("Score Mínimo", 0, 100, 0)
                with col_f2: f_classificacao = st.selectbox("Classificação", ["Todas", "🔥 PRIORIDADE MÁXIMA", "🟢 ALTA PRIORIDADE", "🟡 MÉDIA PRIORIDADE", "⚪ BAIXA PRIORIDADE"])
                with col_f3: f_canal = st.selectbox("Canais Exigidos", ["Qualquer", "Com WhatsApp", "Com E-mail", "Sem Website (Oportunidade)"])
                with col_f4: f_confiabilidade = st.selectbox("Validação Web", ["Todas", "Somente Identidade Validada"])

                df_exibicao = df[df["score_final"] >= f_min_score].copy()
                if f_classificacao != "Todas": df_exibicao = df_exibicao[df_exibicao["classificacao_prioridade"] == f_classificacao]
                if f_canal == "Com WhatsApp" and "whatsapp" in df_exibicao.columns: df_exibicao = df_exibicao[df_exibicao["whatsapp"] != "⚠️ Não encontrado"]
                elif f_canal == "Com E-mail" and "email" in df_exibicao.columns: df_exibicao = df_exibicao[df_exibicao["email"] != "⚠️ Não encontrado"]
                elif f_canal == "Sem Website (Oportunidade)" and "website" in df_exibicao.columns: df_exibicao = df_exibicao[df_exibicao["website"] == "⚠️ Não encontrado"]
                if f_confiabilidade == "Somente Identidade Validada" and "confianca_enriquecimento" in df_exibicao.columns: df_exibicao = df_exibicao[df_exibicao["confianca_enriquecimento"] >= 6]

                if not df_exibicao.empty:
                    df_tabela = df_exibicao[["nome", "score_final", "classificacao_prioridade", "whatsapp", "email", "website", "status_enriquecimento"]].copy()
                    df_tabela.rename(columns={"score_final": "Score", "classificacao_prioridade": "Prioridade"}, inplace=True)
                    df_tabela.insert(0, "Selecionar", False)

                    tabela_editada = st.data_editor(df_tabela, hide_index=True, width="stretch", column_config={"Score": st.column_config.ProgressColumn("Score (0-100)", min_value=0, max_value=100, format="%d")})
                    linhas = tabela_editada[tabela_editada["Selecionar"] == True].index

                    if len(linhas) > 0:
                        st.divider()
                        st.subheader("🔍 Justificativa Analítica do Score")

                        for i, idx in enumerate(linhas):
                            lead = df_exibicao.loc[idx]
                            safe_nome = escape_html_content(lead.get('nome', 'Desconhecido'))
                            safe_classificacao = escape_html_content(lead.get('classificacao_prioridade', ''))
                            
                            with st.expander(f"{safe_nome} — {safe_classificacao} (Score: {lead.get('score_final', 0)})", expanded=True):
                                m1, m2, m3, m4, m5, m6 = st.columns(6)
                                m1.metric("Presença", lead.get("score_presenca_digital", 0))
                                m2.metric("Contato", lead.get("score_contato", 0))
                                m3.metric("Oportunidade", lead.get("score_oportunidade", 0))
                                m4.metric("Qualidade", lead.get("score_qualidade", 0))
                                m5.metric("Proximidade", lead.get("score_proximidade", 0))
                                m6.metric("Confiabilidade", lead.get("score_confiabilidade", 0))
                                st.divider()

                                c1, c2 = st.columns(2)
                                with c1:
                                    st.markdown("**Pontos Positivos (Gatilhos de Venda):**")
                                    motivos_pos = lead.get("motivos_positivos", [])
                                    if isinstance(motivos_pos, list) and motivos_pos:
                                        for motivo in motivos_pos: st.markdown(f"- {escape_html_content(motivo)}")
                                    else:
                                        st.write("- Nenhum.")
                                with c2:
                                    st.markdown("**Pontos Negativos/Desafios:**")
                                    motivos_neg = lead.get("motivos_negativos", [])
                                    if isinstance(motivos_neg, list) and motivos_neg:
                                        for motivo in motivos_neg: st.markdown(f"- {escape_html_content(motivo)}")
                                    else:
                                        st.write("- Nenhum.")

                                if debug_mode:
                                    payloads_dict = st.session_state.get("payloads_comerciais", {})
                                    if isinstance(payloads_dict, dict):
                                        payload_info = payloads_dict.get(lead.get("nome"))
                                        if isinstance(payload_info, dict):
                                            st.divider()
                                            st.markdown("### 🧠 Contexto Comercial para IA")
                                            c_i1, c_i2 = st.columns(2)
                                            c_i1.caption(f"**Intenção:** `{escape_html_content(payload_info.get('payload', {}).get('contexto_comercial', {}).get('intencao', 'N/A'))}`")
                                            c_i2.caption(f"**Tamanho:** `{payload_info.get('size', 0)} bytes`")
                                            st.info(escape_html_content(payload_info.get("payload", {}).get("contexto_comercial", {}).get("contexto_texto", "")))
                                            
                                            with st.expander("Ver Payload JSON Serializável"):
                                                st.json(payload_info.get("payload", {}))

                                msgs_dict = st.session_state.get("mensagens_geradas", {})
                                if isinstance(msgs_dict, dict):
                                    msg_obj = msgs_dict.get(lead.get("nome"))
                                    if isinstance(msg_obj, dict):
                                        st.divider()
                                        col_titulo, col_regen = st.columns([3, 1])
                                        with col_titulo: st.markdown("### 💬 Gerador de Abordagem Comercial")
                                        
                                        safe_key = f"regen_lead_{i}_{sanitize_filename(lead.get('nome', ''))}"
                                        
                                        with col_regen: 
                                            st.button(
                                                "🔄 Gerar nova abordagem", 
                                                key=safe_key, 
                                                on_click=regenerar_mensagem_individual, 
                                                args=(lead.get('nome'), selected_provider, console_log)
                                            )

                                        cg1, cg2, cg3, cg4 = st.columns(4)
                                        cg1.caption(f"**Status:** `{escape_html_content(msg_obj.get('status', 'N/A'))}`")
                                        cg2.caption(f"**Intenção:** `{escape_html_content(msg_obj.get('intencao', 'N/A'))}`")
                                        
                                        provedor_usado = msg_obj.get('provedor', 'draft')
                                        if msg_obj.get("fallback", False): indicador_tag = "🟡 Fallback (Draft)"
                                        elif provedor_usado == "draft": indicador_tag = "📝 Draft Offline"
                                        else: indicador_tag = "🤖 Gerada por IA"
                                            
                                        cg3.caption(f"**Motor:** `{indicador_tag}`")
                                        cg4.caption(f"**Provedor:** `{escape_html_content(provedor_usado).upper()}`")

                                        validacao = msg_obj.get('validacao', {})
                                        if isinstance(validacao, dict):
                                            if validacao.get('valida', False): st.caption("✓ Mensagem validada")
                                            else: st.caption(f"⚠️ Mensagem requer revisão ( { escape_html_content(' | '.join(validacao.get('motivos', []))) } )")
                                        
                                        if msg_obj.get("status") == "success":
                                            st.markdown("**Sugestão de Mensagem (Pronta para uso):**")
                                            st.code(msg_obj.get("mensagem", ""), language="")
                                        else:
                                            st.warning(escape_html_content(msg_obj.get("mensagem", "")))

                                safe_version = escape_html_content(str(lead.get('score_version', 'N/A'))[:10])
                                st.markdown(f"<br><span style='color:gray; font-size:12px;'>Scoring Algorithm v{safe_version}</span>", unsafe_allow_html=True)
            else:
                st.warning("Nenhum lead estruturado encontrado com estes filtros.")

    leads_objetos_state = st.session_state.get("leads_objetos")
    if isinstance(leads_objetos_state, list) and len(leads_objetos_state) > 0:
        st.divider()
        st.subheader("📥 Exportação Comercial")
        df_export = ExportService.gerar_dataframe_comercial(leads_objetos_state, p_log=console_log)

        if not df_export.empty:
            st.dataframe(df_export, hide_index=True, width="stretch")
            
            safe_cidade_file = sanitize_filename(cidade)
            safe_segmento_file = sanitize_filename(segmento)
            
            e1, e2 = st.columns(2)
            with e1:
                if HAS_OPENPYXL:
                    xlsx_data = ExportService.to_excel(df_export, p_log=console_log)
                    if xlsx_data:
                        st.download_button(
                            "📥 Baixar Planilha (XLSX)", 
                            data=xlsx_data, 
                            file_name=f"leads_{safe_cidade_file}_{safe_segmento_file}.xlsx", 
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                            type="primary", 
                            use_container_width=True
                        )
                else:
                    st.warning("Biblioteca 'openpyxl' ausente. Excel desabilitado.")
            with e2:
                csv_data = ExportService.to_csv(df_export, p_log=console_log)
                if csv_data:
                    st.download_button(
                        "📥 Baixar Dados (CSV)", 
                        data=csv_data, 
                        file_name=f"leads_{safe_cidade_file}_{safe_segmento_file}.csv", 
                        mime="text/csv", 
                        use_container_width=True
                    )
        else:
            st.info("Nenhum dado disponível para exportação.")

if __name__ == "__main__":
    main()