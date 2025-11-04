from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from .models import db, User # Importamos 'db' y 'User' desde models

# Inicializamos las extensiones pero sin app
bcrypt = Bcrypt()
login_manager = LoginManager()

# Configuración de Flask-Login
login_manager.login_view = 'auth.login' # 'auth' es el nombre del Blueprint
login_manager.login_message_category = 'info'
login_manager.login_message = 'Por favor, inicie sesión para acceder a esta página.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_app():
    """
    Esta es la "Application Factory".
    Crea y configura la instancia de la app Flask.
    """
    app = Flask(__name__)

    # Configuración de la Base de Datos
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Nahuel@localhost:5432/negocio_db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'una_llave_secreta_muy_dificil'

    # Inicializa las extensiones CON la app
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # --- Registrar Blueprints (los módulos) ---
    
    # Importamos los blueprints aquí para evitar importación circular
    from .auth import auth_bp
    from .main import main_bp
    from .jornadas import jornadas_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(jornadas_bp)

    with app.app_context():
        # Crea todas las tablas si no existen
        db.create_all()

    return app