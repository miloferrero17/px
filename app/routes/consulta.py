import flask
from flask import request, current_app, render_template, flash, redirect, url_for
import json
from dateutil.parser import isoparse

import app.services.brain as brain
from app.Model.transactions import Transactions
from app.Model.contacts import Contacts
from app.Model.events import Events

from app.routes import routes as bp # usamos el mismo blueprint "routes"
from app.services import reporting

from datetime import datetime, timezone, timedelta

from app.Model.px_hce_report import PxHceReport


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
            flash("Puntuación inválida", "error")
            return flask.redirect(flask.url_for("routes.index", tel=tel, txid=txid))

        tx = Transactions()
        try:
            tx.update(id=int(txid), puntuacion=rating, comentario=comentario)
            flash("¡Gracias por tu feedback!", "success")
        except Exception:
            current_app.logger.exception("Error guardando feedback:")
            flash("No se pudo guardar tu feedback", "error")

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
        flash(f"El teléfono {tel} no está registrado.", "error")
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




@bp.post("/consulta/revisar")
def revisar():
    form = request.form

    # 1) Reconstruir dict “tal cual UI” (solo claves de la UI)
    report_dict = {k: form.get(k, "") for k in reporting.UI_KEYS}


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


    # Normalizaciones
    def _parse_date(s):
        if not s: return None
        try:
            # devuelve 'YYYY-MM-DD' para columna date
            return isoparse(s).date().isoformat()
        except Exception:
            return None
    # Sanitizar 'genero' para cumplir el CHECK de la tabla
    allowed_generos = {"Mujer", "Hombre", "Otro"}
    raw_genero = (final_summary.get("genero") or "").strip()
    genero_clean = raw_generos = raw_genero if raw_genero in allowed_generos else None


    # Mapeo explícito a columnas existentes en tu tabla
    row = {
        # Identificación / encuentro / profesional
        "tx_id": tx_id,
        "encounter_started_at": form.get("encounter_started_at") or now_ar,
        "encounter_ended_at": now_ar,
        "clinician_name":    form.get("clinician_name") or "Virginia Fux",
        "clinician_license": form.get("clinician_license") or "MP123",

        # Paciente (header del HTML)
        "birth_date":  _parse_date(final_summary.get("fecha_nacimiento")),  # viene del hidden
        "genero":      genero_clean,

        # TRIAGE (solo si querés persistir lo que se ve arriba; en el HTML no es editable)
        # Si no lo querés guardar, borrá esta línea:
        # "triage": final_summary.get("triage") or None,

        # === Campos editables de la UI (coinciden con name= del HTML) ===
        # Columna 1 — Información Triage
        "motivo_consulta":       final_summary.get("motivo_consulta") or None,
        "sintoma_principal":     final_summary.get("sintoma_principal") or None,
        "factor_desencadenante": final_summary.get("factor_desencadenante") or None,
        "inicio":                final_summary.get("inicio") or None,
        "medicacion_recibida":   final_summary.get("medicacion_recibida") or None,

        # Columna 2 — Historia Clínica
        "antecedentes_personales":     final_summary.get("antecedentes_personales") or None,
        "alergias":                    final_summary.get("alergias") or None,
        "antecedentes_familiares":     final_summary.get("antecedentes_familiares") or None,
        "medicacion_habitual":         final_summary.get("medicacion_habitual") or None,

        # Columna 3 — Consulta Actual
        "anamnesis":             final_summary.get("anamnesis") or None,
        "examen_fisico":         final_summary.get("examen_fisico") or None,
        "impresion_diagnostica": final_summary.get("impresion_diagnostica") or None,

        # Snapshots / integridad
        "final_summary": final_summary,                     # jsonb
        "content_sha256": form.get("content_sha256"),
    }
    # Limpieza de valores vacíos (si tu modelo no los tolera)
    row = {k: v for k, v in row.items() if v not in (None, "", [])}

    repo = PxHceReport()
    saved = repo.upsert_by_tx(row)

    flash("Consulta guardada correctamente.", "success")
    return render_template(
        "save_HC.html",
        report_id=saved.get("id"),
        tx_id=saved.get("tx_id"),
    )