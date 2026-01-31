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
    activo = db.Column(db.Boolean, default=True, nullable=False)
    es_producto_final = db.Column(db.Boolean, default=True, nullable=False)
    precio_cf = db.Column(Numeric(12, 2), default=0, nullable=False)
    precio_minorista = db.Column(Numeric(12, 2), default=0, nullable=False)
    precio_mayorista = db.Column(Numeric(12, 2), default=0, nullable=False)
    stock_actual = db.Column(Numeric(12, 4), default=0, nullable=False)
    stock_reservado = db.Column(Numeric(12, 4), default=0, nullable=False)
    stock_minimo = db.Column(Numeric(12, 4), default=0, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    categoria = db.relationship("CategoriaProducto", back_populates="productos")
    bom_items = db.relationship(
        "ProductoMateriaPrima", back_populates="producto", lazy="dynamic"
    )
    componentes = db.relationship(
        "ProductoComponente",
        foreign_keys="ProductoComponente.producto_id",
        back_populates="producto",
        lazy="dynamic",
    )
    usado_en_componentes = db.relationship(
        "ProductoComponente",
        foreign_keys="ProductoComponente.componente_id",
        back_populates="componente",
        lazy="dynamic",
    )
    consumos_componentes = db.relationship(
        "ConsumoProductoComponente", back_populates="componente", lazy="dynamic"
    )
    ruta_procesos = db.relationship(
        "ProductoProceso", back_populates="producto", lazy="dynamic"
    )
    ordenes_produccion = db.relationship(
        "OrdenProduccion", back_populates="producto", lazy="dynamic"
    )

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
    activo = db.Column(db.Boolean, default=True, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    ordenes = db.relationship("Orden", back_populates="cliente", lazy="dynamic")
    pagos_banco = db.relationship("Bancos", back_populates="cliente", lazy="dynamic")
    usuario = db.relationship("Usuario", back_populates="clientes")

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
    clientes = db.relationship("Cliente", back_populates="usuario", lazy="dynamic")

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
    codigo_orden = db.Column(db.String(100), unique=True)
    fecha = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    fecha_envio = db.Column(db.Date)
    fecha_pago = db.Column(db.Date)
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


class MateriaPrima(db.Model):
    __tablename__ = "materias_primas"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    codigo = db.Column(db.String(80), unique=True, nullable=False, index=True)
    unidad = db.Column(db.String(50), nullable=False)
    costo_unitario = db.Column(Numeric(12, 4), default=0, nullable=False)
    stock_actual = db.Column(Numeric(12, 4), default=0, nullable=False)
    stock_reservado = db.Column(Numeric(12, 4), default=0, nullable=False)
    stock_minimo = db.Column(Numeric(12, 4), default=0, nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    bom_productos = db.relationship(
        "ProductoMateriaPrima", back_populates="materia_prima", lazy="dynamic"
    )
    consumos = db.relationship(
        "ConsumoMateriaPrima", back_populates="materia_prima", lazy="dynamic"
    )
    ajustes = db.relationship(
        "MateriaPrimaAjuste", back_populates="materia_prima", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<MateriaPrima {self.codigo}>"


class ProductoMateriaPrima(db.Model):
    __tablename__ = "productos_materias_primas"
    __table_args__ = (
        db.UniqueConstraint("producto_id", "materia_prima_id", name="uq_producto_mp"),
    )

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    materia_prima_id = db.Column(
        db.Integer, db.ForeignKey("materias_primas.id"), nullable=False
    )
    proceso_id = db.Column(db.Integer, db.ForeignKey("procesos.id"))
    cantidad_necesaria = db.Column(Numeric(12, 4), nullable=False, default=0)
    merma_estandar = db.Column(Numeric(12, 4), default=0, nullable=False)
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    producto = db.relationship("Producto", back_populates="bom_items")
    materia_prima = db.relationship("MateriaPrima", back_populates="bom_productos")
    proceso = db.relationship("Proceso")

    def __repr__(self) -> str:
        return f"<ProductoMateriaPrima {self.producto_id}-{self.materia_prima_id}>"


class ProductoComponente(db.Model):
    __tablename__ = "productos_componentes"
    __table_args__ = (
        db.UniqueConstraint(
            "producto_id", "componente_id", name="uq_producto_componente"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    componente_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    proceso_id = db.Column(db.Integer, db.ForeignKey("procesos.id"))
    cantidad_necesaria = db.Column(Numeric(12, 4), nullable=False, default=0)
    merma_estandar = db.Column(Numeric(12, 4), default=0, nullable=False)
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    producto = db.relationship(
        "Producto", foreign_keys=[producto_id], back_populates="componentes"
    )
    componente = db.relationship(
        "Producto", foreign_keys=[componente_id], back_populates="usado_en_componentes"
    )
    proceso = db.relationship("Proceso")

    def __repr__(self) -> str:
        return f"<ProductoComponente {self.producto_id}-{self.componente_id}>"


class Proceso(db.Model):
    __tablename__ = "procesos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), unique=True, nullable=False)
    descripcion = db.Column(db.String(255))
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    ruta_productos = db.relationship(
        "ProductoProceso", back_populates="proceso", lazy="dynamic"
    )
    procesos_orden = db.relationship(
        "ProcesoOrden", back_populates="proceso", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Proceso {self.nombre}>"


class ProductoProceso(db.Model):
    __tablename__ = "productos_procesos"
    __table_args__ = (
        db.UniqueConstraint("producto_id", "orden", name="uq_producto_proceso_orden"),
        db.UniqueConstraint(
            "producto_id", "proceso_id", name="uq_producto_proceso"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    proceso_id = db.Column(db.Integer, db.ForeignKey("procesos.id"), nullable=False)
    orden = db.Column(db.Integer, nullable=False)
    tiempo_objetivo_min = db.Column(db.Integer)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    producto = db.relationship("Producto", back_populates="ruta_procesos")
    proceso = db.relationship("Proceso", back_populates="ruta_productos")

    def __repr__(self) -> str:
        return f"<ProductoProceso {self.producto_id}-{self.proceso_id} ({self.orden})>"


class OrdenProduccion(db.Model):
    __tablename__ = "ordenes_produccion"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(100), unique=True, nullable=False, index=True)
    producto_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad_planeada = db.Column(Numeric(12, 4), nullable=False, default=0)
    cantidad_final_buena = db.Column(Numeric(12, 4))
    estado = db.Column(db.String(30), nullable=False, default="BORRADOR")
    fecha_inicio = db.Column(db.DateTime)
    fecha_fin = db.Column(db.DateTime)
    prioridad = db.Column(db.String(20))
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    producto = db.relationship("Producto", back_populates="ordenes_produccion")
    procesos = db.relationship(
        "ProcesoOrden", back_populates="orden_produccion", lazy="dynamic"
    )
    consumos = db.relationship(
        "ConsumoMateriaPrima", back_populates="orden_produccion", lazy="dynamic"
    )
    consumos_componentes = db.relationship(
        "ConsumoProductoComponente", back_populates="orden_produccion", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<OrdenProduccion {self.codigo}>"


class ProcesoOrden(db.Model):
    __tablename__ = "procesos_orden"
    __table_args__ = (
        db.UniqueConstraint(
            "orden_produccion_id", "orden", name="uq_orden_proceso_orden"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(
        db.Integer, db.ForeignKey("ordenes_produccion.id"), nullable=False
    )
    proceso_id = db.Column(db.Integer, db.ForeignKey("procesos.id"), nullable=False)
    orden = db.Column(db.Integer, nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="PENDIENTE")
    inicio = db.Column(db.DateTime)
    fin = db.Column(db.DateTime)
    cantidad_entrada = db.Column(Numeric(12, 4))
    cantidad_salida = db.Column(Numeric(12, 4))
    cantidad_perdida = db.Column(Numeric(12, 4))
    motivo_perdida = db.Column(db.String(255))
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    orden_produccion = db.relationship(
        "OrdenProduccion", back_populates="procesos"
    )
    proceso = db.relationship("Proceso", back_populates="procesos_orden")
    consumos = db.relationship(
        "ConsumoMateriaPrima", back_populates="proceso_orden", lazy="dynamic"
    )
    consumos_componentes = db.relationship(
        "ConsumoProductoComponente", back_populates="proceso_orden", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<ProcesoOrden {self.orden_produccion_id}-{self.orden}>"


class ConsumoMateriaPrima(db.Model):
    __tablename__ = "consumos_materia_prima"

    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(
        db.Integer, db.ForeignKey("ordenes_produccion.id"), nullable=False
    )
    proceso_orden_id = db.Column(db.Integer, db.ForeignKey("procesos_orden.id"))
    materia_prima_id = db.Column(
        db.Integer, db.ForeignKey("materias_primas.id"), nullable=False
    )
    cantidad_teorica = db.Column(Numeric(12, 4), default=0, nullable=False)
    cantidad_real = db.Column(Numeric(12, 4))
    desperdicio = db.Column(Numeric(12, 4))
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    orden_produccion = db.relationship(
        "OrdenProduccion", back_populates="consumos"
    )
    proceso_orden = db.relationship("ProcesoOrden", back_populates="consumos")
    materia_prima = db.relationship("MateriaPrima", back_populates="consumos")

    def __repr__(self) -> str:
        return f"<ConsumoMateriaPrima {self.id} Orden {self.orden_produccion_id}>"


class ConsumoProductoComponente(db.Model):
    __tablename__ = "consumos_componentes_producto"

    id = db.Column(db.Integer, primary_key=True)
    orden_produccion_id = db.Column(
        db.Integer, db.ForeignKey("ordenes_produccion.id"), nullable=False
    )
    proceso_orden_id = db.Column(db.Integer, db.ForeignKey("procesos_orden.id"))
    componente_id = db.Column(db.Integer, db.ForeignKey("productos.id"), nullable=False)
    cantidad_teorica = db.Column(Numeric(12, 4), default=0, nullable=False)
    cantidad_real = db.Column(Numeric(12, 4))
    desperdicio = db.Column(Numeric(12, 4))
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    orden_produccion = db.relationship(
        "OrdenProduccion", back_populates="consumos_componentes"
    )
    proceso_orden = db.relationship(
        "ProcesoOrden", back_populates="consumos_componentes"
    )
    componente = db.relationship(
        "Producto", back_populates="consumos_componentes"
    )

    def __repr__(self) -> str:
        return f"<ConsumoProductoComponente {self.id} Orden {self.orden_produccion_id}>"


class MateriaPrimaAjuste(db.Model):
    __tablename__ = "materias_primas_ajustes"

    id = db.Column(db.Integer, primary_key=True)
    materia_prima_id = db.Column(
        db.Integer, db.ForeignKey("materias_primas.id"), nullable=False
    )
    tipo = db.Column(db.String(20), nullable=False)
    cantidad = db.Column(Numeric(12, 4), nullable=False, default=0)
    motivo = db.Column(db.String(255))
    observaciones = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actualizado_en = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    materia_prima = db.relationship("MateriaPrima", back_populates="ajustes")

    def __repr__(self) -> str:
        return f"<MateriaPrimaAjuste {self.materia_prima_id} {self.tipo}>"
