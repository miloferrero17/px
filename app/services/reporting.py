import json
import re
import hashlib
from typing import Dict, List, Tuple, Optional, Any

# === Esquema para ordenar/rotular cards ===================================
SCHEMA_ORDER: List[Tuple[str, str]] = [
    # Header (leído por la vista para edad y chip)
    ("fecha_nacimiento", "Fecha de nacimiento"),
    ("genero", "Género"),
    ("triage", "Clasificación de triage"),

    # Columna 1 — Información Triage
    ("motivo_consulta", "Motivo de consulta"),
    ("sintoma_principal", "Síntoma principal"),
    ("factor_desencadenante", "Factor desencadenante"),
    ("inicio", "Inicio de síntomas"),
    ("medicacion_recibida", "Medicación recibida"),

    # Columna 2 — Historia Clínica
    ("antecedentes_personales", "Antecedentes personales"),
    ("alergias", "Alergias"),
    ("antecedentes_familiares", "Antecedentes familiares"),

    ("medicacion_habitual", "Medicación habitual"),

    # Columna 3 — Consulta Actual
    ("anamnesis", "Anamnesis"),
    ("examen_fisico", "Examen físico"),
    ("impresion_diagnostica", "Impresión diagnóstica"),
]


# === Defaults ==============================================================
DEFAULTS = {
    # Header
    "fecha_nacimiento": "No disponible",
    "genero": "—",
    "triage": "⬜⬜⬜⬜⬜ Urgencia Estimada No disponible",

    # Columna 1 — Información Triage
    "motivo_consulta": "No refiere",
    "sintoma_principal": "No refiere",
    "factor_desencadenante": "No refiere",
    "inicio": "No refiere",
    "medicacion_recibida": "No refiere",

    # Columna 2 — Historia Clínica
    "antecedentes_personales": "Niega",
    "alergias": "Niega",
    "antecedentes_familiares": "Niega",
    "medicacion_habitual": "No refiere",

    # Columna 3 — Consulta Actual
    "anamnesis": "No refiere",
    "examen_fisico": "No consignado",
    "impresion_diagnostica": "No consignada",
}


# === Parsing robusto del JSON del modelo ==================================
def _strip_md_fences(t: str) -> str:
    """Quita ```json ... ``` si el modelo lo agrega por error."""
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", (t or "").strip(), flags=re.I | re.S)

def _extract_json(t: str) -> Dict:
    """
    Intenta cargar JSON directo; si falla, busca el primer objeto {...} en el texto.
    """
    t = _strip_md_fences(t)
    try:
        return json.loads(t)
    except Exception:
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e > s:
            return json.loads(t[s:e+1])
        raise ValueError("No se pudo parsear JSON de la salida del modelo.")

# === Normalización + cards =================================================
def normalize_report_dict(
    data,
    schema=SCHEMA_ORDER,
    defaults=DEFAULTS,
    use_defaults: bool = True,
):
    """
    - Devuelve SOLO las claves usadas por la UI (según SCHEMA_ORDER).
    - Normaliza nombres mínimos (ej. birth_date -> fecha_nacimiento).
    - Si use_defaults=True (recomendado), completa faltantes con DEFAULTS.
    """
    data = dict(data or {})

    # Normalización mínima de nombres para que el HTML lo lea bien
    if "birth_date" in data and "fecha_nacimiento" not in data:
        data["fecha_nacimiento"] = data.pop("birth_date")

    report: Dict[str, str] = {}
    for key, _label in schema:
        # (por si quedó alguna sección en schema en el futuro)
        if key.startswith("__section_"):
            continue
        val = data.get(key, "")

        # Coerción a string y trim
        if isinstance(val, str):
            val = val.strip()
        if use_defaults:
            if val in (None, "", []):
                val = defaults.get(key, "")
        else:
            if val is None:
                val = ""
        report[key] = val

    return report


def cards_from_report(report, schema=SCHEMA_ORDER):
    cards = []
    for key, label in schema:
        if key.startswith("__section_"):
            cards.append({"type": "section", "label": label})
        else:
            cards.append({"type": "field", "key": key, "label": label, "value": report.get(key)})
    return cards

def build_report_cards(conversation_history: List[Dict], brain, model: str = "gpt-4.1", temperature: float = 0.0):
    """
    - Llama al modelo y obtiene JSON.
    - Normaliza y arma cards.
    Devuelve: (report_dict_normalizado, cards)
    """
    out = brain.ask_openai(conversation_history, temperature=temperature, model=model)
    data = _extract_json(out)
    report = normalize_report_dict(data, use_defaults=True)
    cards = cards_from_report(report)
    return report, cards

def build_report_cards_from_json_text(json_text: str):
    """
    Usa un JSON (string) ya dado: lo normaliza y arma cards.
    Devuelve: (report_dict_normalizado, cards)
    """
    data = _extract_json(json_text)
    report = normalize_report_dict(data)
    cards = cards_from_report(report)
    return report, cards

# === Snapshot / hash / helpers ============================================
UI_KEYS = [
    # Header que guardamos como snapshot
    "fecha_nacimiento",
    "genero",

    # Columna 1 — Información Triage
    "motivo_consulta",
    "sintoma_principal",
    "factor_desencadenante",
    "inicio",
    "medicacion_recibida",

    # Columna 2 — Historia Clínica
    "antecedentes_personales",
    "alergias",
    "antecedentes_familiares",
    "medicacion_habitual",

    # Columna 3 — Consulta Actual
    "anamnesis",
    "examen_fisico",
    "impresion_diagnostica",
]

def make_final_summary(report_dict: Dict[str, Any], birth_date: Optional[str], overrides: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Arma el JSON 'tal cual UI' para revisión y para guardar en DB (final_summary).
    Solo incluye las claves visibles.
    """
    out: Dict[str, str] = {}

    for k in UI_KEYS:
        if k == "fecha_nacimiento":
            out[k] = (birth_date or "").strip()
        else:
            v = ""
            if isinstance(report_dict, dict):
                v = (report_dict.get(k) or "")
            out[k] = str(v).strip()

    if overrides:
        for kk, vv in overrides.items():
            out[kk] = (vv or "").strip()

    return out

def hash_canonico(obj: Dict) -> str:
    """
    Hash estable del JSON (claves ordenadas y minificado).
    Útil para 'content_sha256'.
    """
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_embarazo(v: Optional[str]) -> str:
    """
    Devuelve 'Si', 'No', 'Desconoce' o ''.
    """
    s = (v or "").strip().lower()
    if s in {"si", "sí", "s", "y", "yes", "true", "1"}:
        return "Si"
    if s in {"no", "n", "false", "0"}:
        return "No"
    if s in {"desconoce", "desconocido", "ns/nc", "nsnc", "n/a", "na"}:
        return "Desconoce"
    return ""




