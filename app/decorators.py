from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def admin_required(f):
    """
    Decorador personalizado que restringe el acceso solo a usuarios
    con el rol de 'admin'.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si el usuario no está logueado o no es un admin
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('No tienes permiso para acceder a esta página. Se requiere ser Administrador.', 'danger')
            return redirect(url_for('main.index'))
        
        # Si es un admin, permite que la función original se ejecute
        return f(*args, **kwargs)
    return decorated_function