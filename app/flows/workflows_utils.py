
# app/flows/workflows_utils.py
import re, unicodedata
from typing import Optional, Union
from app.Model.coverages import Coverages

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
