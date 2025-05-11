import json
from jinja2 import Environment, FileSystemLoader

def main():
    # 1) Cargar datos
    with open("datos_receta.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2) Configurar Jinja2
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=True
    )
    template = env.get_template("receta.html")

    # 3) Renderizar
    html_output = template.render(
        doctor=data["doctor"],
        paciente=data["paciente"],
        rp=data["rp"],
        diagnostico=data["diagnostico"],
        fecha=data.get("fecha", "")
    )

    # 4) Volcar a archivo
    with open("receta_generada.html", "w", encoding="utf-8") as f:
        f.write(html_output)

    print("✅ HTML generado en receta_generada.html")

if __name__ == "__main__":
    main()