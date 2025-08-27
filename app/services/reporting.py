import json
import re
from typing import Dict, List, Tuple

# Orden y etiquetas para las cards (una por campo)
SCHEMA_ORDER: List[Tuple[str, str]] = [
    ("edad", "Edad"),
    ("genero", "Género"),

    ("__section_consulta", "Consulta actual"), #nuevo

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


    ("__section_antecedentes", "Antecedentes del paciente"), #nuevo


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
    "antecedentes_personales": "Niega",
    "antecedentes_familiares": "Niega",
    "cirugias_previas": "Niega",
    "embarazo": "Desconoce",
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
