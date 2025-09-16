# app/flows/workflows_utils.py
import re, unicodedata, json
from typing import Optional, Union
from app.Model.coverages import Coverages
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NumberLike = Union[float, int, str, None]

# ========= Constantes reutilizables =========
BA_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
YES_RE = re.compile(r"\bsi\b|\bsí\b")
NO_RE  = re.compile(r"\bno\b")

# --------- Normalizaciones ---------
def norm_text(s: Optional[str]) -> str:
    """
    Minúsculas, sin tildes, espacios colapsados.
    Pensado para búsquedas/regex (no para mostrar).
    """
    s = s or ""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def deaccent_upper(s: Optional[str]) -> str:
    """
    MAYÚSCULAS sin tildes, espacios colapsados (p.ej., 'Ú nico' -> 'UNICO').
    """
    s = s or ""
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).strip().upper()
    return s

def plan_norm(s: Optional[str]) -> str:
    """
    Plan en MAYÚSCULAS sin espacios internos (p.ej., ' 210  ' -> '210', 'Ú nico' -> 'UNICO').
    """
    s = (s or "").strip()
    s = re.sub(r"\s+", "", s)
    s = deaccent_upper(s)
    return s or "UNICO"

# --------- Monto / Formato ---------
def fmt_amount(a: NumberLike) -> str:
    """
    Formatea a '1.234,56' (coma decimal). Si no puede, devuelve '-'.
    """
    try:
        return f"{float(a):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"

def calc_amount(obra_txt: Optional[str], plan_txt: Optional[str]) -> Optional[float]:
    """
    Calcula el copago según obra/plan.
    - Normaliza obra y plan.
    - Intenta por (obra, plan) y luego por (obra) a secas.
    - Devuelve float o None si no hay dato/ocurre un error.
    - Para 'PARTICULAR' fuerza plan 'UNICO'.
    """
    obra_norm = deaccent_upper(obra_txt or "")
    plan_n = plan_norm(plan_txt or "")

    cv = Coverages()
    try:
        if obra_norm == "PARTICULAR":
            amt = cv.get_amount_by_name_and_plan("PARTICULAR", "UNICO")
            if amt is None:
                amt = cv.get_amount_by_name("PARTICULAR")
            return float(amt) if amt is not None else None

        amt = cv.get_amount_by_name_and_plan(obra_norm, plan_n)
        if amt is None:
            amt = cv.get_amount_by_name(obra_norm)
        return float(amt) if amt is not None else None

    except Exception as e:
        print(f"[utils.calc_amount] Error Coverages: {e}")
        return None

def parse_amount_ars(v: NumberLike) -> Optional[float]:
    """
    Parsea montos en ARS desde string o número.
    Acepta $ y ARS, separadores de miles y coma decimal.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return float(v)
        except Exception:
            return None
    s = str(v)
    t = s.replace("ARS", "").replace("$", "").strip()
    t = re.sub(r"[^\d,.\-]", "", t)
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except Exception:
        return None

def names_match(expected: str, got: str) -> bool:
    """
    Compara nombres de forma 'suave': sin tildes, en minúsculas y colapsando espacios.
    Acepta si uno contiene al otro.
    """
    def _n(x: Optional[str]) -> str:
        x = x or ""
        x = "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn")
        x = re.sub(r"\s+", " ", x).strip().lower()
        return x
    a, b = _n(expected), _n(got)
    return bool(a and b and (a in b or b in a))

def receipt_datetime_ba(dia: str, hora: str) -> Optional[datetime]:
    """
    Construye un datetime zona Buenos Aires a partir de 'YYYY-MM-DD' y 'HH:MM'.
    """
    try:
        return datetime.strptime(f"{dia} {hora}", "%Y-%m-%d %H:%M").replace(tzinfo=BA_TZ)
    except Exception:
        return None

def is_today_not_future(dt_ba: Optional[datetime]) -> bool:
    """
    True si dt_ba es hoy en BA y no es futura.
    """
    if dt_ba is None:
        return False
    now = datetime.now(BA_TZ)
    return (dt_ba.date() == now.date()) and (dt_ba <= now)

def amounts_equal_2dec(a: Optional[float], b: Optional[float]) -> bool:
    """
    Compara montos redondeando a 2 decimales; None falla.
    """
    if a is None or b is None:
        return False
    return round(float(a), 2) == round(float(b), 2)

# ========= Historial (stateless) ============================================
def hist_load(conversation_str: str) -> list:
    try:
        h = json.loads(conversation_str or "[]")
        return h if isinstance(h, list) else []
    except Exception:
        return []

def hist_save(history: list) -> str:
    try:
        return json.dumps(history)
    except Exception:
        return "[]"

def hist_truncate(history: list, max_len: int = 80) -> list:
    # Evita crecer infinito el historial (performance/ruido).
    if not isinstance(history, list):
        return []
    if len(history) <= max_len:
        return history
    return history[-max_len:]

def hist_last_prompt_idx(history: list, prompts: set[str]) -> int:
    # Busca el último mensaje del bot que sea uno de los prompts (ASK/RETRY/confirm, etc.)
    if not isinstance(history, list):
        return -1
    for i in range(len(history) - 1, -1, -1):
        m = history[i]
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("content") in prompts:
            return i
    return -1

def hist_recent_since(history: list, prompts: set[str]) -> list:
    idx = hist_last_prompt_idx(history, prompts)
    return history[idx + 1:] if idx >= 0 else history

def hist_user_msgs(msgs: list) -> list:
    return [m for m in msgs if isinstance(m, dict) and m.get("role") == "user"]

def hist_last_user_content(msgs: list) -> str:
    for m in reversed(msgs or []):
        if isinstance(m, dict) and m.get("role") == "user":
            return (m.get("content") or "").strip()
    return ""

def hist_count_meta(history: list, flag: str) -> int:
    return sum(
        1 for m in history
        if isinstance(m, dict) and m.get("role") == "meta" and m.get("content") == flag
    )

def hist_add_meta(history: list, flag: str) -> None:
    if isinstance(history, list):
        history.append({"role": "meta", "content": flag})

# ========= Adjuntos =========================================================
def attach_is_line(s: str) -> bool:
    return bool(s and s.startswith("[Adjunto "))

def attach_kind(s: str) -> str:
    """
    Extrae el tipo de la línea de adjunto: "image", "image/jpeg", "application/pdf", "audio", etc.
    Espera líneas como "[Adjunto image] ...", "[Adjunto application/pdf] ...".
    """
    m = re.match(r"^\[Adjunto ([^\]]+)\]", s or "")
    return (m.group(1).strip().lower() if m else "")

# ========= Sí / No ===========================================================
def is_yes(s: str) -> bool:
    n = norm_text(s or "")
    return bool(YES_RE.search(n))

def is_no(s: str) -> bool:
    n = norm_text(s or "")
    return bool(NO_RE.search(n))

# ========= Fechas / zonas ====================================================
def parse_dt_utc(s: Optional[str]):
    """
    Parsea timestamp guardado en DB y devuelve ALWAYS UTC-aware.
    Si no tiene tz, asume UTC (Supabase).
    """
    if not s:
        return None
    dt = None
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except Exception:
                pass
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

# ========= Adjuntos en history ==============================================
def find_last_valid_attachment(history: list) -> str:
    """
    Busca el último user con adjunto image/pdf y devuelve esa línea completa
    (p.ej. "[Adjunto image] ...", "[Adjunto application/pdf] ..."), o "".
    """
    for m in reversed(history or []):
        if isinstance(m, dict) and m.get("role") == "user":
            content = (m.get("content") or "").strip()
            if attach_is_line(content):
                k = (attach_kind(content) or "").lower()
                if k == "image" or k.startswith("image/") or k == "application/pdf":
                    return content
    return ""

# ========= Matching tolerante de destinatario ================================
def names_match_flexible(expected: str, got: str) -> bool:
    """
    Matching tolerante: ignora tildes/may/min/espacios; acepta orden invertido.
    Acepta si hay coincidencia de al menos 2 tokens del esperado.
    """
    if names_match(expected, got):
        return True

    def _norm_tokens(s: str) -> list[str]:
        s = s or ""
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"\s+", " ", s).strip().lower()
        toks = [t for t in s.split(" ") if t and len(t) >= 2]
        return toks

    e, g = set(_norm_tokens(expected)), set(_norm_tokens(got))
    if not e or not g:
        return False
    matched = len(e & g)
    return matched >= min(2, len(e))

