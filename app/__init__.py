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

'''
# app/__init__.py
from flask import Flask

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",  # apunta a tu carpeta de Jinja2
        static_folder="static"       # apunta a tu carpeta de CSS/JS/Imágenes
    )

    # Importás y registrás las rutas (blueprint)
    from app.routes import routes
    app.register_blueprint(routes)

    return app

# Esto permite hacer `from app import app` en serverless-wsgi
app = create_app()


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

# app/__init__.py
from flask import Flask

def create_app():
    app = Flask(
        __name__,
        template_folder="templates",  # apunta a tu carpeta de Jinja2
        static_folder="static"       # apunta a tu carpeta de CSS/JS/Imágenes
    )

    # Importás y registrás las rutas (blueprint)
    from app.routes import routes
    app.register_blueprint(routes)

    return app

# Esto permite hacer `from app import app` en serverless-wsgi
app = create_app()



# app/__init__.py
from flask import Flask

def create_app():
    app = Flask(__name__)

    # Importás el blueprint y lo registrás
    from app.routes import routes
    app.register_blueprint(routes)

    return app

# Esto permite que `from app import app` funcione
app = create_app()

from flask import Flask

app = Flask(__name__)

# Importar las rutas y registrar el blueprint
from app.routes import routes
app.register_blueprint(routes)
'''