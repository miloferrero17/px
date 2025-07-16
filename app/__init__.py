# app/__init__.py
from flask import Flask

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    # clave directa en código
    app.secret_key = "Francisco.17"

    from app.routes import routes
    app.register_blueprint(routes)
    return app

app = create_app()
