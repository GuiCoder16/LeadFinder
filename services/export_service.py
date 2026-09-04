import pandas as pd
import io

class ExportService:
    EXPECTED_COLUMNS = 28
    
    # Contrato fixo para garantir que a exportação não seja corrompida 
    # por chaves ausentes durante um partial-failure
    BASE_COLUMNS = [
        "nome", "categoria", "telefone", "whatsapp", "email", "website", 
        "instagram", "facebook", "endereco", "cidade", "estado", "latitude", 
        "longitude", "id_osm", "url_osm", "score_final", "score_presenca_digital", 
        "score_contato", "score_oportunidade", "score_qualidade", "score_proximidade", 
        "score_confiabilidade", "classificacao_prioridade", "status_enriquecimento", 
        "confianca_enriquecimento", "motivos_positivos", "motivos_negativos", "observacoes"
    ]

    @staticmethod
    def _sanitize_cell(val):
        """
        Previne Formula Injection (CSV/Excel DDE Execution).
        Campos originários de bancos de dados públicos podem iniciar com
        caracteres maliciosos para execução de macros locais no computador do usuário.
        """
        if pd.isna(val) or val is None:
            return ""
        
        text = str(val).strip()
        
        # Blindagem contra execução arbitrária no MS Excel / Sheets
        if text.startswith(('=', '+', '-', '@', '\t', '\r', '\n')):
            return f"'{text}"
            
        return text

    @staticmethod
    def gerar_dataframe_comercial(leads_objetos, p_log=None):
        if not leads_objetos:
            return pd.DataFrame(columns=ExportService.BASE_COLUMNS)
            
        try:
            # Garante que consumimos as propriedades do objeto caso seja classe, ou copia caso dict
            data = [vars(l) if hasattr(l, '__dict__') else l for l in leads_objetos]
            df = pd.DataFrame(data)
            
            # Enforça o contrato de 28 colunas
            for col in ExportService.BASE_COLUMNS:
                if col not in df.columns:
                    df[col] = "⚠️ Não informado"
                    
            # Filtra estritamente o layout final no modelo de contrato
            df = df[ExportService.BASE_COLUMNS]
            
            # Aplica Sanitização de DDE Injection em todo o Dataframe
            for col in df.columns:
                df[col] = df[col].apply(ExportService._sanitize_cell)
                
            return df
            
        except Exception as e:
            if p_log: p_log(e)
            # Fail-closed state: retorna frame vazio mas no contrato de dimensões exato
            return pd.DataFrame(columns=ExportService.BASE_COLUMNS)

    @staticmethod
    def to_csv(df, p_log=None):
        if df is None or df.empty: 
            return None
        try:
            # Exportação transacional de CSV
            return df.to_csv(index=False).encode('utf-8')
        except Exception as e:
            if p_log: p_log(e)
            return None

    @staticmethod
    def to_excel(df, p_log=None):
        if df is None or df.empty: 
            return None
        try:
            # Memory Safe BytesIO buffer com Context Manager (autoclose)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Leads Comerciais')
            return output.getvalue()
        except Exception as e:
            if p_log: p_log(e)
            return None