import flask
from flask import request, current_app, render_template
import json
from datetime import timedelta
from dateutil.parser import isoparse

import app.services.brain as brain
from app.Model.transactions import Transactions
from app.Model.contacts import Contacts
from app.Model.events import Events

from app.routes import routes as bp # usamos el mismo blueprint "routes"
import json
import re
from app.services import reporting


def parse_report_lines(text: str):
    """Fallback: parsea 'Campo: Valor' por líneas."""
    rows = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.search(r"[🟩🟨🟧🟥⬜]", line):
            rows.append(("Clasificación de triage", line))
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            rows.append((k.strip(), v.strip()))
        else:
            rows.append(("", line))
    return rows

def fields_from_json(data: dict):
    """Convierte el JSON esperado a pares (label, value) para la UI."""
    fields = []
    mapping = [
        ("Teléfono", "telefono"),
        ("Edad", "edad"),
        ("Género", "genero"),
        ("Motivo de consulta", "motivo_consulta"),
        ("Síntoma principal", "sintoma_principal"),
        ("Inicio", "inicio"),
        ("Evolución", "evolucion"),
        ("Medicación recibida", "medicacion_recibida"),
        ("Síntomas asociados", "sintomas_asociados"),
        ("Factor desencadenante", "factor_desencadenante"),
        ("Dolor", "dolor"),
        ("Antecedentes personales", "antecedentes_personales"),
        ("Antecedentes familiares relevantes", "antecedentes_familiares"),
        ("Cirugías previas", "cirugias_previas"),
        ("Alergias", "alergias"),
        ("Medicación habitual", "medicacion_habitual"),
        ("Embarazo", "embarazo"),
        ("Vacunas", "vacunas"),
    ]
    for label, key in mapping:
        val = data.get(key, None)
        if val not in (None, "", []):
            fields.append((label, str(val)))

    sv = data.get("signos_vitales") or {}
    if any(sv.get(k) not in (None, "", []) for k in ("temperatura_c", "fc_lpm", "fr_rpm")):
        sv_str = f'T° {sv.get("temperatura_c","N/A")}°C, FC {sv.get("fc_lpm","N/A")} lpm, FR {sv.get("fr_rpm","N/A")} rpm'
        fields.append(("Signos vitales", sv_str))

    tr = data.get("triage") or {}
    barra = tr.get("barra")
    etiqueta = tr.get("etiqueta")
    nivel = tr.get("nivel")
    if barra or etiqueta or nivel:
        extra = f' (Nivel ESI: {nivel})' if isinstance(nivel, int) else ""
        fields.append(("Clasificación de triage", f'{(barra or "").strip()} {(etiqueta or "").strip()}{extra}'.strip()))

    return fields

def try_parse_fields_from_assistant(content: str):
    """Intenta JSON → si falla, cae a las líneas."""
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return fields_from_json(data)
    except Exception:
        pass
    # fallback legado
    return parse_report_lines(content)

def _consulta():
    current_app.logger.info(
        f"[CONSULTA] method={request.method} args={request.args.to_dict()} form={request.form.to_dict()}"
    )

    # 2) Feedback POST
    if request.method == "POST" and request.form.get("rating") is not None:
        tel  = request.form.get("tel", "").strip()
        txid = request.form.get("txid")
        try:
            rating     = int(request.form.get("rating", 0))
            comentario = request.form.get("comment", "").strip()
        except ValueError:
            flask.flash("Puntuación inválida", "error")
            return flask.redirect(flask.url_for("routes.index", tel=tel, txid=txid))

        tx = Transactions()
        try:
            tx.update(id=int(txid), puntuacion=rating, comentario=comentario)
            flask.flash("¡Gracias por tu feedback!", "success")
        except Exception:
            current_app.logger.exception("Error guardando feedback:")
            flask.flash("No se pudo guardar tu feedback", "error")

        current_app.logger.info(
            f"Feedback registrado: tx={txid}, tel={tel}, rating={rating}, comment={comentario}"
        )
        return render_template("feedback_thanks.html")

    # 3) Flujo GET
    tel  = request.values.get("tel", "").strip()
    txid = request.values.get("txid")

    if not tel:
        return render_template("index.html", step="phone")

    contacto = Contacts().get_by_phone(tel)
    if not contacto:
        flask.flash(f"El teléfono {tel} no está registrado.", "error")
        return render_template("index.html", step="phone")

    if not txid:
        sesiones = Transactions().get_by_contact_id(contacto.contact_id)
        sesiones.sort(key=lambda s: s.timestamp, reverse=True)

        sesiones_formateadas = []
        for s in sesiones:
            raw_ts = s.timestamp
            dt = isoparse(raw_ts) if isinstance(raw_ts, str) else raw_ts
            dt_ajustada = dt - timedelta(hours=3)  # (puede migrar a zoneinfo)
            sesiones_formateadas.append({
                "id": s.id,
                "timestamp": dt_ajustada.strftime("%Y-%m-%d | %H:%M")
            })

        return render_template("index.html", step="select", telefono=tel, sesiones=sesiones_formateadas)

    # 3.4 Mostrar Q/A de la transacción
    '''
    ev = Events()
    contexto_copilot = ev.get_assistant_by_event_id(1)
    conversation_history = [{"role": "system", "content": contexto_copilot}]

    convo_str = Transactions().get_conversation_by_id(txid) or "[]"
    conversation_history.append({"role": "assistant", "content": convo_str})

    convo_str = brain.ask_openai(conversation_history)
    try:
        parsed = json.loads(convo_str)
    except json.JSONDecodeError:
        current_app.logger.warning(f"JSON inválido desde OpenAI, uso texto plano: {convo_str!r}")
        parsed = convo_str

    messages = _normalize_messages(parsed)
    interacciones = [m for m in messages if m.get("role") in ("assistant", "user")]

    return render_template("index.html", step="qa", interacciones=interacciones, telefono=tel, txid=txid)
'''
    ev = Events()
    contexto_copilot = ev.get_assistant_by_event_id(1)  # prompt en Supabase que exige JSON

    # 1) Traer la conversación guardada (string JSON)
    convo_str = Transactions().get_conversation_by_id(txid) or "[]"

    # 2) Construir "interacciones" para la vista QA
    try:
        convo_list = json.loads(convo_str)
    except Exception:
        convo_list = []
    interacciones = []
    for m in convo_list:
        role = (m.get("role") or "").lower()
        if role in ("assistant", "user"):
            interacciones.append({
                "role": role,
                "content": m.get("content") or ""
            })

    # 3) Pedir el reporte al modelo (salida JSON) y armar cards
    conversation_history = [
        {"role": "system", "content": contexto_copilot},
        {"role": "user", "content": convo_str},
    ]
    report_dict, cards = reporting.build_report_cards(
        conversation_history=conversation_history,
        brain=brain,            # 
        model="gpt-4.1",
        temperature=0.0
    )

    # 4) Render: seguimos en QA, pero pasamos también "cards" para pintarlas bajo el H1
    return render_template(
        "index.html",
        step="qa",
        interacciones=interacciones,
        cards=cards,
        telefono=tel,   # <- asegúrate de que "tel" exista arriba; si es "telefono", usa ese nombre
        txid=txid,
    )

@bp.route("/consulta", methods=["GET"])
def index():
    return _consulta()

@bp.route("/consulta", methods=["POST"])
def feedback():
    return _consulta()


def _normalize_messages(raw):
    """Devuelve list[{'role':..,'content':..}] a partir de distintos formatos."""
    if isinstance(raw, dict) and "messages" in raw and isinstance(raw["messages"], list):
        raw = raw["messages"]

    if isinstance(raw, list) and raw and isinstance(raw[0], dict):
        out = []
        for item in raw:
            if not isinstance(item, dict):
                out.append({"role": "assistant", "content": str(item)})
            else:
                role = item.get("role") or "assistant"
                content = item.get("content")
                if isinstance(content, (dict, list)):
                    content = json.dumps(content, ensure_ascii=False)
                if content is None:
                    content = ""
                out.append({"role": role, "content": str(content)})
        return out

    if isinstance(raw, list) and (not raw or isinstance(raw[0], str)):
        return [{"role": "assistant", "content": s} for s in raw]

    if isinstance(raw, str):
        return [{"role": "assistant", "content": raw}]

    return []
