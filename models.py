from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class CategoriaProducto(db.Model):
    __tablename__ = "categorias_producto"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.String(255))
    creada_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizada_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    productos = db.relationship("Producto", back_populates="categoria", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<CategoriaProducto {self.nombre}>"


class Producto(db.Model):
    __tablename__ = "productos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    foto = db.Column(db.Text)
    codigo = db.Column(db.String(50), unique=True, nullable=False, index=True)
    categoria_id = db.Column(
        db.Integer, db.ForeignKey("categorias_producto.id"), nullable=False
    )
    precio_cf = db.Column(Numeric(12, 2), default=0, nullable=False)
    precio_minorista = db.Column(Numeric(12, 2), default=0, nullable=False)
    precio_mayorista = db.Column(Numeric(12, 2), default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    categoria = db.relationship("CategoriaProducto", back_populates="productos")

    def __repr__(self) -> str:
        return f"<Producto {self.codigo}>"


class Cliente(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(150), nullable=False)
    telefono = db.Column(db.String(30))
    direccion = db.Column(db.String(255))
    clasificacion_precio = db.Column(db.String(20), nullable=False, default="cf")
    saldo = db.Column(Numeric(12, 2), default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    ordenes = db.relationship("Orden", back_populates="cliente", lazy="dynamic")
    pagos_banco = db.relationship("Bancos", back_populates="cliente", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Cliente {self.codigo}>"


class Bancos(db.Model):
    __tablename__ = "bancos"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    referencia = db.Column(db.String(100), nullable=False, index=True)
    banco = db.Column(db.String(150), nullable=False)
    monto = db.Column(Numeric(12, 2), nullable=False, default=0)
    nota = db.Column(db.String(255))
    asignado = db.Column(db.Boolean, default=False, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    cliente = db.relationship("Cliente", back_populates="pagos_banco")

    def __repr__(self) -> str:
        return f"<Bancos {self.referencia}>"


usuarios_permisos = db.Table(
    "usuarios_permisos",
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), primary_key=True),
    db.Column("permiso_id", db.Integer, db.ForeignKey("permisos.id"), primary_key=True),
)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(100), unique=True, nullable=False, index=True)
    contrasena = db.Column(db.String(255), nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    permisos = db.relationship(
        "Permiso",
        secondary=usuarios_permisos,
        back_populates="usuarios",
        lazy="dynamic",
    )
    ordenes = db.relationship("Orden", back_populates="usuario", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.contrasena = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.contrasena, password)

    def __repr__(self) -> str:
        return f"<Usuario {self.usuario}>"


class Permiso(db.Model):
    __tablename__ = "permisos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    usuarios = db.relationship(
        "Usuario",
        secondary=usuarios_permisos,
        back_populates="permisos",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Permiso {self.nombre}>"


class TipoPago(db.Model):
    __tablename__ = "tipos_pago"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    ordenes = db.relationship("Orden", back_populates="tipo_pago", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<TipoPago {self.nombre}>"


class EstadoOrden(db.Model):
    __tablename__ = "estados_orden"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    ordenes = db.relationship("Orden", back_populates="estado", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<EstadoOrden {self.nombre}>"


class Orden(db.Model):
    __tablename__ = "ordenes"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    tipo_pago_id = db.Column(db.Integer, db.ForeignKey("tipos_pago.id"), nullable=False)
    estado_id = db.Column(
        db.Integer, db.ForeignKey("estados_orden.id"), nullable=False
    )
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    total = db.Column(Numeric(12, 2), default=0, nullable=False)
    saldo = db.Column(Numeric(12, 2), default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    tipo_pago = db.relationship("TipoPago", back_populates="ordenes")
    estado = db.relationship("EstadoOrden", back_populates="ordenes")
    cliente = db.relationship("Cliente", back_populates="ordenes")
    usuario = db.relationship("Usuario", back_populates="ordenes")
    items = db.relationship("OrdenItem", back_populates="orden", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Orden {self.id}>"


class OrdenItem(db.Model):
    __tablename__ = "orden_items"

    id = db.Column(db.Integer, primary_key=True)
    orden_id = db.Column(db.Integer, db.ForeignKey("ordenes.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    precio = db.Column(Numeric(12, 2), nullable=False, default=0)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    orden = db.relationship("Orden", back_populates="items")
    producto = db.relationship("Producto")

    def __repr__(self) -> str:
        return f"<OrdenItem {self.id} Orden {self.orden_id}>"
