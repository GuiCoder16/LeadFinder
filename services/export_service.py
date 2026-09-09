import pandas as pd
import io

class ExportService:
    # CORREÇÃO: Lista explícita mantendo o Contrato exato de 28 colunas
    EXPECTED_COLUMNS = [
        "nome", "categoria", "telefone", "whatsapp", "email", "website", 
        "instagram", "facebook", "endereco", "cidade", "estado", "latitude", 
        "longitude", "id_osm", "url_osm", "score_final", "score_presenca_digital", 
        "score_contato", "score_oportunidade", "score_qualidade", "score_proximidade", 
        "score_confiabilidade", "classificacao_prioridade", "status_enriquecimento", 
        "confianca_enriquecimento", "motivos_positivos", "motivos_negativos", "observacoes"
    ]

    @staticmethod
    def _sanitize_cell(val):
        if pd.isna(val) or val is None:
            return "⚠️ Não informado"
            
        # CORREÇÃO: Bypass para preservar tipos numéricos legítimos e evitar '90' != 90 nos testes
        if isinstance(val, (int, float)):
            return val
            
        text = str(val).strip()
        if not text:
            return "⚠️ Não informado"
            
        # Proteção Formula Injection
        if text.startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
            return f"'{text}"
            
        return text

    @staticmethod
    def gerar_dataframe_comercial(leads_objetos, p_log=None):
        if not leads_objetos:
            return pd.DataFrame(columns=ExportService.EXPECTED_COLUMNS)
            
        try:
            data = [vars(l) if hasattr(l, '__dict__') else l for l in leads_objetos]
            df = pd.DataFrame(data)
            
            # Enforça as 28 colunas com fallback
            for col in ExportService.EXPECTED_COLUMNS:
                if col not in df.columns:
                    df[col] = "⚠️ Não informado"
                    
            df = df[ExportService.EXPECTED_COLUMNS]
            
            # Sanitiza celula a celula, mantendo os tipos originais intactos
            for col in df.columns:
                df[col] = df[col].apply(ExportService._sanitize_cell)
                
            return df
            
        except Exception as e:
            if p_log: p_log(e)
            return pd.DataFrame(columns=ExportService.EXPECTED_COLUMNS)

    @staticmethod
    def to_csv(df, p_log=None):
        if df is None or df.empty: 
            return None
        try:
            return df.to_csv(index=False).encode('utf-8')
        except Exception as e:
            if p_log: p_log(e)
            return None

    @staticmethod
    def to_excel(df, p_log=None):
        if df is None or df.empty: 
            return None
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Leads Comerciais')
            return output.getvalue()
        except Exception as e:
            if p_log: p_log(e)
            return None