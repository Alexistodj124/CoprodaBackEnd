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
    foto = db.Column(db.String(255))
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
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Cliente {self.codigo}>"
