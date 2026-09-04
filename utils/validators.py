import re


_MISSING = {
    "", "none", "null", "não informado", "nao informado",
    "não", "no", "n/a", "nan", "undefined", "⚠️ não encontrado",
}


def normalizar_ausencia(valor) -> str:
    if valor is None:
        return "⚠️ Não encontrado"
    try:
        text = str(valor).strip()
    except Exception:
        return "⚠️ Não encontrado"
    if text.lower() in _MISSING:
        return "⚠️ Não encontrado"
    return text[:1000]


def normalizar_telefone(telefone) -> str:
    val = normalizar_ausencia(telefone)
    if val == "⚠️ Não encontrado":
        return val
    cleaned = re.sub(r"[^\d+]", "", val)
    return cleaned[:20] if cleaned else "⚠️ Não encontrado"


def extrair_whatsapp(telefone, tag_whatsapp) -> tuple:
    wa_val = normalizar_ausencia(tag_whatsapp)
    if wa_val != "⚠️ Não encontrado":
        cleaned = re.sub(r"[^\d]", "", wa_val)[:15]
        if 10 <= len(cleaned) <= 15:
            return f"https://wa.me/{cleaned}", "🟢 Confirmado"

    tel_val = normalizar_telefone(telefone)
    if tel_val != "⚠️ Não encontrado":
        cleaned = re.sub(r"[^\d]", "", tel_val)[:15]
        if len(cleaned) >= 10:
            if not cleaned.startswith("55") and len(cleaned) <= 11:
                cleaned = f"55{cleaned}"
            return f"https://wa.me/{cleaned}", "🟡 Inferido pelo telefone"

    return "⚠️ Não encontrado", "⚠️ Não encontrado"


def normalizar_url(url) -> str:
    val = normalizar_ausencia(url)
    if val == "⚠️ Não encontrado":
        return val
    # Apenas http/https; protocolos arbitrários não atravessam a fronteira.
    if re.match(r"^https?://", val, flags=re.I):
        return val
    if re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}([/:?#].*)?$", val):
        return f"https://{val}"
    return "⚠️ Não encontrado"
