# app/flows/workflows_utils.py
import re, unicodedata, json
from typing import Optional

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


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



# --------- Monto / Formato ---------

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



# app/flows/workflow_utils.py

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
    Extractor de digest clínico con guardrails anti-invención.
    - General (no asume dominios específicos).
    - Exige evidencia textual para detalles específicos; si no están -> "No informado" o formulación genérica.
    - Limita la escalada de certeza diagnóstica.
    Sugerencia al invocar el modelo: temperature=0.2, top_p=0.9
    """
    convo = (conversation_str or "").strip()

    system = (
        "Sos médico/a de urgencias. Leé la transcripción completa de un triage AI y devolvé un resumen clínico técnico y breve.\n"
        "SALIDA: EXCLUSIVAMENTE JSON VÁLIDO (sin backticks) con estas claves EXACTAS (valores string): "
        "\"chief_complaint\",\"symptoms_course\",\"clinical_assessment\",\"suggested_tests\",\"treatment_plan\".\n"
        "\n"
        "MODO ESTRICTO DE HECHOS (OBLIGATORIO):\n"
        "- Afirmá SOLO lo que esté textual o inequívocamente respaldado por la transcripción.\n"
        "- Si falta un dato (p. ej., lateralidad, segmento anatómico, mecanismo, tiempos exactos, antecedentes, valores), escribí exactamente \"No informado\" "
        "o usá formulaciones genéricas SIN inventar (p. ej., \"región afectada\", \"miembro comprometido\").\n"
        "- No escales certeza diagnóstica: síntomas ≠ diagnóstico confirmado. Usá un léxico prudente solo en clinical_assessment: "
        "\"probable\", \"posible\", \"a considerar\". NO inventes resultados ni hallazgos no mencionados.\n"
        "- No deduzcas: derecha/izquierda, nombres de huesos/órganos específicos, embarazo, comorbilidades, alergias, medicaciones, valores de signos/labs, mecanismo exacto, si no aparecen.\n"
        "- Evitá trasladar especulaciones del paciente como hechos.\n"
        "\n"
        "REGLAS DE ESTILO:\n"
        "1) Español, registro clínico, frases cortas, sin adornos.\n"
        "2) No repitas información entre campos.\n"
        "3) Si un dato no surge claro, usá EXACTAMENTE: \"No informado\".\n"
        "4) En \"suggested_tests\" NO incluyas obviedades como \"examen físico\", \"signos vitales\" ni \"laboratorio básico\".\n"
        "5) Evitá verbos vagos sin objetivo (\"controlar\", \"evaluar\"); especificá propósito (p. ej., \"analgesia IV\", \"Rx de región afectada AP y lateral\").\n"
        "6) Máximo 220 caracteres por campo.\n"
        "7) No agregues comentarios ni campos extra.\n"
        "\n"
        "CRITERIOS POR CAMPO:\n"
        "- chief_complaint: motivo principal (qué + tiempo si aparece; si no, \"No informado\").\n"
        "- symptoms_course: cronología/evolución y signos asociados presentes en el texto.\n"
        "- clinical_assessment: hipótesis y riesgos inmediatos SOLO si surgen del texto; usar léxico prudente si no hay confirmación.\n"
        "- suggested_tests: estudios que cambian conducta hoy (tipo + región/objetivo). Si región exacta no aparece, usar \"región afectada\".\n"
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