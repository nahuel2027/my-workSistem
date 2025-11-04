from flask import Blueprint, redirect, url_for, flash, render_template, request
from flask_login import login_required, current_user
from .models import db, Jornada, Venta, CierreMetodoPago # <-- Importar CierreMetodoPago
from sqlalchemy import func
import datetime
import decimal

jornadas_bp = Blueprint('jornadas', __name__)

# --- RUTA INICIAR JORNADA (Sin cambios) ---
@jornadas_bp.route('/jornada/iniciar')
@login_required
def iniciar_jornada():
    jornada_existente = Jornada.query.filter_by(user_id=current_user.id, activa=True).first()
    if jornada_existente:
        flash('Ya tienes una jornada activa.', 'warning')
    else:
        nueva_jornada = Jornada(user_id=current_user.id, activa=True)
        db.session.add(nueva_jornada)
        db.session.commit()
        flash(f'Jornada iniciada a las {nueva_jornada.hora_inicio.strftime("%H:%M")}.', 'success')
    return redirect(url_for('main.index'))

# -----------------------------------------------
# ¡RUTA FINALIZAR JORNADA (REESCRITA)!
# -----------------------------------------------
@jornadas_bp.route('/jornada/finalizar', methods=['GET', 'POST'])
@login_required
def finalizar_jornada():
    """Muestra el formulario de Cierre de Caja (GET) o procesa el cierre (POST)."""

    jornada_activa = Jornada.query.filter_by(user_id=current_user.id, activa=True).first()
    if not jornada_activa:
        flash('No tienes ninguna jornada activa para finalizar.', 'warning')
        return redirect(url_for('main.index'))

    # --- Lógica de GET: Calcular totales esperados por método ---
    # Consultamos las ventas de la jornada, agrupadas por método de pago
    totales_esperados_query = db.session.query(
        Venta.metodo_pago,
        func.sum(Venta.total).label('total_por_metodo')
    ).filter(
        Venta.jornada_id == jornada_activa.id,
        Venta.estado == 'completada'
    ).group_by(
        Venta.metodo_pago
    ).all()

    # Convertimos la lista de tuplas en un diccionario más fácil de usar
    # Ej: {'Efectivo': 150.00, 'Tarjeta Débito': 100.00}
    totales_esperados = {row.metodo_pago: row.total_por_metodo for row in totales_esperados_query}

    # --- Lógica de POST: Procesar el cierre ---
    if request.method == 'POST':
        try:
            notas_cierre = request.form.get('notas_cierre')
            diferencia_efectivo = decimal.Decimal(0)

            # Iteramos sobre los métodos que el sistema esperaba
            for metodo, esperado in totales_esperados.items():
                # El 'name' del input será, ej: "real_contado[Efectivo]"
                # Esto es más seguro que usar request.form.get('Efectivo')
                monto_real_str = request.form.get(f'real_contado[{metodo}]')

                if not monto_real_str:
                    # Si el empleado no ingresó un monto (ej: para 'Tarjeta'), asumimos que es 0
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

    # --- Lógica de GET (continuación) ---
    return render_template(
        'finalizar_jornada.html', 
        jornada=jornada_activa, 
        totales_esperados=totales_esperados # Pasamos el diccionario
    )