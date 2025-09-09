import json
import re
import hashlib
from typing import Dict, List, Tuple, Optional

# === Esquema para ordenar/rotular cards ===================================
SCHEMA_ORDER: List[Tuple[str, str]] = [
    ("fecha_nacimiento", "Fecha de nacimiento"),
    ("genero", "Género"),

    ("__section_consulta", "Consulta actual"),

    ("motivo_consulta", "Motivo de consulta"),
    ("sintoma_principal", "Síntoma principal"),
    ("sintomas_asociados", "Síntomas asociados"),
    ("factor_desencadenante", "Factor desencadenante"),

    ("inicio", "Inicio"),
    ("evolucion", "Evolución del cuadro"),

    ("medicacion_recibida", "Medicación recibida"),
    ("dolor", "Dolor"),

    ("triage", "Clasificación de triage"),

    ("__section_examenfisico", "Examen Físico"),
    ("examen_fisico", "Examen Físico"),

    ("__section_antecedentes", "Antecedentes del paciente"),
    ("antecedentes_personales", "Antecedentes personales"),
    ("antecedentes_familiares", "Antecedentes familiares relevantes"),
    ("cirugias_previas", "Cirugías previas"),
    ("alergias", "Alergias"),
    ("medicacion_habitual", "Medicación habitual"),
    ("embarazo", "Embarazo"),
    ("vacunas", "Vacunas"),
]

# === Defaults ==============================================================
DEFAULTS = {k: "No refiere" for k, _ in SCHEMA_ORDER}
DEFAULTS.update({
    "fecha_nacimiento": "No disponible",
    "antecedentes_personales": "Niega",
    "antecedentes_familiares": "Niega",
    "cirugias_previas": "Niega",
    "embarazo": "",
    "triage": "⬜⬜⬜⬜⬜ Urgencia Estimada No disponible",
})

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
def normalize_report_dict(data, schema=SCHEMA_ORDER, defaults=DEFAULTS):
    data = dict(data or {})
    report: Dict[str, str] = {}
    for key, _label in schema:
        if key.startswith("__section_"):
            continue
        v = data.get(key) if isinstance(data, dict) else None
        report[key] = (v if isinstance(v, str) and v.strip() else defaults[key])
    if "embarazo" in report:
        report["embarazo"] = normalize_embarazo(report.get("embarazo"))
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
    report = normalize_report_dict(data)
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
    "fecha_nacimiento","genero",
    "motivo_consulta","sintoma_principal","sintomas_asociados","factor_desencadenante",
    "inicio","evolucion","medicacion_recibida",
    "dolor","triage",
    "examen_fisico",
    "antecedentes_personales","antecedentes_familiares","cirugias_previas",
    "alergias","medicacion_habitual","embarazo","vacunas","anamnesis",
    "impresion_diagnostica",
]

def make_final_summary(report_dict: Dict, birth_date: Optional[str], overrides: Optional[Dict[str, str]] = None) -> Dict:
    """
    Arma el JSON 'tal cual UI' que se muestra en revisión y se guarda en la DB
    dentro de la columna jsonb (p.ej. final_summary_json). No expandir a columnas.
    """
    out: Dict[str, str] = {}
    for k in UI_KEYS:
        if k == "fecha_nacimiento":
            out[k] = (birth_date or "").strip()
        else:
            val = ""
            if isinstance(report_dict, dict):
                val = (report_dict.get(k) or "")
            out[k] = str(val).strip()
    if overrides:
        for kk, vv in overrides.items():
            out[kk] = (vv or "").strip()
    if "embarazo" in out:
        out["embarazo"] = normalize_embarazo(out.get("embarazo"))
    return out

def hash_canonico(obj: Dict) -> str:
    """
    Hash estable del JSON (claves ordenadas y minificado).
    Útil para 'content_sha256'.
    """
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def normalize_associated_symptoms(texto: Optional[str]) -> List[str]:
    """
    'tos, disnea; fiebre, Tos' -> ['tos','disnea','fiebre']
    """
    if not texto:
        return []
    parts = re.split(r"[;,]", texto)
    clean: List[str] = []
    seen = set()
    for p in parts:
        s = p.strip()
        if not s:
            continue
        key = s.lower()
        if key not in seen:
            seen.add(key)
            clean.append(s)
    return clean

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



