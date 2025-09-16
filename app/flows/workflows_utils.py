
# app/flows/workflows_utils.py
import re, unicodedata
from typing import Optional, Union
from app.Model.coverages import Coverages
from datetime import datetime
from zoneinfo import ZoneInfo
NumberLike = Union[float, int, str, None]

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
def fmt_amount(a: Union[float, int, str, None]) -> str:
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



def parse_amount_ars(v: Union[str, int, float, None]) -> Optional[float]:
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
        tz = ZoneInfo("America/Argentina/Buenos_Aires")
        return datetime.strptime(f"{dia} {hora}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except Exception:
        return None

def is_today_not_future(dt_ba: Optional[datetime]) -> bool:
    """
    True si dt_ba es hoy en BA y no es futura.
    """
    if dt_ba is None:
        return False
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    now = datetime.now(tz)
    return (dt_ba.date() == now.date()) and (dt_ba <= now)

def amounts_equal_2dec(a: Optional[float], b: Optional[float]) -> bool:
    """
    Compara montos redondeando a 2 decimales; None falla.
    """
    if a is None or b is None:
        return False
    return round(float(a), 2) == round(float(b), 2)
