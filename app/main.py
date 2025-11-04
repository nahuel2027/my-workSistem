# -----------------------------------------------
# IMPORTACIONES (Todas juntas al principio)
# -----------------------------------------------
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, jsonify
)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, desc, cast, Date, extract
import decimal
import datetime
from datetime import date, timedelta

# Importar Modelos y extensiones
from .models import (
    db, Producto, Venta, DetalleVenta, Jornada, User, MovimientoStock, Cliente
)
from . import bcrypt
from .decorators import admin_required

# --- Constantes ---
PER_PAGE = 10 # Define cuántos productos mostrar por página

# --- Blueprint ---
main_bp = Blueprint('main', __name__)


# --- Función Helper ---
def get_jornada_activa():
    """Encuentra la jornada activa del usuario actual."""
    return Jornada.query.filter_by(user_id=current_user.id, activa=True).first()

# -----------------------------------------------
# RUTA 1: DASHBOARD
# -----------------------------------------------
@main_bp.route('/')
@login_required
def index():
    """Página de inicio / Dashboard con analítica en tiempo real."""
    
    jornada_activa = get_jornada_activa()
    today = date.today()
    empleados_activos = Jornada.query.filter_by(activa=True).count()

    # 1. ¿Cuánto se vendió HOY? (Solo ventas 'completada')
    ventas_hoy_query = db.session.query(
        func.sum(Venta.total).label('total_ingresos'),
        func.sum(Venta.ganancia_bruta_total).label('total_ganancia')
    ).filter(
        func.date(Venta.fecha) == today,
        Venta.estado == 'completada'
    ).first()
    ventas_hoy = ventas_hoy_query.total_ingresos or decimal.Decimal(0)
    ganancia_hoy = ventas_hoy_query.total_ganancia or decimal.Decimal(0)

    # 2. ¿Cuánto vendí YO en MI turno actual?
    ventas_mi_jornada = decimal.Decimal(0)
    ganancia_mi_jornada = decimal.Decimal(0)
    if jornada_activa:
        ventas_jornada_query = db.session.query(
            func.sum(Venta.total).label('total_ingresos'),
            func.sum(Venta.ganancia_bruta_total).label('total_ganancia')
        ).filter(
            Venta.jornada_id == jornada_activa.id,
            Venta.estado == 'completada'
        ).first()
        ventas_mi_jornada = ventas_jornada_query.total_ingresos or decimal.Decimal(0)
        ganancia_mi_jornada = ventas_jornada_query.total_ganancia or decimal.Decimal(0)

    # 3. ¿Producto Estrella de Hoy?
    producto_estrella = "N/A"
    producto_top_query = db.session.query(
        DetalleVenta.producto_id,
        func.sum(DetalleVenta.cantidad).label('total_vendido')
    ).join(
        Venta, DetalleVenta.venta_id == Venta.id
    ).filter(
        func.date(Venta.fecha) == today,
        Venta.estado == 'completada'
    ).group_by(
        DetalleVenta.producto_id
    ).order_by(
        desc('total_vendido')
    ).first()
    if producto_top_query:
        producto = db.session.get(Producto, producto_top_query.producto_id)
        if producto:
            producto_estrella = f"{producto.nombre} ({int(producto_top_query.total_vendido)}u)"

    # 4. ¿Hay productos con stock bajo? (Solo para Admins)
    productos_stock_bajo = []
    if current_user.role == 'admin':
        productos_stock_bajo = Producto.query.filter(
            Producto.stock <= Producto.stock_minimo
        ).order_by(Producto.stock.asc()).all()
    
    return render_template('index.html', 
                           jornada_activa=jornada_activa,
                           ventas_hoy=ventas_hoy,
                           ganancia_hoy=ganancia_hoy,
                           ventas_mi_jornada=ventas_mi_jornada,
                           ganancia_mi_jornada=ganancia_mi_jornada,
                           empleados_activos=empleados_activos,
                           producto_estrella=producto_estrella,
                           productos_stock_bajo=productos_stock_bajo
                          )

# -----------------------------------------------
# RUTA 2: GESTIONAR PRODUCTOS (CRUD, Búsqueda, Paginación)
# -----------------------------------------------
@main_bp.route('/productos', methods=['GET', 'POST'])
@login_required
@admin_required
def gestionar_productos():
    """Página para ver, agregar, buscar y paginar productos."""
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio_costo = decimal.Decimal(request.form.get('precio_costo'))
        precio = decimal.Decimal(request.form.get('precio'))
        stock = int(request.form.get('stock'))
        stock_minimo = int(request.form.get('stock_minimo'))
        descripcion = request.form.get('descripcion')

        if not nombre or precio <= 0 or stock < 0 or precio_costo < 0 or stock_minimo < 0:
            flash('Datos inválidos. Revisa nombre, precios y stock.', 'danger')
        elif precio_costo > precio:
            flash('Error: El precio de costo no puede ser mayor al precio de venta.', 'warning')
        else:
            try:
                nuevo_producto = Producto(
                    nombre=nombre, 
                    precio_costo=precio_costo,
                    precio=precio, 
                    stock=stock, 
                    stock_minimo=stock_minimo,
                    descripcion=descripcion
                )
                db.session.add(nuevo_producto)
                db.session.commit()
                flash(f'Producto "{nombre}" agregado exitosamente.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f'Error: Ya existe un producto con el nombre "{nombre}".', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al agregar producto: {str(e)}', 'danger')
        
        return redirect(url_for('main.gestionar_productos'))

    # Lógica GET
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q', '', type=str)
    productos_query = Producto.query.order_by(Producto.nombre)
    if search_query:
        productos_query = productos_query.filter(Producto.nombre.ilike(f'%{search_query}%'))
    productos_paginados = productos_query.paginate(page=page, per_page=PER_PAGE, error_out=False)
    
    return render_template(
        'productos.html', 
        productos=productos_paginados,
        search_query=search_query
    )

# -----------------------------------------------
# RUTA 3: VER VENTAS
# -----------------------------------------------
@main_bp.route('/ventas')
@login_required
@admin_required
def ver_ventas():
    """Muestra un historial de todas las ventas."""
    ventas = Venta.query.options(
        db.joinedload(Venta.user), 
        db.joinedload(Venta.jornada),
        db.joinedload(Venta.cliente)
    ).order_by(Venta.fecha.desc()).all()
    return render_template('ventas.html', ventas=ventas)

# -----------------------------------------------
# RUTA 4: NUEVA VENTA (AJAX/JSON)
# -----------------------------------------------
@main_bp.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_venta():
    """
    Formulario para crear una nueva venta (AJAX/JSON).
    """
    if request.method == 'POST':
        jornada_activa = get_jornada_activa()
        if not jornada_activa:
            return jsonify({'success': False, 'error': 'No hay una jornada activa.'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No se recibieron datos.'}), 400

        producto_ids = data.get('producto_ids', [])
        cantidades = data.get('cantidades', [])
        cliente_id_str = data.get('cliente_id')
        cliente_id = int(cliente_id_str) if cliente_id_str else None
        metodo_pago = data.get('metodo_pago')
            
        if not metodo_pago:
            return jsonify({'success': False, 'error': 'Debe seleccionar un método de pago.'}), 400
        if not producto_ids or not cantidades or len(producto_ids) != len(cantidades):
            return jsonify({'success': False, 'error': 'Datos de productos inválidos.'}), 400

        items_venta = []
        total_venta = decimal.Decimal(0)
        total_ganancia_bruta = decimal.Decimal(0)

        try:
            for i in range(len(producto_ids)):
                id_prod = int(producto_ids[i])
                cantidad_prod = int(cantidades[i])
                if cantidad_prod <= 0: continue 
                producto = db.session.get(Producto, id_prod)
                if not producto: raise Exception(f'Producto con ID {id_prod} no encontrado.')
                if producto.stock < cantidad_prod: raise Exception(f'Stock insuficiente para "{producto.nombre}".')
                
                precio_linea = producto.precio * cantidad_prod
                total_venta += precio_linea
                ganancia_linea = (producto.precio - producto.precio_costo) * cantidad_prod
                total_ganancia_bruta += ganancia_linea
                items_venta.append({
                    'producto': producto, 'cantidad': cantidad_prod,
                    'precio_unitario': producto.precio, 'precio_costo_unitario': producto.precio_costo
                })

            if not items_venta:
                 return jsonify({'success': False, 'error': 'No se seleccionaron productos válidos.'}), 400

            nueva_venta = Venta(
                total=total_venta, 
                ganancia_bruta_total=total_ganancia_bruta,
                user_id=current_user.id,
                jornada_id=jornada_activa.id,
                estado='completada',
                cliente_id=cliente_id,
                metodo_pago=metodo_pago
            )
            db.session.add(nueva_venta)
            db.session.flush() 
            
            for item in items_venta:
                item['producto'].stock -= item['cantidad']
                detalle = DetalleVenta(
                    venta_id=nueva_venta.id,
                    producto_id=item['producto'].id,
                    cantidad=item['cantidad'],
                    precio_unitario=item['precio_unitario'],
                    precio_costo_unitario=item['precio_costo_unitario']
                )
                db.session.add(detalle)
                
                mov_stock_venta = MovimientoStock(
                    producto_id=item['producto'].id,
                    cantidad=-item['cantidad'],
                    tipo='Venta',
                    user_id=current_user.id
                )
                db.session.add(mov_stock_venta)

            db.session.commit()
            return jsonify({'success': True, 'venta_id': nueva_venta.id})

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    # Lógica GET
    productos = Producto.query.filter(Producto.stock > 0).order_by(Producto.nombre).all()
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return render_template('nueva_venta.html', productos=productos, clientes=clientes)

# -----------------------------------------------
# RUTA 5: RECIBO DE VENTA
# -----------------------------------------------
@main_bp.route('/venta/recibo/<int:venta_id>')
@login_required
def recibo_venta(venta_id):
    """Muestra una página simple (tipo ticket) de la venta para imprimir."""
    venta = Venta.query.options(
        db.joinedload(Venta.user),
        db.joinedload(Venta.cliente),
        db.joinedload(Venta.detalles).joinedload(DetalleVenta.producto)
    ).get_or_404(venta_id)
    
    if current_user.role != 'admin' and venta.user_id != current_user.id:
        flash('No tienes permiso para ver este recibo.', 'danger')
        return redirect(url_for('main.index'))
        
    return render_template('recibo.html', venta=venta)

# -----------------------------------------------
# RUTA 6: HISTORIAL DE JORNADAS
# -----------------------------------------------
@main_bp.route('/jornadas/historial')
@login_required
@admin_required
def historial_jornadas():
    """Muestra una lista de todas las jornadas laborales completadas, con filtros."""
    
    user_id_filtro = request.args.get('user_id', '', type=str)
    fecha_filtro_str = request.args.get('fecha', '', type=str)

    query = Jornada.query.options(
        db.joinedload(Jornada.user),
        db.joinedload(Jornada.cierres_metodo_pago) # Carga previa de cierres
    ).filter_by(
        activa=False
    )

    if user_id_filtro:
        query = query.filter(Jornada.user_id == int(user_id_filtro))
    
    fecha_filtro = None
    if fecha_filtro_str:
        try:
            fecha_filtro = datetime.datetime.strptime(fecha_filtro_str, '%Y-%m-%d').date()
            query = query.filter(func.date(Jornada.hora_inicio) == fecha_filtro)
        except ValueError:
            flash('Formato de fecha inválido. Use AAAA-MM-DD.', 'danger')

    jornadas_completadas = query.order_by(Jornada.hora_fin.desc()).all()
    usuarios = User.query.filter(User.role.in_(['admin', 'empleado'])).order_by(User.username).all()

    return render_template(
        'historial_jornadas.html', 
        jornadas=jornadas_completadas,
        usuarios=usuarios,
        user_id_filtro=user_id_filtro,
        fecha_filtro=fecha_filtro_str
    )

# -----------------------------------------------
# RUTA 7: EDITAR PRODUCTO
# -----------------------------------------------
@main_bp.route('/producto/editar/<int:producto_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_producto(producto_id):
    """Edita un producto existente."""
    producto = Producto.query.get_or_404(producto_id)
    
    if request.method == 'POST':
        producto.nombre = request.form.get('nombre')
        producto.descripcion = request.form.get('descripcion')
        producto.precio_costo = decimal.Decimal(request.form.get('precio_costo'))
        producto.precio = decimal.Decimal(request.form.get('precio'))
        producto.stock = int(request.form.get('stock'))
        producto.stock_minimo = int(request.form.get('stock_minimo'))

        if producto.precio_costo > producto.precio:
            flash('Error: El precio de costo no puede ser mayor al precio de venta.', 'warning')
            return render_template('editar_producto.html', producto=producto)
        
        try:
            db.session.commit()
            flash(f'Producto "{producto.nombre}" actualizado exitosamente.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash(f'Error: Ya existe un producto con el nombre "{producto.nombre}".', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar producto: {str(e)}', 'danger')
        
        return redirect(url_for('main.gestionar_productos'))
    
    return render_template('editar_producto.html', producto=producto)

# -----------------------------------------------
# RUTA 8: ELIMINAR PRODUCTO
# -----------------------------------------------
@main_bp.route('/producto/eliminar/<int:producto_id>', methods=['POST'])
@login_required
@admin_required
def eliminar_producto(producto_id):
    """Elimina un producto si no tiene ventas."""
    producto = Producto.query.get_or_404(producto_id)
    
    if producto.detalles_venta:
        flash(f'Error: No se puede eliminar "{producto.nombre}" porque ya tiene ventas registradas.', 'danger')
    else:
        try:
            nombre_producto = producto.nombre
            db.session.delete(producto)
            db.session.commit()
            flash(f'Producto "{nombre_producto}" eliminado exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar producto: {str(e)}', 'danger')
            
    return redirect(url_for('main.gestionar_productos'))

# -----------------------------------------------
# RUTA 9: AJUSTE DE INVENTARIO
# -----------------------------------------------
@main_bp.route('/inventario/ajuste', methods=['GET', 'POST'])
@login_required
@admin_required
def ajuste_inventario():
    """Registra entradas o salidas de stock."""
    
    if request.method == 'POST':
        try:
            producto_id = int(request.form.get('producto_id'))
            cantidad = int(request.form.get('cantidad'))
            tipo_movimiento = request.form.get('tipo_movimiento')
            
            if not producto_id or cantidad == 0 or not tipo_movimiento:
                flash('Todos los campos son obligatorios y la cantidad no puede ser cero.', 'danger')
                productos = Producto.query.order_by(Producto.nombre).all()
                return render_template('ajuste_inventario.html', productos=productos)

            producto = db.session.get(Producto, producto_id)
            if not producto:
                flash('Producto no encontrado.', 'danger')
                raise Exception("Producto no válido")

            nuevo_movimiento = MovimientoStock(
                producto_id=producto_id,
                cantidad=cantidad,
                tipo=tipo_movimiento,
                user_id=current_user.id
            )
            db.session.add(nuevo_movimiento)
            
            producto.stock += cantidad
            
            db.session.commit()
            
            flash(f'Stock de "{producto.nombre}" actualizado exitosamente. Nuevo stock: {producto.stock}', 'success')
            return redirect(url_for('main.ajuste_inventario'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar el ajuste: {str(e)}', 'danger')
            return redirect(url_for('main.ajuste_inventario'))

    # Lógica GET
    productos = Producto.query.order_by(Producto.nombre).all()
    return render_template('ajuste_inventario.html', productos=productos)

# -----------------------------------------------
# RUTA 10: ANULAR VENTA
# -----------------------------------------------
@main_bp.route('/venta/anular/<int:venta_id>', methods=['POST'])
@login_required
@admin_required
def anular_venta(venta_id):
    """Anula una venta y devuelve el stock."""
    
    venta = Venta.query.get_or_404(venta_id)
    
    if venta.estado == 'anulada':
        flash('Esta venta ya ha sido anulada.', 'warning')
        return redirect(url_for('main.ver_ventas'))
        
    try:
        for detalle in venta.detalles:
            producto = db.session.get(Producto, detalle.producto_id)
            if producto:
                producto.stock += detalle.cantidad
                
                mov_stock_anulacion = MovimientoStock(
                    producto_id=detalle.producto_id,
                    cantidad=detalle.cantidad,
                    tipo='Anulación Venta',
                    user_id=current_user.id
                )
                db.session.add(mov_stock_anulacion)
            else:
                raise Exception(f"Producto ID {detalle.producto_id} no encontrado. Anulación cancelada.")
        
        venta.estado = 'anulada'
        
        db.session.commit()
        
        flash(f'Venta #{venta.id} anulada exitosamente. El stock ha sido restaurado.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al anular la venta: {str(e)}', 'danger')
        
    return redirect(url_for('main.ver_ventas'))

# -----------------------------------------------
# RUTA 11: GESTIÓN DE USUARIOS
# -----------------------------------------------
@main_bp.route('/admin/usuarios')
@login_required
@admin_required
def gestionar_usuarios():
    """Muestra la lista de todos los usuarios para administrar."""
    usuarios = User.query.order_by(User.username).all()
    return render_template('gestionar_usuarios.html', usuarios=usuarios)

# -----------------------------------------------
# RUTA 12: ACTIVAR/DESACTIVAR USUARIO
# -----------------------------------------------
@main_bp.route('/admin/usuario/toggle_active/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_active(user_id):
    """Activa o desactiva la cuenta de un usuario."""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('No puedes desactivar tu propia cuenta.', 'danger')
        return redirect(url_for('main.gestionar_usuarios'))
        
    user.is_active = not user.is_active
    db.session.commit()
    
    estado = "activada" if user.is_active else "desactivada"
    flash(f'La cuenta de {user.username} ha sido {estado}.', 'success')
    return redirect(url_for('main.gestionar_usuarios'))

# -----------------------------------------------
# RUTA 13: CAMBIAR ROL DE USUARIO
# -----------------------------------------------
@main_bp.route('/admin/usuario/toggle_role/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def toggle_role(user_id):
    """Promueve o degrada a un usuario (admin <-> empleado)."""
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('No puedes cambiar tu propio rol.', 'danger')
        return redirect(url_for('main.gestionar_usuarios'))
    
    if user.role == 'admin' and User.query.filter_by(role='admin').count() == 1:
        flash('No se puede degradar al último administrador.', 'danger')
        return redirect(url_for('main.gestionar_usuarios'))
        
    if user.role == 'empleado':
        user.role = 'admin'
        flash(f'{user.username} ha sido promovido a Administrador.', 'success')
    else:
        user.role = 'empleado'
        flash(f'{user.username} ha sido degradado a Empleado.', 'success')
        
    db.session.commit()
    return redirect(url_for('main.gestionar_usuarios'))

# -----------------------------------------------
# RUTA 14: RESETEAR CONTRASEÑA
# -----------------------------------------------
@main_bp.route('/admin/usuario/reset_password/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def reset_password(user_id):
    """Muestra y procesa el formulario para cambiar la contraseña de otro usuario."""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if not new_password or len(new_password) < 4:
            flash('La contraseña debe tener al menos 4 caracteres.', 'warning')
        else:
            user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
            db.session.commit()
            flash(f'La contraseña de {user.username} ha sido actualizada.', 'success')
            return redirect(url_for('main.gestionar_usuarios'))
            
    return render_template('reset_password.html', user=user)

# -----------------------------------------------
# RUTA 15: PÁGINA DE REPORTES (Gráficos)
# -----------------------------------------------
@main_bp.route('/reportes')
@login_required
@admin_required
def reportes():
    """Muestra la página principal del dashboard de reportes."""
    return render_template('reportes.html')

# -----------------------------------------------
# RUTA 16: API - VENTAS DIARIAS
# -----------------------------------------------
@main_bp.route('/api/reporte/ventas_diarias_30d')
@login_required
@admin_required
def api_ventas_diarias_30d():
    """Devuelve ingresos y ganancias por día de los últimos 30 días."""
    fecha_limite = date.today() - timedelta(days=30)
    
    ventas_por_dia = db.session.query(
        cast(Venta.fecha, Date).label('fecha_dia'),
        func.sum(Venta.total).label('total_ingresos'),
        func.sum(Venta.ganancia_bruta_total).label('total_ganancia')
    ).filter(
        Venta.estado == 'completada',
        Venta.fecha >= fecha_limite
    ).group_by('fecha_dia').order_by('fecha_dia').all()
    
    labels = [venta.fecha_dia.strftime('%d/%m') for venta in ventas_por_dia]
    data_ingresos = [float(venta.total_ingresos) for venta in ventas_por_dia]
    data_ganancia = [float(venta.total_ganancia) for venta in ventas_por_dia]
    
    return jsonify(labels=labels, data_ingresos=data_ingresos, data_ganancia=data_ganancia)

# -----------------------------------------------
# RUTA 17: API - VENTAS POR EMPLEADO
# -----------------------------------------------
@main_bp.route('/api/reporte/ventas_por_empleado_mes')
@login_required
@admin_required
def api_ventas_por_empleado_mes():
    """Devuelve el total de ingresos y ganancias por cada empleado este mes."""
    mes_actual = date.today().month
    anio_actual = date.today().year
    
    ventas = db.session.query(
        User.username,
        func.sum(Venta.total).label('total_ingresos'),
        func.sum(Venta.ganancia_bruta_total).label('total_ganancia')
    ).join(
        User, Venta.user_id == User.id
    ).filter(
        Venta.estado == 'completada',
        extract('month', Venta.fecha) == mes_actual,
        extract('year', Venta.fecha) == anio_actual
    ).group_by(User.username).order_by(desc('total_ingresos')).all()
    
    labels = [v.username for v in ventas]
    data_ingresos = [float(v.total_ingresos) for v in ventas]
    data_ganancia = [float(v.total_ganancia) for v in ventas]
    
    return jsonify(labels=labels, data_ingresos=data_ingresos, data_ganancia=data_ganancia)

# -----------------------------------------------
# RUTA 18: API - PRODUCTOS TOP 5
# -----------------------------------------------
@main_bp.route('/api/reporte/productos_top_5_mes')
@login_required
@admin_required
def api_productos_top_5_mes():
    """Devuelve los 5 productos más vendidos (por cantidad) este mes."""
    
    mes_actual = date.today().month
    anio_actual = date.today().year
    
    productos = db.session.query(
        Producto.nombre,
        func.sum(DetalleVenta.cantidad).label('total_cantidad')
    ).join(
        Producto, DetalleVenta.producto_id == Producto.id
    ).join(
        Venta, DetalleVenta.venta_id == Venta.id
    ).filter(
        Venta.estado == 'completada',
        extract('month', Venta.fecha) == mes_actual,
        extract('year', Venta.fecha) == anio_actual
    ).group_by(
        Producto.nombre
    ).order_by(
        desc('total_cantidad')
    ).limit(5).all()
    
    labels = [p.nombre for p in productos]
    data = [int(p.total_cantidad) for p in productos]
    
    return jsonify(labels=labels, data=data)

# -----------------------------------------------
# RUTA 19: REPORTE DE INVENTARIO
# -----------------------------------------------
@main_bp.route('/reportes/inventario', methods=['GET'])
@login_required
@admin_required
def reporte_inventario():
    """Muestra un historial auditable de todos los movimientos de stock."""
    
    page = request.args.get('page', 1, type=int)
    producto_id_filtro = request.args.get('producto_id', '', type=str)
    tipo_filtro = request.args.get('tipo', '', type=str)
    
    query = MovimientoStock.query.options(
        db.joinedload(MovimientoStock.user),
        db.joinedload(MovimientoStock.producto)
    )
    
    if producto_id_filtro:
        query = query.filter(MovimientoStock.producto_id == int(producto_id_filtro))
    if tipo_filtro:
        query = query.filter(MovimientoStock.tipo == tipo_filtro)
        
    movimientos_paginados = query.order_by(
        MovimientoStock.fecha.desc()
    ).paginate(page=page, per_page=25, error_out=False)
    
    productos = Producto.query.order_by(Producto.nombre).all()
    tipos_movimiento_query = db.session.query(MovimientoStock.tipo).distinct().all()
    tipos_movimiento = [t[0] for t in tipos_movimiento_query]
    
    return render_template(
        'reporte_inventario.html',
        movimientos=movimientos_paginados,
        productos=productos,
        tipos_movimiento=tipos_movimiento,
        producto_id_filtro=producto_id_filtro,
        tipo_filtro=tipo_filtro
    )

# -----------------------------------------------
# RUTA 20: GESTIONAR CLIENTES
# -----------------------------------------------
@main_bp.route('/admin/clientes', methods=['GET', 'POST'])
@login_required
@admin_required
def gestionar_clientes():
    """Muestra lista de clientes y formulario para agregar."""
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        documento = request.form.get('documento_fiscal')
        telefono = request.form.get('telefono')
        email = request.form.get('email')

        if not nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
        else:
            try:
                nuevo_cliente = Cliente(
                    nombre=nombre, 
                    documento_fiscal=documento, 
                    telefono=telefono, 
                    email=email
                )
                db.session.add(nuevo_cliente)
                db.session.commit()
                flash(f'Cliente "{nombre}" agregado exitosamente.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f'Error: Ya existe un cliente con ese documento fiscal.', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al agregar cliente: {str(e)}', 'danger')
        
        return redirect(url_for('main.gestionar_clientes'))

    # Lógica GET
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    return render_template('gestionar_clientes.html', clientes=clientes)

# -----------------------------------------------
# RUTA 21: EDITAR CLIENTE
# -----------------------------------------------
@main_bp.route('/admin/cliente/editar/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar_cliente(cliente_id):
    """Muestra formulario para editar un cliente."""
    cliente = Cliente.query.get_or_404(cliente_id)
    
    if request.method == 'POST':
        cliente.nombre = request.form.get('nombre')
        cliente.documento_fiscal = request.form.get('documento_fiscal')
        cliente.telefono = request.form.get('telefono')
        cliente.email = request.form.get('email')
        
        if not cliente.nombre:
            flash('El nombre del cliente es obligatorio.', 'danger')
        else:
            try:
                db.session.commit()
                flash(f'Cliente "{cliente.nombre}" actualizado exitosamente.', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(f'Error: Ya existe un cliente con ese documento fiscal.', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'Error al actualizar cliente: {str(e)}', 'danger')
            
            return redirect(url_for('main.gestionar_clientes'))
    
    return render_template('editar_cliente.html', cliente=cliente)

# -----------------------------------------------
# RUTA 22: ELIMINAR CLIENTE
# -----------------------------------------------
@main_bp.route('/admin/cliente/eliminar/<int:cliente_id>', methods=['POST'])
@login_required
@admin_required
def eliminar_cliente(cliente_id):
    """Elimina un cliente (si no tiene ventas)."""
    cliente = Cliente.query.get_or_404(cliente_id)
    
    if cliente.ventas:
        flash(f'Error: No se puede eliminar "{cliente.nombre}" porque ya tiene ventas asociadas.', 'danger')
    else:
        try:
            nombre_cliente = cliente.nombre
            db.session.delete(cliente)
            db.session.commit()
            flash(f'Cliente "{nombre_cliente}" eliminado exitosamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar cliente: {str(e)}', 'danger')
            
    return redirect(url_for('main.gestionar_clientes'))

# -----------------------------------------------
# RUTA 23: PERFIL DE CLIENTE
# -----------------------------------------------
@main_bp.route('/admin/cliente/perfil/<int:cliente_id>')
@login_required
@admin_required
def perfil_cliente(cliente_id):
    """Muestra el perfil detallado y el historial de compras de un cliente."""
    
    cliente = Cliente.query.get_or_404(cliente_id)
    
    ventas_cliente = Venta.query.options(
        db.joinedload(Venta.user),
        db.joinedload(Venta.jornada)
    ).filter_by(
        cliente_id=cliente.id
    ).order_by(
        Venta.fecha.desc()
    ).all()
    
    analiticas = db.session.query(
        func.sum(Venta.total).label('total_gastado'),
        func.count(Venta.id).label('total_compras')
    ).filter_by(
        cliente_id=cliente.id,
        estado='completada'
    ).first()
    
    compras_anuladas = Venta.query.filter_by(
        cliente_id=cliente.id,
        estado='anulada'
    ).count()

    total_gastado = analiticas.total_gastado or decimal.Decimal(0)
    total_compras = analiticas.total_compras or 0

    return render_template(
        'perfil_cliente.html',
        cliente=cliente,
        ventas=ventas_cliente,
        total_gastado=total_gastado,
        total_compras=total_compras,
        compras_anuladas=compras_anuladas
    )