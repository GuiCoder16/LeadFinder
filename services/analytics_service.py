import copy
import math
import pandas as pd
import io

ANALYTICS_EXPORT_COLUMNS = [
    "timestamp", "run_id", "status", "leads", "whatsapp", "email", 
    "alta_prioridade", "sem_website", "duracao_total", "slowest_stage", "failure_reason", "provider"
]
ALLOWED_FAILURES = {"GEOCODING_FAILURE", "OVERPASS_FAILURE", "ENRICHMENT_FAILURE", "LLM_FAILURE", "NETWORK_TIMEOUT", "RATE_LIMIT", "INVALID_INPUT", "PROCESSING_FAILURE", "SCORING_FAILURE", "PAYLOAD_FAILURE", "EXPORT_FAILURE", "SESSION_STATE_CORRUPTION", "STALE_RUN"}

def _safe_float(val):
    if isinstance(val, (int, float)) and math.isfinite(val) and val >= 0:
        return float(val)
    return None

def _safe_div(num, denom):
    if not denom or denom <= 0: return 0.0
    return round((num / denom) * 100, 2)

def calculate_conversion_metrics(history):
    if not isinstance(history, list) or not history:
        return {"whatsapp_rate": 0.0, "email_rate": 0.0, "website_gap_rate": 0.0, "high_priority_rate": 0.0}
    
    total_leads = total_wa = total_email = total_sem_web = total_high = 0
    
    for run in history:
        if not isinstance(run, dict): continue
        c_metrics = run.get("commercial_metrics", {})
        if not isinstance(c_metrics, dict): continue
        
        total_leads += c_metrics.get("total_leads", 0)
        total_wa += c_metrics.get("whatsapp", 0)
        total_email += c_metrics.get("email", 0)
        total_sem_web += c_metrics.get("sem_website", 0)
        total_high += c_metrics.get("alta_prioridade", 0)
        
    return {
        "whatsapp_rate": _safe_div(total_wa, total_leads),
        "email_rate": _safe_div(total_email, total_leads),
        "website_gap_rate": _safe_div(total_sem_web, total_leads),
        "high_priority_rate": _safe_div(total_high, total_leads)
    }

def calculate_stage_performance(history):
    if not isinstance(history, list): return {}
    stages = {}
    
    for run in history:
        if not isinstance(run, dict): continue
        durations = run.get("durations", {})
        if not isinstance(durations, dict): continue
        
        for stage, val in durations.items():
            if stage == "total_duration": continue
            f_val = _safe_float(val)
            if f_val is not None:
                if stage not in stages: stages[stage] = []
                stages[stage].append(f_val)
                
    result = {}
    slowest_overall_stage = None
    max_avg = -1
    
    for stage, vals in stages.items():
        if not vals: continue
        avg = sum(vals) / len(vals)
        if avg > max_avg:
            max_avg = avg
            slowest_overall_stage = stage
            
        result[stage] = {
            "avg": round(avg, 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
            "samples": len(vals)
        }
        
    return {"stages": result, "slowest_stage": slowest_overall_stage}

def calculate_failure_analytics(history):
    if not isinstance(history, list): return {"total": 0, "partial": 0, "reasons": {}}
    
    total = partial = 0
    reasons = {}
    
    for run in history:
        if not isinstance(run, dict): continue
        st = run.get("status")
        if st == "failed": total += 1
        elif st == "partial_success": partial += 1
        else: continue
        
        fr = run.get("failure_reason", "UNKNOWN_FAILURE")
        if not isinstance(fr, str) or fr not in ALLOWED_FAILURES:
            fr = "UNKNOWN_FAILURE"
            
        reasons[fr] = reasons.get(fr, 0) + 1
        
    return {"total_failures": total, "partial_failures": partial, "by_reason": reasons}

def find_best_runs(history):
    if not isinstance(history, list): return {}
    
    bests = {"most_leads": None, "most_whatsapp": None, "most_email": None, "most_high_priority": None, "fastest": None}
    maxes = {"leads": -1, "wa": -1, "em": -1, "hp": -1}
    min_time = float('inf')
    
    for run in history:
        if not isinstance(run, dict) or run.get("status") == "failed": continue
        c_m = run.get("commercial_metrics", {})
        if isinstance(c_m, dict):
            if c_m.get("total_leads", -1) > maxes["leads"]:
                maxes["leads"] = c_m.get("total_leads")
                bests["most_leads"] = run.get("run_id")
            if c_m.get("whatsapp", -1) > maxes["wa"]:
                maxes["wa"] = c_m.get("whatsapp")
                bests["most_whatsapp"] = run.get("run_id")
            if c_m.get("alta_prioridade", -1) > maxes["hp"]:
                maxes["hp"] = c_m.get("alta_prioridade")
                bests["most_high_priority"] = run.get("run_id")
                
        d_m = run.get("durations", {})
        if isinstance(d_m, dict):
            td = _safe_float(d_m.get("total_duration"))
            if td is not None and td < min_time:
                min_time = td
                bests["fastest"] = run.get("run_id")
                
    return bests

def build_history_timeline(history):
    if not isinstance(history, list): return []
    timeline = []
    for run in history:
        if not isinstance(run, dict): continue
        c_m = run.get("commercial_metrics", {})
        timeline.append({
            "timestamp": run.get("timestamp", ""),
            "status": run.get("status", "unknown"),
            "leads": c_m.get("total_leads", 0) if isinstance(c_m, dict) else 0,
            "whatsapp": c_m.get("whatsapp", 0) if isinstance(c_m, dict) else 0,
            "duration": _safe_float(run.get("durations", {}).get("total_duration")) or 0.0,
            "failure_reason": run.get("failure_reason", "")
        })
    return timeline

def _sanitize_csv_cell(val):
    if pd.isna(val) or val is None: return ""
    text = str(val).strip()
    if text.startswith(('=', '+', '-', '@', '\t', '\r', '\n')): return f"'{text}"
    return text

def export_operational_analytics_csv(history):
    if not isinstance(history, list) or not history: return None
    
    rows = []
    perf = calculate_stage_performance(history)
    
    for run in history:
        if not isinstance(run, dict): continue
        c_m = run.get("commercial_metrics", {})
        
        # Obter o slowest stage global, ou individual se quisessemos (aqui usando um placeholder para manter fixo)
        slowest = perf.get("slowest_stage", "")
        
        rows.append({
            "timestamp": run.get("timestamp", ""),
            "run_id": run.get("run_id", ""),
            "status": run.get("status", ""),
            "leads": c_m.get("total_leads", 0),
            "whatsapp": c_m.get("whatsapp", 0),
            "email": c_m.get("email", 0),
            "alta_prioridade": c_m.get("alta_prioridade", 0),
            "sem_website": c_m.get("sem_website", 0),
            "duracao_total": _safe_float(run.get("durations", {}).get("total_duration")) or 0,
            "slowest_stage": slowest,
            "failure_reason": run.get("failure_reason", ""),
            "provider": run.get("provider", "")
        })
        
    try:
        df = pd.DataFrame(rows, columns=ANALYTICS_EXPORT_COLUMNS)
        for col in df.columns: df[col] = df[col].apply(_sanitize_csv_cell)
        return df.to_csv(index=False).encode('utf-8')
    except Exception:
        return None

def build_operational_dashboard(history):
    """Orquestrador final que devolve todo o dicionário formatado e estéril para a UI."""
    return {
        "conversion": calculate_conversion_metrics(history),
        "performance": calculate_stage_performance(history),
        "failures": calculate_failure_analytics(history),
        "best_runs": find_best_runs(history),
        "timeline": build_history_timeline(history)
    }