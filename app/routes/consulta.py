import flask
from flask import request, current_app, render_template, flash
import json
from dateutil.parser import isoparse

import app.services.brain as brain
from app.Model.transactions import Transactions
from app.Model.contacts import Contacts
from app.Model.events import Events

from app.routes import routes as bp # usamos el mismo blueprint "routes"
import re
from app.services import reporting

from datetime import datetime, timezone, timedelta

from app.Model.px_hce_report import PxHceReport


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
        return render_template("medico_seleccionar_telefono.html")

    contacto = Contacts().get_by_phone(tel)
    if not contacto:
        flask.flash(f"El teléfono {tel} no está registrado.", "error")
        return render_template("medico_seleccionar_telefono.html")

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

        return render_template(
            "paciente_consultas.html",
            telefono=tel,
            sesiones=sesiones_formateadas
        )


    # 3.4 Mostrar Q/A de la transacción



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
    encounter_started_at = datetime.now(tz=timezone(timedelta(hours=-3))).isoformat()

    # Siempre plantilla nueva (3 columnas, estilos unificados)
    return render_template(
        "consulta_v2.html",
        # si no usás "interacciones" en v2 podés quitarlo, no estorba
        interacciones=interacciones,
        cards=cards,
        telefono=tel,
        txid=txid,
        encounter_started_at=encounter_started_at,
        clinician_name="Virginia Fux",
        clinician_license="MP123",
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
from flask import request, render_template
from app.services import reporting  # helpers que ya definiste (UI_KEYS, build_vitals_dict, etc.)
import json

@bp.post("/consulta/revisar")
def revisar():
    form = request.form

    # 1) Reconstruir dict “tal cual UI” (solo claves de la UI)
    report_dict = {k: form.get(k, "") for k in reporting.UI_KEYS}

    # 2) Síntomas asociados como lista normalizada
    assoc_list = reporting.normalize_associated_symptoms(form.get("sintomas_asociados"))

    # 3) Snapshot final + hash canónico (SIN signos vitales, sin overrides)
    birth_date = form.get("fecha_nacimiento") or form.get("birth_date")
    final_summary = reporting.make_final_summary(report_dict, birth_date)
    content_sha256 = reporting.hash_canonico(final_summary)

    # 4) Render de la pantalla de revisión (AÚN NO guardamos)
    return render_template(
        "review.html",
        tx_id=form.get("tx_id"),
        encounter_started_at=form.get("encounter_started_at"),
        clinician_name=form.get("clinician_name"),
        clinician_license=form.get("clinician_license"),
        patient_dni=form.get("patient_dni"),
        final_summary=final_summary,
        content_sha256=content_sha256,
        assoc_list=assoc_list,
    )
@bp.post("/consulta/aceptar")
def aceptar():
    form = request.form

    # Base
    now_ar = datetime.now(tz=timezone(timedelta(hours=-3))).isoformat()
    tx_id = int(form.get("tx_id"))

    # JSONs del form
    try:
        final_summary = json.loads(form.get("final_summary_json") or "{}")
    except Exception:
        final_summary = {}

    try:
        assoc_list = json.loads(form.get("associated_json") or "[]")
    except Exception:
        assoc_list = []

    # Normalizaciones
    def _parse_date(s):
        if not s: return None
        try:
            # devuelve 'YYYY-MM-DD' para columna date
            return isoparse(s).date().isoformat()
        except Exception:
            return None

    dolor_raw = (final_summary.get("dolor") or "").strip()
    pain_scale = int(dolor_raw) if dolor_raw.isdigit() else None
    pain_text  = None if pain_scale is not None else (dolor_raw or None)

    genero = final_summary.get("genero") or None
    if genero not in ("Mujer","Hombre","Otro"):
        genero = None

    embarazo = reporting.normalize_embarazo(final_summary.get("embarazo"))

    # Mapeo explícito a columnas existentes en tu tabla
    row = {
        # Identificación / encuentro / profesional
        "tx_id": tx_id,
        "encounter_started_at": form.get("encounter_started_at") or now_ar,
        "encounter_ended_at": now_ar,
        "clinician_name":    form.get("clinician_name") or "Virginia Fux",
        "clinician_license": form.get("clinician_license") or "MP123",

        # Paciente
        "patient_dni": form.get("patient_dni"),
        "birth_date":  _parse_date(final_summary.get("fecha_nacimiento")),
        "genero":      genero,

        # Núcleo clínico (columnas en inglés de tu tabla)
        "chief_complaint":     final_summary.get("motivo_consulta") or None,
        "main_symptom":        final_summary.get("sintoma_principal") or None,
        "associated_symptoms": assoc_list,  # jsonb
        "trigger_factor":      final_summary.get("factor_desencadenante") or None,
        "onset_text":          final_summary.get("inicio") or None,
        "evolucion":           final_summary.get("evolucion") or None,
        "meds_taken_prior":    final_summary.get("medicacion_recibida") or None,
        "pain_scale":          pain_scale,
        "pain_text":           pain_text,
        "triage_text":         final_summary.get("triage") or None,
        "physical_exam":       final_summary.get("examen_fisico") or None,

        # Antecedentes
        "personal_history":      final_summary.get("antecedentes_personales") or None,
        "family_history":        final_summary.get("antecedentes_familiares") or None,
        "surgeries":             final_summary.get("cirugias_previas") or None,
        "allergies":             final_summary.get("alergias") or None,
        "current_medication":    final_summary.get("medicacion_habitual") or None,
        "pregnancy_status":      embarazo or None,
        "immunizations_summary": final_summary.get("vacunas") or None,

        # Campos nuevos en español
        "anamnesis":             final_summary.get("anamnesis") or None,
        "impresion_diagnostica": final_summary.get("impresion_diagnostica") or None,

        # Snapshots / integridad
        "final_summary": final_summary,      # jsonb (tu columna se llama así)
        "content_sha256": form.get("content_sha256"),
    }

    # Limpia None/""/[] si tu modelo no los tolera
    row = {k: v for k, v in row.items() if v not in (None, "", [])}

    repo = PxHceReport()
    saved = repo.upsert_by_tx(row)

    flash("Consulta guardada correctamente.", "success")
    return render_template(
        "save_HC.html",
        report_id=saved.get("id"),
        tx_id=saved.get("tx_id"),
    )