from flask import Blueprint

routes = Blueprint("routes", __name__)

# Importa los módulos para que registren sus rutas sobre este blueprint
import app.routes.whatsapp  # noqa: F401
import app.routes.consulta  # noqa: F401
