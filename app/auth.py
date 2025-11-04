from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from sqlalchemy.exc import IntegrityError
# Importamos db, User, y bcrypt (desde __init__.py)
from .models import db, User 
from . import bcrypt 

# Creamos el Blueprint
auth_bp = Blueprint('auth', __name__)

# --- RUTA DE LOGIN (Sin cambios) ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index')) # 'main' es el nombre del Blueprint
    
   # ... (dentro de la función login() en app/auth.py) ...
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        # --- LÓGICA DE LOGIN MEJORADA ---
        if user:
            # 1. ¿Está activa la cuenta?
            if not user.is_active:
                flash('Tu cuenta ha sido desactivada. Contacta a un administrador.', 'danger')
            # 2. ¿Es la contraseña correcta?
            elif bcrypt.check_password_hash(user.password_hash, password):
                login_user(user)
                flash(f'¡Bienvenido de nuevo, {user.username}!', 'success')
                return redirect(url_for('main.index'))
            # 3. Si no, la contraseña es incorrecta
            else:
                flash('Login fallido. Revisa tu usuario y contraseña.', 'danger')
        else:
            # 4. Si no, el usuario no existe
            flash('Login fallido. Revisa tu usuario y contraseña.', 'danger')
        # --- FIN DE LA LÓGICA ---

    return render_template('login.html')

# --- RUTA DE LOGOUT (Sin cambios) ---
@auth_bp.route('/logout')
def logout():
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('auth.login')) # 'auth' es el nombre del Blueprint

# --- RUTA DE REGISTRO (¡MODIFICADA!) ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Ruta de registro.
    1. Si no hay usuarios, el primero se crea como 'admin'.
    2. Si ya hay usuarios, solo un 'admin' logueado puede crear más.
    """
    
    # 1. Contamos cuántos usuarios hay en la base de datos
    user_count = User.query.count()
    
    # 2. Lógica de Permiso:
    # Si ya hay usuarios (user_count > 0) Y (el usuario actual NO está logueado O NO es un admin)
    if user_count > 0 and (not current_user.is_authenticated or current_user.role != 'admin'):
        flash('No tienes permiso para registrar nuevas cuentas.', 'danger')
        return redirect(url_for('main.index'))

    # 3. Lógica del POST (si el formulario se envía)
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # 4. Lógica de Asignación de Rol
        if user_count == 0:
            role = 'admin'
            flash_message = f'Cuenta de Administrador {username} creada. Ahora puedes iniciar sesión.'
        else:
            role = 'empleado'
            flash_message = f'Cuenta de Empleado {username} creada.'
            
        nuevo_usuario = User(username=username, password_hash=hashed_password, role=role)
        
        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash(flash_message, 'success')
            
            # 5. Lógica de Redirección
            if current_user.is_authenticated:
                # Un admin logueado que crea una cuenta, vuelve al dashboard
                return redirect(url_for('main.index'))
            else:
                # El primer admin que se registra, va al login
                return redirect(url_for('auth.login'))
                
        except IntegrityError:
            db.session.rollback()
            flash('Ese nombre de usuario ya existe.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'danger')

    # 4. Si es un GET, solo muestra el formulario
    return render_template('register.html')