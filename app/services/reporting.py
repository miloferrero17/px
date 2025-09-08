import json
import re
from typing import Dict, List, Tuple

# Orden y etiquetas para las cards (una por campo)
# Orden y etiquetas para las cards (una por campo)
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

    ("signos_vitales", "Signos vitales"),
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

# Defaults para cualquier campo ausente o vacío
DEFAULTS = {k: "No refiere" for k, _ in SCHEMA_ORDER}
DEFAULTS.update({
    "fecha_nacimiento": "No disponible",
    "antecedentes_personales": "Niega",
    "antecedentes_familiares": "Niega",
    "cirugias_previas": "Niega",
    "embarazo": "",
    "signos_vitales": "T° N/A, FC N/A lpm, FR N/A rpm",
    "triage": "⬜⬜⬜⬜⬜ Urgencia Estimada No disponible",
})

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

def normalize_report_dict(data, schema=SCHEMA_ORDER, defaults=DEFAULTS):
    data = dict(data or {})
    report = {}
    for key, _label in schema:
        if key.startswith("__section_"):   # saltar títulos
            continue
        v = data.get(key) if isinstance(data, dict) else None
        report[key] = (v if isinstance(v, str) and v.strip() else defaults[key])
        # Normalización específica
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
    Orquestador principal:
      - Llama a OpenAI con conversation_history (system ya exige JSON en el prompt).
      - Parsea la salida a JSON robustamente.
      - Normaliza y genera cards.
    Devuelve: (report_dict, cards)
    """
    out = brain.ask_openai(conversation_history, temperature=temperature, model=model)
    data = _extract_json(out)
    report = normalize_report_dict(data)
    cards = cards_from_report(report)
    return report, cards

def build_report_cards_from_json_text(json_text: str):  #ahora no lo usamos, es para armar las cards desde algun json
    """ 
    Si ya tenés un JSON (string) de otra fuente:
      - Lo parsea, normaliza y arma cards, sin llamar a OpenAI.
    Devuelve: (report_dict, cards)
    """
    data = _extract_json(json_text)
    report = normalize_report_dict(data)
    cards = cards_from_report(report)
    return report, cards

# === Helpers para snapshot, hash y estructuración ===
from typing import Optional
import hashlib

# Claves que queremos en el snapshot "tal cual UI"
UI_KEYS = [
    "fecha_nacimiento","genero",
    "motivo_consulta","sintoma_principal","sintomas_asociados","factor_desencadenante",
    "inicio","evolucion","medicacion_recibida",
    "dolor","signos_vitales","triage",
    "examen_fisico",
    "antecedentes_personales","antecedentes_familiares","cirugias_previas",
    "alergias","medicacion_habitual","embarazo","vacunas","anamnesis",
    "impresion_diagnostica",
]

def make_final_summary(report_dict: Dict, birth_date: Optional[str], overrides: Optional[Dict[str, str]] = None) -> Dict:
    """
    Arma el JSON 'tal cual UI' para mostrar en revisión y guardar en final_summary.
    - report_dict: lo que viene del modelo + lo editado por el médico
    - birth_date: permitir setear explícito la fecha de nacimiento
    - overrides: permite forzar algún texto (p.ej. signos_vitales formateado)
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
    Útil para 'content_sha256' del final_summary.
    """
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def normalize_associated_symptoms(texto: Optional[str]) -> List[str]:
    """
    'tos, disnea; fiebre, Tos' -> ['tos','disnea','fiebre'] (sin duplicados; preserva el 1er casing visto).
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
from typing import Optional

def normalize_embarazo(v: Optional[str]) -> str:
    """
    Devuelve 'Si', 'No', 'Desconoce' o '' (vacío) si no reconoce el valor.
    Maneja acentos, mayúsculas y sinónimos obvios.
    """
    s = (v or "").strip().lower()
    if s in {"si", "sí", "s", "y", "yes", "true", "1"}:
        return "Si"
    if s in {"no", "n", "false", "0"}:
        return "No"
    if s in {"desconoce", "desconocido", "ns/nc", "nsnc", "n/a", "na"}:
        return "Desconoce"
    return ""  # fuerza el placeholder "Seleccionar…"

# --- Signos vitales simplificados: JSON fijo + string legible ---

def _coerce_num(s: Optional[str], cast, lo=None, hi=None):
    if s is None:
        return None
    ss = str(s).strip()
    if ss == "":
        return None
    try:
        x = cast(ss.replace(",", "."))
    except Exception:
        return None
    # Si querés, podés validar rangos acá (lo/hi) y devolver None si no cumple.
    return x

def build_vitals_dict(
    temp_c: Optional[str] = None,
    bp_sys: Optional[str] = None,
    bp_dia: Optional[str] = None,
    fc_bpm: Optional[str] = None,
    fr_rpm: Optional[str] = None,
    spo2_pct: Optional[str] = None,
) -> Dict:
    """
    Construye un dict con claves fijas para guardar en 'vitals' (jsonb).
    Solo incluye claves con valor (omite None).
    """
    v = {
        "temp_c":  _coerce_num(temp_c, float),
        "bp_sys":  _coerce_num(bp_sys, int),
        "bp_dia":  _coerce_num(bp_dia, int),
        "fc_bpm":  _coerce_num(fc_bpm, int),
        "fr_rpm":  _coerce_num(fr_rpm, int),
        "spo2_pct":_coerce_num(spo2_pct, int),
    }
    return {k: v for k, v in v.items() if v is not None}

def format_vitals_text(v: Optional[Dict]) -> str:
    """
    Genera el texto legible para 'signos_vitales' en el final_summary.
    Muestra solo lo presente.
    """
    if not v:
        return ""
    parts: List[str] = []
    if "temp_c" in v:   parts.append(f"T° {v['temp_c']}°C")
    if "bp_sys" in v and "bp_dia" in v: parts.append(f"TA {v['bp_sys']}/{v['bp_dia']}")
    elif "bp_sys" in v: parts.append(f"TA {v['bp_sys']}/–")
    elif "bp_dia" in v: parts.append(f"TA –/{v['bp_dia']}")
    if "fc_bpm" in v:   parts.append(f"FC {v['fc_bpm']} lpm")
    if "fr_rpm" in v:   parts.append(f"FR {v['fr_rpm']} rpm")
    if "spo2_pct" in v: parts.append(f"SpO₂ {v['spo2_pct']}%")
    return ", ".join(parts)
