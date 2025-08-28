# scripts/test_px_hce_report.py
import os, sys, json, random, time
from datetime import datetime, timezone, timedelta

# Asegura que el import encuentre "app"
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from app.Model.px_hce_report import PxHceReport  # usa tu modelo

def main():
    repo = PxHceReport()

    # Un tx_id de prueba (cambialo si querés correr varias veces)
    tx_id = 99001 + random.randint(0, 999)

    row = {
        "contact_id": None,                   # usá un contact_id válido de tu DB, si tenés
        "tx_id": 277,
        "patient_dni": "35123456",
        "birth_date": "1992-04-10",
        "genero": "Mujer",

        "encounter_class": "emergency",
        # Fechas con offset -03:00 (CABA). Lambda suele estar en UTC; acá da igual, es prueba:
        "encounter_started_at": datetime.now(tz=timezone(timedelta(hours=-3))).isoformat(),
        "encounter_ended_at":   None,  # probamos null en el primer insert

        "clinician_name": "Virginia Fux",
        "clinician_license": "MP123",

        "chief_complaint": "Dolor abdominal",
        "main_symptom": "Dolor en FID",
        "associated_symptoms": ["náuseas", "fiebre"],  # LIST → JSONB
        "trigger_factor": "Ingesta copiosa",
        "onset_text": "Hace 6 horas",
        "evolucion": "Empeorando",
        "meds_taken_prior": "Paracetamol 1g",
        "pain_scale": 7,
        "pain_text": None,
        "vitals": {"temp_c": 38.1, "fc_bpm": 96, "fr_rpm": 18, "spo2_pct": 98},  # DICT → JSONB
        "triage_text": "🟨 Urgencia baja",
        "physical_exam": "Dolor a la palpación en FID",

        "personal_history": "Niega",
        "family_history": "Niega",
        "surgeries": "Apendicectomía 2015",
        "allergies": "Penicilina",
        "current_medication": "Ibuprofeno esporádico",
        "pregnancy_status": "No",
        "immunizations_summary": "Esquema completo",

        # Snapshot + hash (para la prueba mandamos algo mínimo)
        "final_summary": {"motivo_consulta":"Dolor abdominal","sintoma_principal":"Dolor en FID"},
        "content_sha256": "hash_de_prueba_" + str(tx_id),
    }

    print("▶️  UPSERT #1 (INSERT esperado)…")
    res1 = repo.upsert_by_tx(row)
    print("Respuesta:", json.dumps(res1, ensure_ascii=False, indent=2))

    # Simulamos un cambio y el segundo upsert (UPDATE esperado, misma fila por tx_id)
    time.sleep(0.5)
    row["vitals"]["fc_bpm"] = 98
    row["encounter_ended_at"] = datetime.now(tz=timezone(timedelta(hours=-3))).isoformat()
    row["content_sha256"] = "hash_de_prueba_cambiado_" + str(tx_id)

    print("\n▶️  UPSERT #2 (UPDATE esperado)…")
    res2 = repo.upsert_by_tx(row)
    print("Respuesta:", json.dumps(res2, ensure_ascii=False, indent=2))

    print(f"\n✅ Probá en Supabase Table Editor: debería existir UNA sola fila con tx_id={tx_id}, con fc_bpm=98 y encounter_ended_at seteado.")

if __name__ == "__main__":
    main()
