import os
import json
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generate_recipe_pdf_from_data(
    doctor: dict,
    paciente: dict,
    rp: list,
    diagnostico: str,
    fecha: str,
    # quitamos el default "templates", ya no lo vamos a usar
    template_name: str = "receta.html",
    output_pdf: str = "receta.pdf"
) -> str:
    """
    Genera un PDF de la receta médica a partir de los datos pasados como argumentos.
    """

    # 1) calculo dónde está app/templates
    #    __file__ = .../app/pdf_builder/generate_pdf.py
    base_dir     = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    template_dir = os.path.join(base_dir, "templates")

    if not os.path.isdir(template_dir):
        raise RuntimeError(f"No encuentro la carpeta de plantillas en: {template_dir}")

    # 2) inicializo Jinja apuntando a app/templates
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True
    )
    template = env.get_template(template_name)

    # 3) renderizo HTML
    html_content = template.render(
        doctor=doctor,
        paciente=paciente,
        rp=rp,
        diagnostico=diagnostico,
        fecha=fecha
    )

    # 4) genero el PDF
    HTML(string=html_content).write_pdf(output_pdf)
    print(f"✅ PDF generado en {output_pdf}")
    return output_pdf


def generate_recipe_pdf(
    json_path: str = "datos_receta.json",
    template_name: str = "receta.html",
    output_pdf: str = "receta.pdf"
) -> str:
    """
    Carga datos desde JSON y llama a generate_recipe_pdf_from_data.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return generate_recipe_pdf_from_data(
        doctor=data.get("doctor", {}),
        paciente=data.get("paciente", {}),
        rp=data.get("rp", []),
        diagnostico=data.get("diagnostico", ""),
        fecha=data.get("fecha", ""),
        template_name=template_name,
        output_pdf=output_pdf
    )


if __name__ == "__main__":
    # Ejemplo de uso
    sample_doctor = {
        "nombre": "EMILIO FERRERO",
        "especialidad": "MÉDICO CARDIOLOGO",
        "matricula": "140.100",
        "email": "milonguitaferrero@gmail.com",
        "logo_url": "https://web.innovamed.com.ar/hubfs/LOGO%20A%20COLOR%20SOLO-2.png"
    }
    sample_paciente = {
        "nombre": "FRANCISCO PEREZ",
        "dni": "32359799",
        "sexo": "Masculino",
        "fecha_nac": "17/05/1986",
        "obra_social": "OSDE",
        "plan": "450",
        "credencial": "62028536101"
    }
    sample_rp = ["Rayos X de Tobillos."]
    sample_diagnostico = "Torcedura de tobillo"
    sample_fecha = "21/04/2025"

    generate_recipe_pdf_from_data(
        doctor=sample_doctor,
        paciente=sample_paciente,
        rp=sample_rp,
        diagnostico=sample_diagnostico,
        fecha=sample_fecha,
        output_pdf="app/temp/receta_eje.pdf"
    )

