from flask import Blueprint, redirect, url_for, flash, render_template, request
from flask_login import login_required, current_user
from .models import db, Jornada, Venta, CierreMetodoPago # <-- Importar CierreMetodoPago
<<<<<<< HEAD
from sqlalchemy import func
import datetime
import decimal
=======
from sqlalchemy import func # <-- Importar func
import datetime
import decimal # <-- Importar decimal
>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)

jornadas_bp = Blueprint('jornadas', __name__)

# --- RUTA INICIAR JORNADA (Sin cambios) ---
@jornadas_bp.route('/jornada/iniciar')
@login_required
def iniciar_jornada():
<<<<<<< HEAD
    jornada_existente = Jornada.query.filter_by(user_id=current_user.id, activa=True).first()
=======
    """Inicia un nuevo turno (jornada) para el usuario."""
    jornada_existente = Jornada.query.filter_by(user_id=current_user.id, activa=True).first()

>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)
    if jornada_existente:
        flash('Ya tienes una jornada activa.', 'warning')
    else:
        nueva_jornada = Jornada(user_id=current_user.id, activa=True)
        db.session.add(nueva_jornada)
        db.session.commit()
        flash(f'Jornada iniciada a las {nueva_jornada.hora_inicio.strftime("%H:%M")}.', 'success')
<<<<<<< HEAD
=======

>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)
    return redirect(url_for('main.index'))

# -----------------------------------------------
# ¡RUTA FINALIZAR JORNADA (REESCRITA)!
# -----------------------------------------------
@jornadas_bp.route('/jornada/finalizar', methods=['GET', 'POST'])
@login_required
def finalizar_jornada():
<<<<<<< HEAD
    """Muestra el formulario de Cierre de Caja (GET) o procesa el cierre (POST)."""

    jornada_activa = Jornada.query.filter_by(user_id=current_user.id, activa=True).first()
=======
    """
    Muestra el formulario de Cierre de Caja (GET)
    o procesa el cierre (POST).
    """

    # 1. Buscar la jornada activa del empleado
    jornada_activa = Jornada.query.filter_by(user_id=current_user.id, activa=True).first()

>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)
    if not jornada_activa:
        flash('No tienes ninguna jornada activa para finalizar.', 'warning')
        return redirect(url_for('main.index'))

<<<<<<< HEAD
    # --- Lógica de GET: Calcular totales esperados por método ---
    # Consultamos las ventas de la jornada, agrupadas por método de pago
=======
    # 2. Calcular el efectivo esperado (solo ventas 'completadas')
>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)
    totales_esperados_query = db.session.query(
        Venta.metodo_pago,
        func.sum(Venta.total).label('total_por_metodo')
    ).filter(
        Venta.jornada_id == jornada_activa.id,
        Venta.estado == 'completada'
    ).group_by(
        Venta.metodo_pago
    ).all()

<<<<<<< HEAD
    # Convertimos la lista de tuplas en un diccionario más fácil de usar
    # Ej: {'Efectivo': 150.00, 'Tarjeta Débito': 100.00}
    totales_esperados = {row.metodo_pago: row.total_por_metodo for row in totales_esperados_query}

    # --- Lógica de POST: Procesar el cierre ---
=======
    # Convertimos la lista de tuplas en un diccionario
    # Ej: {'Efectivo': 150.00, 'Tarjeta Débito': 100.00}
    totales_esperados = {row.metodo_pago: row.total_por_metodo for row in totales_esperados_query}

    # 3. Lógica POST (Cuando el empleado envía el formulario)
>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)
    if request.method == 'POST':
        try:
            notas_cierre = request.form.get('notas_cierre')
            diferencia_efectivo = decimal.Decimal(0)

            # Iteramos sobre los métodos que el sistema esperaba
            for metodo, esperado in totales_esperados.items():
                # El 'name' del input será, ej: "real_contado[Efectivo]"
<<<<<<< HEAD
                # Esto es más seguro que usar request.form.get('Efectivo')
                monto_real_str = request.form.get(f'real_contado[{metodo}]')

                if not monto_real_str:
                    # Si el empleado no ingresó un monto (ej: para 'Tarjeta'), asumimos que es 0
=======
                monto_real_str = request.form.get(f'real_contado[{metodo}]')

                if not monto_real_str:
                    # Si el empleado no ingresó un monto (ej: para 'Tarjeta'), asumimos 0
>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)
                    monto_real_contado = decimal.Decimal(0)
                else:
                    monto_real_contado = decimal.Decimal(monto_real_str)

                # Calcular la diferencia para este método
                diferencia = monto_real_contado - esperado

                # Guardar el registro de Cierre para este método
                cierre_metodo = CierreMetodoPago(
                    jornada_id=jornada_activa.id,
                    metodo_pago=metodo,
                    monto_esperado=esperado,
                    monto_real_contado=monto_real_contado,
                    diferencia=diferencia
                )
                db.session.add(cierre_metodo)

                # Guardamos la diferencia de efectivo para el mensaje flash
                if metodo == 'Efectivo':
                    diferencia_efectivo = diferencia

            # Actualizar la Jornada (cerrarla y añadir notas)
            jornada_activa.activa = False
            jornada_activa.hora_fin = datetime.datetime.now(datetime.timezone.utc)
            jornada_activa.notas_cierre = notas_cierre

            db.session.commit()

            # Informar el resultado al empleado
            if diferencia_efectivo == 0:
                flash('¡Caja de Efectivo cerrada perfectamente! Turno finalizado.', 'success')
            elif diferencia_efectivo > 0:
                flash(f'Turno finalizado con un SOBRANTE de Efectivo de ${diferencia_efectivo}.', 'warning')
            else:
                flash(f'Turno finalizado con un FALTANTE de Efectivo de ${abs(diferencia_efectivo)}.', 'danger')

            return redirect(url_for('main.index'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar el cierre: {str(e)}', 'danger')

<<<<<<< HEAD
    # --- Lógica de GET (continuación) ---
    return render_template(
        'finalizar_jornada.html', 
        jornada=jornada_activa, 
        totales_esperados=totales_esperados # Pasamos el diccionario
=======
    # 4. Lógica GET (Solo mostrar el formulario)
    # Pasamos el diccionario de totales a la plantilla
    return render_template(
        'finalizar_jornada.html', 
        jornada=jornada_activa, 
        totales_esperados=totales_esperados
>>>>>>> 3469ee7 (Actualizo código con nuevas funciones)
    )