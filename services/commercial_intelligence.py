import math
import copy

def _safe_number(val, default=0.0):
    if isinstance(val, bool): 
        return default
    if isinstance(val, (int, float)) and math.isfinite(val) and val >= 0:
        return float(val)
    return default

def _safe_div(num, denom):
    n = _safe_number(num)
    d = _safe_number(denom)
    if d <= 0: 
        return 0.0
    return round(n / d, 2)

def _safe_dict(val):
    if isinstance(val, dict):
        return val
    return {}

def _parse_timestamp(run):
    if not isinstance(run, dict): 
        return 0.0
    ts = run.get("timestamp")
    if isinstance(ts, (int, float)) and math.isfinite(ts):
        return float(ts)
    if isinstance(ts, str):
        try:
            return float(ts)
        except ValueError:
            return 0.0
    return 0.0

def _calculate_commercial_score(run):
    if not isinstance(run, dict) or run.get("status") == "failed":
        return 0.0
        
    c_m = _safe_dict(run.get("commercial_metrics"))
    
    leads = _safe_number(c_m.get("total_leads"))
    wa = _safe_number(c_m.get("whatsapp"))
    em = _safe_number(c_m.get("email"))
    hp = _safe_number(c_m.get("alta_prioridade"))
    sw = _safe_number(c_m.get("sem_website"))
    
    raw_score = (hp * 5) + (sw * 3) + (wa * 2) + (em * 1) + (leads * 0.5)
    
    durations = _safe_dict(run.get("durations"))
    dur = _safe_number(durations.get("total_duration", 0))
    efficiency_factor = 1.0 + math.log10(dur + 1.0) 
    
    return round(raw_score / efficiency_factor, 2)

def calculate_data_sufficiency(history):
    if not isinstance(history, list): 
        return "insufficient"
    valid_runs = sum(1 for r in history if isinstance(r, dict) and r.get("status") != "failed")
    
    if valid_runs <= 1: return "insufficient"
    if valid_runs <= 5: return "limited"
    if valid_runs <= 12: return "moderate"
    return "strong"

def find_best_commercial_run(history):
    if not isinstance(history, list): 
        return None
    best_run_id = None
    max_score = -1.0
    
    for run in history:
        if not isinstance(run, dict): continue
        if run.get("status") == "failed": continue
        
        score = _calculate_commercial_score(run)
        if score > max_score:
            max_score = score
            run_id = run.get("run_id")
            best_run_id = str(run_id)[:8] if run_id else "unknown"
            
    return {"run_id": best_run_id, "score": max_score} if best_run_id else None

def analyze_efficiency(history):
    if not isinstance(history, list): 
        return {}
    total_leads = total_wa = total_hp = total_sw = total_dur = 0.0
    
    for run in history:
        if not isinstance(run, dict) or run.get("status") == "failed": 
            continue
            
        c_m = _safe_dict(run.get("commercial_metrics"))
        durations = _safe_dict(run.get("durations"))
        dur = _safe_number(durations.get("total_duration", 0))
        
        if dur <= 0: 
            continue
        
        total_leads += _safe_number(c_m.get("total_leads"))
        total_wa += _safe_number(c_m.get("whatsapp"))
        total_hp += _safe_number(c_m.get("alta_prioridade"))
        total_sw += _safe_number(c_m.get("sem_website"))
        total_dur += dur
        
    if total_dur == 0: 
        return {}
    
    return {
        "leads_per_sec": _safe_div(total_leads, total_dur),
        "whatsapp_per_sec": _safe_div(total_wa, total_dur),
        "high_priority_per_sec": _safe_div(total_hp, total_dur),
        "sem_website_per_sec": _safe_div(total_sw, total_dur)
    }

def calculate_commercial_trend(history):
    if not isinstance(history, list): 
        return "insufficient_data"
        
    valid_runs = [r for r in history if isinstance(r, dict) and r.get("status") != "failed"]
    
    if len(valid_runs) < 4: 
        return "insufficient_data"
    
    sorted_runs = sorted(valid_runs, key=_parse_timestamp)
    
    mid = len(sorted_runs) // 2
    older_half = sorted_runs[:mid]
    recent_half = sorted_runs[mid:]
    
    older_avg = _safe_div(sum(_calculate_commercial_score(r) for r in older_half), len(older_half))
    recent_avg = _safe_div(sum(_calculate_commercial_score(r) for r in recent_half), len(recent_half))
    
    diff = recent_avg - older_avg
    if diff > 1.0: return "improving"
    if diff < -1.0: return "declining"
    return "stable"

def analyze_provider_performance(history):
    if not isinstance(history, list): 
        return {}
    providers = {}
    allowed_providers = {"draft", "openai", "gemini"}
    
    for run in history:
        if not isinstance(run, dict) or run.get("status") == "failed": 
            continue
            
        prov = str(run.get("provider", "unknown")).strip().lower()
        if prov not in allowed_providers: 
            prov = "unknown"
        
        if prov not in providers:
            providers[prov] = {"runs": 0, "total_score": 0.0, "total_dur": 0.0, "total_leads": 0.0, "total_wa": 0.0}
            
        providers[prov]["runs"] += 1
        providers[prov]["total_score"] += _calculate_commercial_score(run)
        
        durations = _safe_dict(run.get("durations"))
        providers[prov]["total_dur"] += _safe_number(durations.get("total_duration", 0))
        
        c_m = _safe_dict(run.get("commercial_metrics"))
        providers[prov]["total_leads"] += _safe_number(c_m.get("total_leads"))
        providers[prov]["total_wa"] += _safe_number(c_m.get("whatsapp"))
            
    summary = {}
    for p, data in providers.items():
        summary[p] = {
            "runs": data["runs"],
            "avg_score": _safe_div(data["total_score"], data["runs"]),
            "avg_duration": _safe_div(data["total_dur"], data["runs"]),
            "wa_conversion_rate": _safe_div(data["total_wa"], data["total_leads"])
        }
    return summary

def analyze_parameter_performance(history):
    if not isinstance(history, list): 
        return {}
    combos = {}
    
    for run in history:
        if not isinstance(run, dict) or run.get("status") == "failed": 
            continue
        
        params = _safe_dict(run.get("params"))
        if not params: 
            continue
        
        safe_params = {}
        for k, v in params.items():
            if isinstance(v, (str, int, float, bool)):
                safe_params[str(k)] = str(v)
        
        if not safe_params: 
            continue
        
        combo_key = tuple(sorted(safe_params.items()))
        
        if combo_key not in combos:
            combos[combo_key] = {"runs": 0, "total_score": 0.0}
            
        combos[combo_key]["runs"] += 1
        combos[combo_key]["total_score"] += _calculate_commercial_score(run)
        
    summary = {}
    best_combo = None
    max_avg = -1.0
    
    for combo_key, data in combos.items():
        str_key = " | ".join([f"{k}:{v}" for k, v in combo_key])
        avg_score = _safe_div(data["total_score"], data["runs"])
        summary[str_key] = {
            "runs": data["runs"],
            "avg_score": avg_score
        }
        if avg_score > max_avg:
            max_avg = avg_score
            best_combo = str_key
            
    return {"combinations": summary, "best_combination": best_combo}

def generate_commercial_insights(history):
    sufficiency = calculate_data_sufficiency(history)
    if sufficiency in ["insufficient", "limited"]:
        return ["Há dados suficientes para gerar recomendações comerciais mais confiáveis apenas após mais execuções."]
        
    insights = []
    trend = calculate_commercial_trend(history)
    
    if trend == "improving":
        insights.append("📈 As execuções recentes apresentam um desempenho comercial superior ao histórico antigo.")
    elif trend == "declining":
        insights.append("📉 Houve uma queda na qualidade comercial ou eficiência nas últimas execuções.")
        
    best_run = find_best_commercial_run(history)
    if best_run and best_run.get("run_id"):
        insights.append(f"🏆 A execução de maior valor comercial acumulado foi a ID [{best_run['run_id']}]. Recomenda-se investigar os parâmetros utilizados nela.")
        
    prov_perf = analyze_provider_performance(history)
    if prov_perf:
        best_prov = max(prov_perf.items(), key=lambda x: x[1]['avg_score'], default=(None, None))[0]
        if best_prov and prov_perf[best_prov]['runs'] > 1:
            insights.append(f"🤖 O provedor LLM '{best_prov.upper()}' apresentou o maior Commercial Score médio nas execuções analisadas.")

    param_perf = analyze_parameter_performance(history)
    if param_perf and param_perf.get("best_combination"):
        insights.append(f"⚙️ A melhor combinação de parâmetros identificada foi: {param_perf['best_combination']}")

    if not insights:
        insights.append("O desempenho comercial tem se mantido constante dentro da média.")
        
    return insights

def build_commercial_intelligence_dashboard(history):
    return {
        "sufficiency": calculate_data_sufficiency(history),
        "best_run": find_best_commercial_run(history),
        "efficiency": analyze_efficiency(history),
        "trend": calculate_commercial_trend(history),
        "provider_performance": analyze_provider_performance(history),
        "parameter_performance": analyze_parameter_performance(history),
        "insights": generate_commercial_insights(history)
    }