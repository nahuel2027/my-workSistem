from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from flask_login import UserMixin
import datetime
import decimal

db = SQLAlchemy()

# -----------------------------------------------
# MODELO DE USUARIO
# -----------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='empleado')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    ventas = db.relationship('Venta', backref='user', lazy=True)
    jornadas = db.relationship('Jornada', backref='user', lazy=True)
    movimientos_stock = db.relationship('MovimientoStock', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

# -----------------------------------------------
# MODELO DE CLIENTE
# -----------------------------------------------
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    documento_fiscal = db.Column(db.String(20), nullable=True, unique=True)
    telefono = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    ventas = db.relationship('Venta', backref='cliente', lazy=True)

    def __repr__(self):
        return f'<Cliente {self.nombre}>'

# -----------------------------------------------
# MODELO MOVIMIENTO STOCK (AUDITORÍA)
# -----------------------------------------------
class MovimientoStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime(timezone=True), server_default=func.now())
    cantidad = db.Column(db.Integer, nullable=False) # Positivo (entrada), Negativo (salida)
    tipo = db.Column(db.String(50), nullable=False) # Ej: "Entrada Proveedor", "Venta", "Anulación Venta"
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<MovimientoStock {self.id} - Prod {self.producto_id} ({self.cantidad})>'

# -----------------------------------------------
# MODELO DE JORNADA (TURNO)
# -----------------------------------------------
class Jornada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hora_inicio = db.Column(db.DateTime(timezone=True), server_default=func.now())
    hora_fin = db.Column(db.DateTime(timezone=True), nullable=True)
    activa = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notas_cierre = db.Column(db.Text, nullable=True)
    
    ventas = db.relationship('Venta', backref='jornada', lazy=True)
    cierres_metodo_pago = db.relationship('CierreMetodoPago', backref='jornada', lazy=True)

    @property
    def duracion(self):
        if self.hora_fin:
            delta = self.hora_fin - self.hora_inicio
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}h {minutes}m {seconds}s"
        return "En curso"

    @property
    def diferencia_efectivo(self):
        for cierre in self.cierres_metodo_pago:
            if cierre.metodo_pago == 'Efectivo':
                return cierre.diferencia
        return decimal.Decimal(0)

    def __repr__(self):
        return f'<Jornada {self.id} - User {self.user_id}>'

# -----------------------------------------------
# MODELO CIERRE METODO PAGO (ARQUEO)
# -----------------------------------------------
class CierreMetodoPago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornada.id'), nullable=False)
    metodo_pago = db.Column(db.String(50), nullable=False)
    monto_esperado = db.Column(db.Numeric(10, 2), nullable=False)
    monto_real_contado = db.Column(db.Numeric(10, 2), nullable=False)
    diferencia = db.Column(db.Numeric(10, 2), nullable=False)

# -----------------------------------------------
# MODELO DE PRODUCTO
# -----------------------------------------------
class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    precio_costo = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    stock_minimo = db.Column(db.Integer, nullable=False, default=5) # Alerta de Stock
    
    movimientos_stock = db.relationship('MovimientoStock', backref='producto', lazy=True)
    
    def __repr__(self):
        return f'<Producto {self.nombre}>'

# -----------------------------------------------
# MODELO DE VENTA
# -----------------------------------------------
class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime(timezone=True), server_default=func.now())
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    ganancia_bruta_total = db.Column(db.Numeric(10, 2), nullable=False, default=0.0)
    estado = db.Column(db.String(20), nullable=False, default='completada')
    metodo_pago = db.Column(db.String(50), nullable=False, default='Efectivo')
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    jornada_id = db.Column(db.Integer, db.ForeignKey('jornada.id'), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    
    detalles = db.relationship('DetalleVenta', backref='venta', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Venta {self.id} - {self.estado}>'

# -----------------------------------------------
# MODELO DE DETALLE DE VENTA
# -----------------------------------------------
class DetalleVenta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    precio_costo_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    
    producto = db.relationship('Producto', backref='detalles_venta')