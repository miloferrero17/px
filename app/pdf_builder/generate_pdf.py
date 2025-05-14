from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
import requests
from io import BytesIO

def generate_recipe_pdf_from_data(
    doctor: dict,
    paciente: dict,
    rp: list,
    diagnostico: str,
    fecha: str,
    output_pdf: str = "tmp/receta.pdf"
) -> str:
    """
    Genera un PDF de receta médica usando ReportLab.
    """

    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottom=2*cm
    )

    styles = getSampleStyleSheet()
    heading = ParagraphStyle("heading", parent=styles["Heading2"], spaceAfter=12)
    story = []

    # Logo (si hay URL válida)
    if doctor.get("logo_url"):
        try:
            response = requests.get(doctor["logo_url"])
            logo = ImageReader(BytesIO(response.content))
            story.append(Image(logo, width=5*cm, height=5*cm))
            story.append(Spacer(1, 12))
        except Exception as e:
            story.append(Paragraph("⚠️ Error al cargar el logo", styles["Normal"]))

    # Título
    story.append(Paragraph("RECETA MÉDICA", styles["Title"]))
    story.append(Spacer(1, 12))

    # Datos del médico
    story.append(Paragraph(f"<b>Dr. {doctor['nombre']}</b>", styles["Heading3"]))
    story.append(Paragraph(f"{doctor['especialidad']}", styles["Normal"]))
    story.append(Paragraph(f"Matrícula: {doctor['matricula']}", styles["Normal"]))
    story.append(Paragraph(f"Email: {doctor['email']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Datos del paciente
    story.append(Paragraph(f"<b>Paciente:</b> {paciente['nombre']}", styles["Normal"]))
    story.append(Paragraph(f"DNI: {paciente['dni']}", styles["Normal"]))
    story.append(Paragraph(f"Sexo: {paciente['sexo']}", styles["Normal"]))
    story.append(Paragraph(f"Fecha de nacimiento: {paciente['fecha_nac']}", styles["Normal"]))
    story.append(Paragraph(f"Obra social: {paciente['obra_social']} - Plan: {paciente['plan']}", styles["Normal"]))
    story.append(Paragraph(f"Credencial: {paciente['credencial']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Diagnóstico
    story.append(Paragraph(f"<b>Diagnóstico:</b> {diagnostico}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Indicaciones
    story.append(Paragraph("<b>Rp:</b>", styles["Heading3"]))
    for item in rp:
        story.append(Paragraph(f"- {item}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Fecha
    story.append(Paragraph(f"Fecha: {fecha}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Descargo de responsabilidad
    #story.append(Paragraph("<i>Esta orientación no sustituye la consulta médica presencial.</i>", styles["Normal"]))

    # Generar PDF
    doc.build(story)
    return output_pdf


if __name__ == "__main__":
    doctor = {
        "nombre": "Agustin Fernandez Viña",
        "especialidad": "MÉDICO ESPECIALISTA EN DIAGNÓSTICO",
        "matricula": "140.100",
        "email": "agustinfvinadxi@gmail.com",
        "logo_url": "https://web.innovamed.com.ar/hubfs/LOGO%20A%20COLOR%20SOLO-2.png"
    }

    paciente = {
        "nombre": "EMILIO  FERRERO",
        "dni": "32359799",
        "sexo": "Masculino",
        "fecha_nac": "17/05/1986",
        "obra_social": "OSDE",
        "plan": "450",
        "credencial": "62028536101"
    }

    rp = [
        "Radiografia de tobillo",
        "Ecodopler color de vasos de cuello."
    ]

    diagnostico = "ACV"
    fecha = "21/04/2025"

    path = generate_recipe_pdf_from_data(doctor, paciente, rp, diagnostico, fecha)
    print(f"✅ Receta generada en: {path}")

'''


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

def generate_recipe_pdf_from_data(
    doctor: dict,
    paciente: dict,
    rp: list,
    diagnostico: str,
    fecha: str,
    output_pdf: str = "tmp/receta.pdf"  # en Lambda sólo /tmp
) -> str:
    """
    Genera un PDF de receta médica usando ReportLab (pure-Python).
    """
    # 1) Configuro documento
    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    # si querés otro estilo
    heading = ParagraphStyle(
        "heading", parent=styles["Heading2"], spaceAfter=12
    )

    story = []
    # Título
    story.append(Paragraph("RECETA MÉDICA", styles["Title"]))
    story.append(Spacer(1, 12))

    # Datos del doctor
    story.append(Paragraph(
        f"<b>Dr. {doctor['nombre']}</b> — {doctor['especialidad']} (Matrícula: {doctor['matricula']})",
        styles["Normal"]
    ))
    story.append(Paragraph(f"Email: {doctor.get('email','')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Datos del paciente
    story.append(Paragraph(f"<b>Paciente:</b> {paciente['nombre']}", styles["Normal"]))
    story.append(Paragraph(f"DNI: {paciente['dni']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Prescripciones
    story.append(Paragraph("Prescripciones:", heading))
    for item in rp:
        story.append(Paragraph(f"• {item}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Diagnóstico y fecha
    story.append(Paragraph(f"<b>Diagnóstico:</b> {diagnostico}", styles["Normal"]))
    story.append(Paragraph(f"<b>Fecha:</b> {fecha}", styles["Normal"]))

    # 4) Creo el PDF
    doc.build(story)
    return output_pdf
'''
