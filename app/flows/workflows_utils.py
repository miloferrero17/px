# app/flows/workflows_utils.py
import re, unicodedata, json
from typing import Optional

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


import json
import re
from typing import Tuple, Dict, Any, Optional

import app.services.brain as brain

# ===== Config =====
MAX_LEN = 1200               # Twilio ~1600 -> margen seguro
NO_INFO = "No informado"

# Keys estructuradas (en inglés)
JSON_KEYS = [
    "chief_complaint",    # motivo de consulta
    "symptoms_course",    # sintomatología y evolución
    "clinical_assessment",# orientación diagnóstica
    "suggested_tests",    # exámenes complementarios (sin examen físico / signos vitales / laboratorio básico)
    "treatment_plan",     # tratamiento sugerido
]

# Regex para capturar la línea EXACTA de urgencia (5 cuadrados + etiqueta)
# 🟩=U+1F7E9, 🟨=U+1F7E8, 🟧=U+1F7E7, 🟥=U+1F7E5, ⬜=U+2B1C
STRICT_URGENCY = True 
URGENCY_LINE_RE = re.compile(
    r"^(?P<line>(?:[🟥🟧🟨🟩⬜]\uFE0F?){5}\s+Urgencia Estimada[^\n\r]*)$",
    re.MULTILINE
)

def _build_extractor_messages(conversation_str: str) -> list[dict]:
    """
    Extractor de digest clínico.
    - General (no asume dominios específicos).
    - Exige evidencia textual para detalles específicos; si no están -> "No informado" o formulación genérica.
    - Limita la escalada de certeza diagnóstica.
    """
    convo = (conversation_str or "").strip()

    system = (
        "Eres un médico especialista en medicina de urgencias entrenado para procesar la transcripción de un triage AI y convertirla en un reporte médico breve y estructurado para un médico de guardia.\n"
        "SALIDA: EXCLUSIVAMENTE JSON VÁLIDO (sin backticks) con estas claves EXACTAS (valores string): "
        "\"chief_complaint\",\"symptoms_course\",\"clinical_assessment\",\"suggested_tests\",\"treatment_plan\".\n"
        "\n"
        "MODO ESTRICTO DE HECHOS (OBLIGATORIO):\n"
        "- Afirmá SOLO lo que esté textual o inequívocamente respaldado por la transcripción.\n"
        "- Si falta un dato (p. ej., lateralidad, segmento anatómico, mecanismo, tiempos exactos, antecedentes, valores), escribí \"No informado\" "
        "o usá formulaciones genéricas SIN inventar (p. ej., \"región afectada\", \"miembro comprometido\").\n"
        "- No escales certeza diagnóstica: síntomas ≠ diagnóstico confirmado. Usá un léxico prudente solo en clinical_assessment: "
        "\"probable\", \"posible\", \"a considerar\". NO inventes resultados ni hallazgos no mencionados.\n"
        "- No deduzcas: derecha/izquierda, nombres de huesos/órganos específicos, embarazo, comorbilidades, alergias, medicaciones, valores de signos/labs, mecanismo exacto, si no aparecen.\n"
        "\n"
        "REGLAS DE ESTILO:\n"
        "1) Español, registro clínico, frases cortas.\n"
        "2) No repitas información entre campos.\n"
        "3) Si un dato no surge claro, usá EXACTAMENTE: \"No informado\".\n"
        "4) En \"suggested_tests\" NO incluyas obviedades como \"examen físico\", \"signos vitales\" ni \"laboratorio básico\".\n"
        "5) Evitá verbos vagos sin objetivo (\"controlar\", \"evaluar\"); especificá propósito.\n"
        "\n"
        "CRITERIOS POR CAMPO:\n"
        "- chief_complaint: motivo principal (qué + tiempo si aparece; si no, \"No informado\").\n"
        "- symptoms_course: cronología/evolución y signos asociados presentes en el texto.\n"
        "- clinical_assessment: hipótesis y riesgos inmediatos SOLO si surgen del texto; usar léxico prudente si no hay confirmación.\n"
        "- suggested_tests: estudios complementarios para diagnosticar al paciente. Si región exacta no aparece, usar \"región afectada\".\n"
        "- treatment_plan: medidas iniciales concretas (intervención + vía + objetivo) sin asumir datos ausentes.\n"
        "\n"
        "CONSISTENCIA TÉCNICA (GENÉRICA):\n"
        "- Generalizá anatomía si faltan detalles (\"miembro afectado\", \"región afectada\").\n"
        "- No conviertas síntomas en diagnósticos confirmados sin mención explícita (p. ej., no poner \"fractura\" si nunca se menciona o confirma).\n"
        "- No inventes valores, resultados, ni antecedentes.\n"
        "Devolvé SOLO el JSON final."
    )

    user = (
        "A continuación tenés el historial completo (JSON con {role, content}). "
        "Leelo y devolvé SOLO el JSON solicitado:\n\n"
        f"{convo}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},

    ]




def _safe_load_json(text: str) -> Dict[str, Any]:
    """Carga JSON de forma robusta; si falla, retorna {}."""
    t = (text or "").strip()
    # remover posibles fences ```json ... ```
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I | re.S).strip()
    try:
        data = json.loads(t or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        # intento de extraer primer {...} balanceado
        s, e = t.find("{"), t.rfind("}")
        if s != -1 and e > s:
            try:
                data = json.loads(t[s:e+1])
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

def _extract_urgency_line(conversation_str: str) -> str:
    """
    Parsea conversation_str (JSON) → recorre SOLO mensajes del assistant →
    busca la última línea con 5 cuadrados + 'Urgencia Estimada ...' y la devuelve literal.
    """
    try:
        history = json.loads(conversation_str or "[]")
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    # Regex local: exactamente 5 cuadrados (cualquier color admitido), VS16 opcional en ⬜️
    pattern = re.compile(r"^(?:[🟥🟧🟨🟩⬜]\uFE0F?){5}\s+Urgencia Estimada[^\n\r]*", re.MULTILINE)

    for msg in reversed(history):
        if not isinstance(msg, dict):
            continue
        if (msg.get("role") or "").lower() != "assistant":
            continue
        text = (msg.get("content") or "")
        matches = pattern.findall(text)
        if matches:
            return matches[-1].strip()

    return ""


def _truncate(text: str, max_len: int = MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    truncated = text[: max_len - 1].rstrip()
    return truncated + "…"

def generar_medical_digest(conversation_str: str, national_id: Optional[str]) -> Tuple[str, Dict[str, Any]]:
    """
    Genera el digest para médicos a partir del conversation_str.
    - Usa la línea EXACTA de urgencia del reporte si está presente (no infiere).
    - Pide al LLM las secciones clínicas del digest con keys en inglés.
    - Devuelve (digest_text, digest_json).
    """
    # 1) Urgencia exacta (si existe en el reporte)
    urgency_line = _extract_urgency_line(conversation_str or "")

    # 2) Extraer secciones con LLM (temp=0 por configuración de brain)
    messages = _build_extractor_messages(conversation_str or "[]")
    raw = brain.ask_openai(messages)  # temperatura por defecto 0
    data = _safe_load_json(raw)

    # 3) Normalización y defaults
    values: Dict[str, str] = {}
    for k in JSON_KEYS:
        v = (data.get(k) or "").strip()
        if not v or v.lower() in {"none", "null", "n/a"}:
            v = NO_INFO
        # Filtrado leve en suggested_tests por si el modelo se cuela
        if k == "suggested_tests":
            v = re.sub(r"\b(examen\s+físico|examen\s+fisico|signos\s+vitales)\b", "", v, flags=re.I).strip()
            if not v:
                v = NO_INFO
        values[k] = v

    dni = (national_id or "").strip() or NO_INFO

    # 4) Render del mensaje (ES) con título y bloques
    bold = lambda t: f"*{t}*"

    blocks = [
        bold("Resumen Médico"),
        f"{bold('DNI:')} {dni}",
        urgency_line,
        f"{bold('Motivo de consulta:')} {values['chief_complaint']}",
        f"{bold('Sintomatología y evolución:')} {values['symptoms_course']}",
        f"{bold('Orientación diagnóstica:')} {values['clinical_assessment']}",
        f"{bold('Exámenes complementarios:')} {values['suggested_tests']}",
        f"{bold('Tratamiento sugerido:')} {values['treatment_plan']}",
    ]

    digest_text = _truncate("\n\n".join(blocks), MAX_LEN)
    # 5) JSON estructurado (keys en inglés)
    digest_json: Dict[str, Any] = {
        "national_id": dni,
        "urgency_line": urgency_line,
        "chief_complaint": values["chief_complaint"],
        "symptoms_course": values["symptoms_course"],
        "clinical_assessment": values["clinical_assessment"],
        "suggested_tests": values["suggested_tests"],
        "treatment_plan": values["treatment_plan"],
    }

    return digest_text, digest_json



from typing import Optional

def get_last_question_index(conversation_history, max_preguntas_str: str, offtopic_notice: Optional[str] = None,):    
    """
    Devuelve el índice en conversation_history del último mensaje del asistente
    que contiene una línea con formato 'N/max_preguntas - ...'.

    Si se pasa offtopic_notice, se IGNORAN los mensajes del asistente que contengan
    ese texto (por ejemplo, los avisos de "Para poder continuar..."), para que
    siempre tome la última "pregunta pura" como referencia.

    Si no encuentra nada, devuelve None.
    """
    prefix_pattern = re.compile(r"^\d+/" + re.escape(max_preguntas_str) + r" - ")

    for idx in range(len(conversation_history) - 1, -1, -1):
        msg = conversation_history[idx]
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue

        content = (msg.get("content") or "").strip()

        # Ignorar mensajes de aviso off-topic (que también incluyen la pregunta numerada)
        if offtopic_notice and offtopic_notice in content:
            continue

        for line in content.splitlines():
            line = line.strip()
            if prefix_pattern.match(line):
                return idx

    return None
