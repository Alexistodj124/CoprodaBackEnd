from datetime import date, datetime, timedelta
from decimal import Decimal
import re

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.wrappers import Response

from config import Config
from models import (
    Bancos,
    CategoriaProducto,
    Cliente,
    ConsumoMateriaPrima,
    ConsumoProductoComponente,
    EstadoOrden,
    MateriaPrima,
    MateriaPrimaAjuste,
    Permiso,
    Proceso,
    ProcesoOrden,
    Producto,
    ProductoComponente,
    ProductoMateriaPrima,
    ProductoProceso,
    TipoPago,
    Usuario,
    OrdenProduccion,
    Orden,
    OrdenItem,
    db,
)



migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Habilitar CORS para el front (localhost:5173)
    CORS(app, resources={r"/*": {"origins": "*"}})
    # Si quieres permitir cualquier origen durante desarrollo:
    # CORS(app)

    db.init_app(app)
    migrate.init_app(app, db)

    @app.route("/")
    def index():
        return jsonify({"message": "API funcionando"})

    @app.route("/auth/login", methods=["POST"])
    def login():
        """
        Login básico.

        Espera JSON:
        {
        "usuario": "ana",
        "contrasena": "mi_contrasena"
        }

        Responde 200 si las credenciales son correctas,
        401 si no.
        """
        data = request.get_json(silent=True) or {}
        nombre_usuario = (data.get("usuario") or data.get("username") or "").strip()
        contrasena = data.get("contrasena") or data.get("password")

        if not nombre_usuario or not contrasena:
            return jsonify({"error": "usuario y contrasena son requeridos"}), 400

        usuario = Usuario.query.filter_by(usuario=nombre_usuario).first()
        if not usuario or not usuario.check_password(contrasena):
            return jsonify({"error": "credenciales invalidas"}), 401

        return jsonify(
            {
                "id": usuario.id,
                "usuario": usuario.usuario,
                "activo": usuario.activo,
                "permisos": [p.nombre for p in usuario.permisos.all()],
            }
        )

    # ---------- CRUD PRODUCTOS ----------

    def categoria_to_dict(categoria: CategoriaProducto) -> dict:
        return {
            "id": categoria.id,
            "nombre": categoria.nombre,
            "descripcion": categoria.descripcion,
            "creada_en": categoria.creada_en.isoformat() if categoria.creada_en else None,
            "actualizada_en": categoria.actualizada_en.isoformat()
            if categoria.actualizada_en
            else None,
        }

    @app.route("/categorias_producto", methods=["GET"])
    def listar_categorias_producto():
        categorias = CategoriaProducto.query.order_by(CategoriaProducto.id).all()
        return jsonify([categoria_to_dict(c) for c in categorias])

    @app.route("/categorias_producto/<int:categoria_id>", methods=["GET"])
    def obtener_categoria_producto(categoria_id: int):
        categoria = CategoriaProducto.query.get_or_404(categoria_id)
        return jsonify(categoria_to_dict(categoria))

    @app.route("/categorias_producto", methods=["POST"])
    def crear_categoria_producto():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        descripcion = (data.get("descripcion") or "").strip() or None

        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400

        existente = CategoriaProducto.query.filter_by(nombre=nombre).first()
        if existente:
            return jsonify({"error": "Ya existe una categoría con ese nombre"}), 409

        categoria = CategoriaProducto(nombre=nombre, descripcion=descripcion)
        db.session.add(categoria)
        db.session.commit()
        return jsonify(categoria_to_dict(categoria)), 201

    @app.route("/categorias_producto/<int:categoria_id>", methods=["PUT", "PATCH"])
    def actualizar_categoria_producto(categoria_id: int):
        categoria = CategoriaProducto.query.get_or_404(categoria_id)
        data = request.get_json(silent=True) or {}

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            conflicto = (
                CategoriaProducto.query.filter_by(nombre=nombre)
                .filter(CategoriaProducto.id != categoria.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe una categoría con ese nombre"}), 409
            categoria.nombre = nombre

        if "descripcion" in data:
            descripcion = (data.get("descripcion") or "").strip() or None
            categoria.descripcion = descripcion

        db.session.commit()
        return jsonify(categoria_to_dict(categoria))

    @app.route("/categorias_producto/<int:categoria_id>", methods=["DELETE"])
    def eliminar_categoria_producto(categoria_id: int):
        categoria = CategoriaProducto.query.get_or_404(categoria_id)
        db.session.delete(categoria)
        db.session.commit()
        return jsonify({"message": "Categoría eliminada"})

    def producto_to_dict(producto: Producto) -> dict:
        return {
            "id": producto.id,
            "nombre": producto.nombre,
            "foto": producto.foto,
            "codigo": producto.codigo,
            "categoria_id": producto.categoria_id,
            "activo": producto.activo,
            "es_producto_final": producto.es_producto_final,
            "precio_cf": float(producto.precio_cf),
            "precio_minorista": float(producto.precio_minorista),
            "precio_mayorista": float(producto.precio_mayorista),
            "stock_actual": float(producto.stock_actual or 0),
            "stock_reservado": float(producto.stock_reservado or 0),
            "stock_minimo": float(producto.stock_minimo or 0),
            "creado_en": producto.creado_en.isoformat() if producto.creado_en else None,
            "actualizado_en": producto.actualizado_en.isoformat()
            if producto.actualizado_en
            else None,
        }

    @app.route("/productos", methods=["GET"])
    def listar_productos():
        productos = Producto.query.order_by(Producto.id).all()
        return jsonify([producto_to_dict(p) for p in productos])

    @app.route("/productos/<int:producto_id>", methods=["GET"])
    def obtener_producto(producto_id: int):
        producto = Producto.query.get_or_404(producto_id)
        return jsonify(producto_to_dict(producto))

    def _parse_precio(value, field_name: str):
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"El campo {field_name} debe ser numérico")

    def _parse_decimal(value, field_name: str, default=None):
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        try:
            return Decimal(str(value))
        except (TypeError, ValueError):
            raise ValueError(f"El campo {field_name} debe ser numérico")

    @app.route("/productos", methods=["POST"])
    def crear_producto():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        codigo = (data.get("codigo") or "").strip()
        foto = (data.get("foto") or "").strip() or None
        categoria_id = data.get("categoria_id")
        activo = _parse_bool(data.get("activo"), default=True)
        es_producto_final = _parse_bool(
            data.get("es_producto_final"), default=True
        )
        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400
        if not codigo:
            return jsonify({"error": "El código es requerido"}), 400
        if categoria_id is None:
            return jsonify({"error": "La categoría es requerida"}), 400

        conflicto = Producto.query.filter_by(codigo=codigo).first()
        if conflicto:
            return jsonify({"error": "Ya existe un producto con ese código"}), 409

        categoria = CategoriaProducto.query.get(categoria_id)
        if not categoria:
            return jsonify({"error": "Categoría no encontrada"}), 404

        try:
            precio_cf = _parse_precio(data.get("precio_cf", 0), "precio_cf") or 0
            precio_minorista = _parse_precio(
                data.get("precio_minorista", 0), "precio_minorista"
            ) or 0
            precio_mayorista = _parse_precio(
                data.get("precio_mayorista", 0), "precio_mayorista"
            ) or 0
            stock_actual = _parse_decimal(
                data.get("stock_actual", 0), "stock_actual", default=Decimal("0")
            )
            stock_reservado = _parse_decimal(
                data.get("stock_reservado", 0),
                "stock_reservado",
                default=Decimal("0"),
            )
            stock_minimo = _parse_decimal(
                data.get("stock_minimo", 0), "stock_minimo", default=Decimal("0")
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        producto = Producto(
            nombre=nombre,
            codigo=codigo,
            foto=foto,
            categoria_id=categoria_id,
            activo=activo,
            es_producto_final=es_producto_final,
            precio_cf=precio_cf,
            precio_minorista=precio_minorista,
            precio_mayorista=precio_mayorista,
            stock_actual=stock_actual or 0,
            stock_reservado=stock_reservado or 0,
            stock_minimo=stock_minimo or 0,
        )
        db.session.add(producto)
        db.session.commit()
        return jsonify(producto_to_dict(producto)), 201

    @app.route("/productos/<int:producto_id>", methods=["PUT", "PATCH"])
    def actualizar_producto(producto_id: int):
        producto = Producto.query.get_or_404(producto_id)
        data = request.get_json(silent=True) or {}

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            producto.nombre = nombre

        if "codigo" in data:
            codigo = (data.get("codigo") or "").strip()
            if not codigo:
                return jsonify({"error": "El código es requerido"}), 400
            conflicto = (
                Producto.query.filter_by(codigo=codigo)
                .filter(Producto.id != producto.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe un producto con ese código"}), 409
            producto.codigo = codigo

        if "sku" in data:
            sku = (data.get("sku") or "").strip() or None
            if sku:
                conflicto = (
                    Producto.query.filter_by(sku=sku)
                    .filter(Producto.id != producto.id)
                    .first()
                )
                if conflicto:
                    return jsonify({"error": "Ya existe un producto con ese sku"}), 409
            producto.sku = sku

        if "foto" in data:
            producto.foto = (data.get("foto") or "").strip() or None

        if "categoria_id" in data:
            categoria_id = data.get("categoria_id")
            categoria = CategoriaProducto.query.get(categoria_id)
            if not categoria:
                return jsonify({"error": "Categoría no encontrada"}), 404
            producto.categoria_id = categoria_id

        if "activo" in data:
            producto.activo = _parse_bool(data.get("activo"), default=producto.activo)

        if "es_producto_final" in data:
            producto.es_producto_final = _parse_bool(
                data.get("es_producto_final"), default=producto.es_producto_final
            )

        if "unidad_produccion" in data:
            producto.unidad_produccion = (
                (data.get("unidad_produccion") or "").strip() or None
            )

        if "lead_time_objetivo_min" in data:
            producto.lead_time_objetivo_min = data.get("lead_time_objetivo_min")

        if "peso_unitario_est" in data:
            try:
                producto.peso_unitario_est = (
                    _parse_precio(data.get("peso_unitario_est"), "peso_unitario_est")
                    or 0
                )
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        if "version_bom" in data:
            producto.version_bom = data.get("version_bom") or producto.version_bom

        if "notas_produccion" in data:
            producto.notas_produccion = (
                (data.get("notas_produccion") or "").strip() or None
            )

        try:
            if "precio_cf" in data:
                producto.precio_cf = _parse_precio(data.get("precio_cf"), "precio_cf")
            if "precio_minorista" in data:
                producto.precio_minorista = _parse_precio(
                    data.get("precio_minorista"), "precio_minorista"
                )
            if "precio_mayorista" in data:
                producto.precio_mayorista = _parse_precio(
                    data.get("precio_mayorista"), "precio_mayorista"
                )
            if "stock_actual" in data:
                producto.stock_actual = _parse_decimal(
                    data.get("stock_actual"), "stock_actual"
                )
            if "stock_reservado" in data:
                producto.stock_reservado = _parse_decimal(
                    data.get("stock_reservado"), "stock_reservado"
                )
            if "stock_minimo" in data:
                producto.stock_minimo = _parse_decimal(
                    data.get("stock_minimo"), "stock_minimo"
                )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        db.session.commit()
        return jsonify(producto_to_dict(producto))

    @app.route("/productos/<int:producto_id>", methods=["DELETE"])
    def eliminar_producto(producto_id: int):
        producto = Producto.query.get_or_404(producto_id)
        db.session.delete(producto)
        db.session.commit()
        return jsonify({"message": "Producto eliminado"})

    def cliente_to_dict(cliente: Cliente) -> dict:
        return {
            "id": cliente.id,
            "codigo": cliente.codigo,
            "nombre": cliente.nombre,
            "telefono": cliente.telefono,
            "direccion": cliente.direccion,
            "clasificacion_precio": cliente.clasificacion_precio,
            "saldo": float(cliente.saldo),
            "activo": cliente.activo,
            "usuario_id": cliente.usuario_id,
            "creado_en": cliente.creado_en.isoformat() if cliente.creado_en else None,
            "actualizado_en": cliente.actualizado_en.isoformat()
            if cliente.actualizado_en
            else None,
        }

    @app.route("/clientes", methods=["GET"])
    def listar_clientes():
        clientes = Cliente.query.order_by(Cliente.id).all()
        return jsonify([cliente_to_dict(c) for c in clientes])

    @app.route("/clientes/<int:cliente_id>", methods=["GET"])
    def obtener_cliente(cliente_id: int):
        cliente = Cliente.query.get_or_404(cliente_id)
        return jsonify(cliente_to_dict(cliente))

    @app.route("/clientes", methods=["POST"])
    def crear_cliente():
        data = request.get_json(silent=True) or {}
        codigo = (data.get("codigo") or "").strip()
        nombre = (data.get("nombre") or "").strip()
        telefono = (data.get("telefono") or "").strip() or None
        direccion = (data.get("direccion") or "").strip() or None
        clasificacion_precio = (data.get("clasificacion_precio") or "cf").strip().lower()
        saldo_val = data.get("saldo", 0)
        activo = _parse_bool(data.get("activo"), default=True)
        usuario_id = data.get("usuario_id")

        if not codigo:
            return jsonify({"error": "El código es requerido"}), 400
        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400

        conflicto = Cliente.query.filter_by(codigo=codigo).first()
        if conflicto:
            return jsonify({"error": "Ya existe un cliente con ese código"}), 409

        if clasificacion_precio not in ("cf", "minorista", "mayorista"):
            return (
                jsonify(
                    {"error": "clasificacion_precio debe ser cf, minorista o mayorista"}
                ),
                400,
            )

        try:
            saldo = _parse_precio(saldo_val, "saldo") or 0
            _validate_fk(Usuario, usuario_id, "usuario_id")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

        cliente = Cliente(
            codigo=codigo,
            nombre=nombre,
            telefono=telefono,
            direccion=direccion,
            clasificacion_precio=clasificacion_precio,
            saldo=saldo,
            activo=activo,
            usuario_id=usuario_id,
        )
        db.session.add(cliente)
        db.session.commit()
        return jsonify(cliente_to_dict(cliente)), 201

    @app.route("/clientes/<int:cliente_id>", methods=["PUT", "PATCH"])
    def actualizar_cliente(cliente_id: int):
        cliente = Cliente.query.get_or_404(cliente_id)
        data = request.get_json(silent=True) or {}

        if "codigo" in data:
            codigo = (data.get("codigo") or "").strip()
            if not codigo:
                return jsonify({"error": "El código es requerido"}), 400
            conflicto = (
                Cliente.query.filter_by(codigo=codigo)
                .filter(Cliente.id != cliente.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe un cliente con ese código"}), 409
            cliente.codigo = codigo

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            cliente.nombre = nombre

        if "telefono" in data:
            cliente.telefono = (data.get("telefono") or "").strip() or None

        if "direccion" in data:
            cliente.direccion = (data.get("direccion") or "").strip() or None

        if "clasificacion_precio" in data:
            clasificacion_precio = (data.get("clasificacion_precio") or "").strip().lower()
            if clasificacion_precio not in ("cf", "minorista", "mayorista"):
                return (
                    jsonify(
                        {
                            "error": "clasificacion_precio debe ser cf, minorista o mayorista"
                        }
                    ),
                    400,
                )
            cliente.clasificacion_precio = clasificacion_precio

        if "saldo" in data:
            try:
                cliente.saldo = _parse_precio(data.get("saldo"), "saldo") or 0
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        if "activo" in data:
            cliente.activo = _parse_bool(data.get("activo"), default=cliente.activo)

        if "usuario_id" in data:
            try:
                _validate_fk(Usuario, data.get("usuario_id"), "usuario_id")
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404
            cliente.usuario_id = data.get("usuario_id")

        db.session.commit()
        return jsonify(cliente_to_dict(cliente))

    @app.route("/clientes/<int:cliente_id>", methods=["DELETE"])
    def eliminar_cliente(cliente_id: int):
        cliente = Cliente.query.get_or_404(cliente_id)
        db.session.delete(cliente)
        db.session.commit()
        return jsonify({"message": "Cliente eliminado"})

    def _parse_fecha(value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            if isinstance(value, str):
                return datetime.fromisoformat(value).date()
            return value
        except (ValueError, TypeError):
            raise ValueError("El formato de fecha debe ser YYYY-MM-DD")

    def _parse_datetime(value, field_name: str):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            return value
        except (ValueError, TypeError):
            raise ValueError(f"El campo {field_name} debe ser datetime ISO")

    def _parse_bool(value, default=None):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            val = value.strip().lower()
            if val in ("true", "1", "t", "yes", "y"):
                return True
            if val in ("false", "0", "f", "no", "n"):
                return False
        return bool(value)

    def _dias_credito_from_tipo_pago(tipo_pago: TipoPago) -> int:
        if not tipo_pago or not tipo_pago.nombre:
            return 0
        match = re.search(r"\d+", tipo_pago.nombre)
        return int(match.group()) if match else 0

    def banco_to_dict(banco: Bancos) -> dict:
        return {
            "id": banco.id,
            "fecha": banco.fecha.isoformat() if banco.fecha else None,
            "referencia": banco.referencia,
            "banco": banco.banco,
            "monto": float(banco.monto),
            "nota": banco.nota,
            "asignado": banco.asignado,
            "cliente_id": banco.cliente_id,
            "creado_en": banco.creado_en.isoformat() if banco.creado_en else None,
            "actualizado_en": banco.actualizado_en.isoformat()
            if banco.actualizado_en
            else None,
        }

    @app.route("/bancos", methods=["GET"])
    def listar_bancos():
        pagos = Bancos.query.order_by(Bancos.id).all()
        return jsonify([banco_to_dict(p) for p in pagos])

    @app.route("/bancos/<int:banco_id>", methods=["GET"])
    def obtener_banco(banco_id: int):
        pago = Bancos.query.get_or_404(banco_id)
        return jsonify(banco_to_dict(pago))

    @app.route("/bancos", methods=["POST"])
    def crear_banco():
        data = request.get_json(silent=True) or {}

        referencia = (data.get("referencia") or "").strip()
        nombre_banco = (data.get("banco") or "").strip()
        monto_val = data.get("monto")
        nota = (data.get("nota") or "").strip() or None
        asignado = _parse_bool(data.get("asignado"), default=False)
        cliente_id = data.get("cliente_id")

        if not referencia:
            return jsonify({"error": "La referencia es requerida"}), 400
        if not nombre_banco:
            return jsonify({"error": "El banco es requerido"}), 400
        try:
            monto = _parse_precio(monto_val, "monto")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if monto is None:
            return jsonify({"error": "El monto es requerido"}), 400

        try:
            fecha = _parse_fecha(data.get("fecha"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if cliente_id is not None:
            cliente = Cliente.query.get(cliente_id)
            if not cliente:
                return jsonify({"error": "Cliente no encontrado"}), 404

        pago = Bancos(
            fecha=fecha,
            referencia=referencia,
            banco=nombre_banco,
            monto=monto,
            nota=nota,
            asignado=asignado,
            cliente_id=cliente_id,
        )
        db.session.add(pago)
        db.session.commit()
        return jsonify(banco_to_dict(pago)), 201

    @app.route("/bancos/<int:banco_id>", methods=["PUT", "PATCH"])
    def actualizar_banco(banco_id: int):
        pago = Bancos.query.get_or_404(banco_id)
        data = request.get_json(silent=True) or {}

        if "referencia" in data:
            referencia = (data.get("referencia") or "").strip()
            if not referencia:
                return jsonify({"error": "La referencia es requerida"}), 400
            pago.referencia = referencia

        if "banco" in data:
            nombre_banco = (data.get("banco") or "").strip()
            if not nombre_banco:
                return jsonify({"error": "El banco es requerido"}), 400
            pago.banco = nombre_banco

        if "monto" in data:
            try:
                nuevo_monto = _parse_precio(data.get("monto"), "monto")
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            if nuevo_monto is None:
                return jsonify({"error": "El monto es requerido"}), 400
            pago.monto = nuevo_monto

        if "nota" in data:
            pago.nota = (data.get("nota") or "").strip() or None

        if "asignado" in data:
            pago.asignado = _parse_bool(data.get("asignado"), default=pago.asignado)

        if "fecha" in data:
            try:
                pago.fecha = _parse_fecha(data.get("fecha"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        if "cliente_id" in data:
            cliente_id = data.get("cliente_id")
            if cliente_id is not None:
                cliente = Cliente.query.get(cliente_id)
                if not cliente:
                    return jsonify({"error": "Cliente no encontrado"}), 404
            pago.cliente_id = cliente_id

        db.session.commit()
        return jsonify(banco_to_dict(pago))

    @app.route("/bancos/<int:banco_id>", methods=["DELETE"])
    def eliminar_banco(banco_id: int):
        pago = Bancos.query.get_or_404(banco_id)
        if pago.asignado:
            cliente = Cliente.query.get(pago.cliente_id)
            if not cliente:
                return jsonify({"error": "Cliente no encontrado"}), 404
            if pago.monto is None or pago.monto <= 0:
                return jsonify({"error": "El monto del banco debe ser mayor que cero"}), 400

            today = date.today()

            def _dias_restantes(orden: Orden) -> int:
                dias_credito = _dias_credito_from_tipo_pago(orden.tipo_pago)
                fecha_base = orden.fecha_envio or orden.fecha or today
                vencimiento = fecha_base + timedelta(days=dias_credito)
                return (vencimiento - today).days

            ordenes = Orden.query.filter_by(cliente_id=cliente.id).all()
            ordenes_ordenadas = sorted(
                ordenes,
                key=lambda orden: (
                    _dias_restantes(orden),
                    orden.fecha_envio or orden.fecha or date.min,
                    orden.id,
                ),
            )

            restante = Decimal(pago.monto)
            for orden in ordenes_ordenadas:
                if restante <= 0:
                    break
                total = Decimal(orden.total)
                saldo_actual = Decimal(orden.saldo)
                pagado = total - saldo_actual
                if pagado <= 0:
                    continue
                revertir = pagado if pagado <= restante else restante
                orden.saldo = saldo_actual + revertir
                if orden.estado_id == 4:
                    orden.estado_id = 3
                restante -= revertir

            cliente.saldo = (cliente.saldo or 0) + Decimal(pago.monto)

        db.session.delete(pago)
        db.session.commit()
        return jsonify({"message": "Pago eliminado"})

    @app.route("/ordenes/abonos", methods=["POST"])
    def crear_abono_orden():
        data = request.get_json(silent=True) or {}
        cliente_id = data.get("cliente_id")
        banco_id = data.get("banco_id")

        if cliente_id is None:
            return jsonify({"error": "cliente_id es requerido"}), 400
        if banco_id is None:
            return jsonify({"error": "banco_id es requerido"}), 400

        cliente = Cliente.query.get(cliente_id)
        if not cliente:
            return jsonify({"error": "Cliente no encontrado"}), 404

        banco = Bancos.query.get(banco_id)
        if not banco:
            return jsonify({"error": "Banco no encontrado"}), 404
        if banco.asignado:
            return jsonify({"error": "El pago del banco ya fue asignado"}), 409
        if banco.monto is None or banco.monto <= 0:
            return jsonify({"error": "El monto del banco debe ser mayor que cero"}), 400

        ordenes = (
            Orden.query.filter_by(cliente_id=cliente_id)
            .filter(Orden.saldo > 0)
            .filter(Orden.estado_id != 4)
            .all()
        )
        if not ordenes:
            return jsonify({"error": "No hay ordenes con saldo"}), 404

        today = date.today()

        def _dias_restantes(orden: Orden) -> int:
            dias_credito = _dias_credito_from_tipo_pago(orden.tipo_pago)
            fecha_base = orden.fecha_envio or orden.fecha or today
            vencimiento = fecha_base + timedelta(days=dias_credito)
            return (vencimiento - today).days

        ordenes_ordenadas = sorted(
            ordenes,
            key=lambda orden: (
                _dias_restantes(orden),
                orden.fecha_envio or orden.fecha or date.min,
                orden.id,
            ),
        )

        restante = Decimal(banco.monto)
        asignaciones = []
        for orden in ordenes_ordenadas:
            if restante <= 0:
                break
            saldo_actual = Decimal(orden.saldo)
            if saldo_actual <= 0:
                continue
            aplicar = saldo_actual if saldo_actual <= restante else restante
            nuevo_saldo = saldo_actual - aplicar
            if nuevo_saldo <= 0:
                orden.saldo = Decimal("0.00")
                orden.estado_id = 4
                orden.fecha_pago = date.today()
            else:
                orden.saldo = nuevo_saldo
            restante -= aplicar
            asignaciones.append(
                {
                    "orden_id": orden.id,
                    "aplicado": float(aplicar),
                    "saldo_nuevo": float(orden.saldo),
                    "estado_id": orden.estado_id,
                }
            )

        banco.asignado = True
        banco.cliente_id = cliente_id
        # Permite saldo a favor en el mismo campo cuando el abono excede el saldo total.
        cliente.saldo = (cliente.saldo or 0) - Decimal(banco.monto)

        db.session.commit()
        return (
            jsonify(
                {
                    "banco_id": banco.id,
                    "cliente_id": cliente_id,
                    "monto": float(banco.monto),
                    "restante": float(restante),
                    "asignaciones": asignaciones,
                }
            ),
            200,
        )

    def usuario_to_dict(usuario: Usuario) -> dict:
        return {
            "id": usuario.id,
            "usuario": usuario.usuario,
            "activo": usuario.activo,
            "permisos": [p.nombre for p in usuario.permisos.all()],
            "creado_en": usuario.creado_en.isoformat() if usuario.creado_en else None,
            "actualizado_en": usuario.actualizado_en.isoformat()
            if usuario.actualizado_en
            else None,
        }

    @app.route("/usuarios", methods=["GET"])
    def listar_usuarios():
        usuarios = Usuario.query.order_by(Usuario.id).all()
        return jsonify([usuario_to_dict(u) for u in usuarios])

    @app.route("/usuarios/<int:usuario_id>", methods=["GET"])
    def obtener_usuario(usuario_id: int):
        usuario = Usuario.query.get_or_404(usuario_id)
        return jsonify(usuario_to_dict(usuario))

    def _get_permisos_from_payload(permisos_nombres):
        if permisos_nombres is None:
            return []
        if not isinstance(permisos_nombres, list):
            raise ValueError("permisos debe ser una lista de nombres")
        permisos = []
        for nombre in permisos_nombres:
            if not isinstance(nombre, str) or not nombre.strip():
                raise ValueError("Cada permiso debe ser un string no vacío")
            perm = Permiso.query.filter_by(nombre=nombre.strip()).first()
            if not perm:
                perm = Permiso(nombre=nombre.strip())
                db.session.add(perm)
            permisos.append(perm)
        return permisos

    @app.route("/usuarios", methods=["POST"])
    def crear_usuario():
        data = request.get_json(silent=True) or {}
        nombre_usuario = (data.get("usuario") or "").strip()
        contrasena = data.get("contrasena")
        activo = _parse_bool(data.get("activo"), default=True)
        permisos_nombres = data.get("permisos")

        if not nombre_usuario:
            return jsonify({"error": "El usuario es requerido"}), 400
        if not contrasena:
            return jsonify({"error": "La contraseña es requerida"}), 400

        conflicto = Usuario.query.filter_by(usuario=nombre_usuario).first()
        if conflicto:
            return jsonify({"error": "Ya existe un usuario con ese nombre"}), 409

        try:
            permisos = _get_permisos_from_payload(permisos_nombres)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        usuario = Usuario(usuario=nombre_usuario, activo=activo)
        usuario.set_password(contrasena)
        usuario.permisos.extend(permisos)
        db.session.add(usuario)
        db.session.commit()
        return jsonify(usuario_to_dict(usuario)), 201

    @app.route("/usuarios/<int:usuario_id>", methods=["PUT", "PATCH"])
    def actualizar_usuario(usuario_id: int):
        usuario = Usuario.query.get_or_404(usuario_id)
        data = request.get_json(silent=True) or {}

        if "usuario" in data:
            nombre_usuario = (data.get("usuario") or "").strip()
            if not nombre_usuario:
                return jsonify({"error": "El usuario es requerido"}), 400
            conflicto = (
                Usuario.query.filter_by(usuario=nombre_usuario)
                .filter(Usuario.id != usuario.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe un usuario con ese nombre"}), 409
            usuario.usuario = nombre_usuario

        if "contrasena" in data:
            contrasena = data.get("contrasena")
            if not contrasena:
                return jsonify({"error": "La contraseña es requerida"}), 400
            usuario.set_password(contrasena)

        if "activo" in data:
            usuario.activo = _parse_bool(data.get("activo"), default=usuario.activo)

        if "permisos" in data:
            permisos_nombres = data.get("permisos")
            try:
                nuevos_permisos = _get_permisos_from_payload(permisos_nombres)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            usuario.permisos = nuevos_permisos

        db.session.commit()
        return jsonify(usuario_to_dict(usuario))

    @app.route("/usuarios/<int:usuario_id>", methods=["DELETE"])
    def eliminar_usuario(usuario_id: int):
        usuario = Usuario.query.get_or_404(usuario_id)
        db.session.delete(usuario)
        db.session.commit()
        return jsonify({"message": "Usuario eliminado"})

    def permiso_to_dict(permiso: Permiso) -> dict:
        return {
            "id": permiso.id,
            "nombre": permiso.nombre,
            "creado_en": permiso.creado_en.isoformat() if permiso.creado_en else None,
            "actualizado_en": permiso.actualizado_en.isoformat()
            if permiso.actualizado_en
            else None,
        }

    @app.route("/permisos", methods=["GET"])
    def listar_permisos():
        permisos = Permiso.query.order_by(Permiso.id).all()
        return jsonify([permiso_to_dict(p) for p in permisos])

    @app.route("/permisos/<int:permiso_id>", methods=["GET"])
    def obtener_permiso(permiso_id: int):
        permiso = Permiso.query.get_or_404(permiso_id)
        return jsonify(permiso_to_dict(permiso))

    @app.route("/permisos", methods=["POST"])
    def crear_permiso():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()

        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400

        conflicto = Permiso.query.filter_by(nombre=nombre).first()
        if conflicto:
            return jsonify({"error": "Ya existe un permiso con ese nombre"}), 409

        permiso = Permiso(nombre=nombre)
        db.session.add(permiso)
        db.session.commit()
        return jsonify(permiso_to_dict(permiso)), 201

    @app.route("/permisos/<int:permiso_id>", methods=["PUT", "PATCH"])
    def actualizar_permiso(permiso_id: int):
        permiso = Permiso.query.get_or_404(permiso_id)
        data = request.get_json(silent=True) or {}

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            conflicto = (
                Permiso.query.filter_by(nombre=nombre)
                .filter(Permiso.id != permiso.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe un permiso con ese nombre"}), 409
            permiso.nombre = nombre

        db.session.commit()
        return jsonify(permiso_to_dict(permiso))

    @app.route("/permisos/<int:permiso_id>", methods=["DELETE"])
    def eliminar_permiso(permiso_id: int):
        permiso = Permiso.query.get_or_404(permiso_id)
        db.session.delete(permiso)
        db.session.commit()
        return jsonify({"message": "Permiso eliminado"})

    def tipopago_to_dict(tipopago: TipoPago) -> dict:
        return {
            "id": tipopago.id,
            "nombre": tipopago.nombre,
            "activo": tipopago.activo,
            "creado_en": tipopago.creado_en.isoformat() if tipopago.creado_en else None,
            "actualizado_en": tipopago.actualizado_en.isoformat()
            if tipopago.actualizado_en
            else None,
        }

    @app.route("/tipos_pago", methods=["GET"])
    def listar_tipos_pago():
        tipos = TipoPago.query.order_by(TipoPago.id).all()
        return jsonify([tipopago_to_dict(t) for t in tipos])

    @app.route("/tipos_pago/<int:tipopago_id>", methods=["GET"])
    def obtener_tipo_pago(tipopago_id: int):
        tipopago = TipoPago.query.get_or_404(tipopago_id)
        return jsonify(tipopago_to_dict(tipopago))

    @app.route("/tipos_pago", methods=["POST"])
    def crear_tipo_pago():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        activo = _parse_bool(data.get("activo"), default=True)

        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400

        conflicto = TipoPago.query.filter_by(nombre=nombre).first()
        if conflicto:
            return jsonify({"error": "Ya existe un tipo de pago con ese nombre"}), 409

        tipopago = TipoPago(nombre=nombre, activo=activo)
        db.session.add(tipopago)
        db.session.commit()
        return jsonify(tipopago_to_dict(tipopago)), 201

    @app.route("/tipos_pago/<int:tipopago_id>", methods=["PUT", "PATCH"])
    def actualizar_tipo_pago(tipopago_id: int):
        tipopago = TipoPago.query.get_or_404(tipopago_id)
        data = request.get_json(silent=True) or {}

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            conflicto = (
                TipoPago.query.filter_by(nombre=nombre)
                .filter(TipoPago.id != tipopago.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe un tipo de pago con ese nombre"}), 409
            tipopago.nombre = nombre

        if "activo" in data:
            tipopago.activo = _parse_bool(data.get("activo"), default=tipopago.activo)

        db.session.commit()
        return jsonify(tipopago_to_dict(tipopago))

    @app.route("/tipos_pago/<int:tipopago_id>", methods=["DELETE"])
    def eliminar_tipo_pago(tipopago_id: int):
        tipopago = TipoPago.query.get_or_404(tipopago_id)
        db.session.delete(tipopago)
        db.session.commit()
        return jsonify({"message": "Tipo de pago eliminado"})

    def estadoorden_to_dict(estado: EstadoOrden) -> dict:
        return {
            "id": estado.id,
            "nombre": estado.nombre,
            "creado_en": estado.creado_en.isoformat() if estado.creado_en else None,
            "actualizado_en": estado.actualizado_en.isoformat()
            if estado.actualizado_en
            else None,
        }

    @app.route("/estados_orden", methods=["GET"])
    def listar_estados_orden():
        estados = EstadoOrden.query.order_by(EstadoOrden.id).all()
        return jsonify([estadoorden_to_dict(e) for e in estados])

    @app.route("/estados_orden/<int:estado_id>", methods=["GET"])
    def obtener_estado_orden(estado_id: int):
        estado = EstadoOrden.query.get_or_404(estado_id)
        return jsonify(estadoorden_to_dict(estado))

    @app.route("/estados_orden", methods=["POST"])
    def crear_estado_orden():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()

        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400

        conflicto = EstadoOrden.query.filter_by(nombre=nombre).first()
        if conflicto:
            return jsonify({"error": "Ya existe un estado con ese nombre"}), 409

        estado = EstadoOrden(nombre=nombre)
        db.session.add(estado)
        db.session.commit()
        return jsonify(estadoorden_to_dict(estado)), 201

    @app.route("/estados_orden/<int:estado_id>", methods=["PUT", "PATCH"])
    def actualizar_estado_orden(estado_id: int):
        estado = EstadoOrden.query.get_or_404(estado_id)
        data = request.get_json(silent=True) or {}

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            conflicto = (
                EstadoOrden.query.filter_by(nombre=nombre)
                .filter(EstadoOrden.id != estado.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe un estado con ese nombre"}), 409
            estado.nombre = nombre

        db.session.commit()
        return jsonify(estadoorden_to_dict(estado))

    @app.route("/estados_orden/<int:estado_id>", methods=["DELETE"])
    def eliminar_estado_orden(estado_id: int):
        estado = EstadoOrden.query.get_or_404(estado_id)
        db.session.delete(estado)
        db.session.commit()
        return jsonify({"message": "Estado eliminado"})

    def ordenitem_to_dict(item: OrdenItem) -> dict:
        return {
            "id": item.id,
            "orden_id": item.orden_id,
            "producto_id": item.producto_id,
            "precio": float(item.precio),
            "cantidad": item.cantidad,
            "creado_en": item.creado_en.isoformat() if item.creado_en else None,
            "actualizado_en": item.actualizado_en.isoformat()
            if item.actualizado_en
            else None,
        }

    def orden_to_dict(orden: Orden) -> dict:
        return {
            "id": orden.id,
            "codigo_orden": orden.codigo_orden,
            "fecha": orden.fecha.isoformat() if orden.fecha else None,
            "fecha_envio": orden.fecha_envio.isoformat() if orden.fecha_envio else None,
            "fecha_pago": orden.fecha_pago.isoformat() if orden.fecha_pago else None,
            "usuario_id": orden.usuario_id,
            "tipo_pago_id": orden.tipo_pago_id,
            "estado_id": orden.estado_id,
            "cliente_id": orden.cliente_id,
            "total": float(orden.total),
            "saldo": float(orden.saldo),
            "items": [ordenitem_to_dict(i) for i in orden.items],
            "creado_en": orden.creado_en.isoformat() if orden.creado_en else None,
            "actualizado_en": orden.actualizado_en.isoformat()
            if orden.actualizado_en
            else None,
        }

    def _validate_fk(model, id_value, field_name: str):
        if id_value is None:
            raise ValueError(f"El campo {field_name} es requerido")
        obj = model.query.get(id_value)
        if not obj:
            raise LookupError(f"{field_name} no encontrado")
        return obj

    def _parse_items(items_payload):
        if items_payload is None:
            return []
        if not isinstance(items_payload, list) or not items_payload:
            raise ValueError("items debe ser una lista no vacía")
        parsed_items = []
        for item in items_payload:
            if not isinstance(item, dict):
                raise ValueError("Cada item debe ser un objeto")
            producto_id = item.get("producto_id")
            cantidad = item.get("cantidad", 1)
            precio = item.get("precio")
            producto = Producto.query.get(producto_id)
            if not producto:
                raise LookupError("producto_id no encontrado")
            if not producto.es_producto_final:
                raise ValueError("producto_id no es producto final")
            try:
                cantidad_int = int(cantidad)
            except (TypeError, ValueError):
                raise ValueError("cantidad debe ser entero")
            if cantidad_int <= 0:
                raise ValueError("cantidad debe ser mayor que cero")
            try:
                precio_val = _parse_precio(precio, "precio")
            except ValueError as exc:
                raise ValueError(str(exc))
            if precio_val is None:
                raise ValueError("precio es requerido")
            parsed_items.append(
                {
                    "producto_id": producto_id,
                    "cantidad": cantidad_int,
                    "precio": precio_val,
                }
            )
        return parsed_items

    def _generar_codigo_orden(cliente_codigo: str) -> str:
        ts = int(datetime.utcnow().timestamp())
        codigo = f"{cliente_codigo}-{ts}"
        while Orden.query.filter_by(codigo_orden=codigo).first():
            ts += 1
            codigo = f"{cliente_codigo}-{ts}"
        return codigo

    @app.route("/ordenes", methods=["GET"])
    def listar_ordenes():
        ordenes = Orden.query.order_by(Orden.id).all()
        return jsonify([orden_to_dict(o) for o in ordenes])

    @app.route("/ordenes/<int:orden_id>", methods=["GET"])
    def obtener_orden(orden_id: int):
        orden = Orden.query.get_or_404(orden_id)
        return jsonify(orden_to_dict(orden))

    @app.route("/ordenes", methods=["POST"])
    def crear_orden():
        data = request.get_json(silent=True) or {}
        try:
            fecha = _parse_fecha(data.get("fecha"))
            fecha_envio = _parse_fecha(data.get("fecha_envio"))
            fecha_pago = _parse_fecha(data.get("fecha_pago"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        tipo_pago_id = data.get("tipo_pago_id")
        estado_id = data.get("estado_id")
        cliente_id = data.get("cliente_id")
        usuario_id = data.get("usuario_id")
        saldo_val = data.get("saldo")

        try:
            if usuario_id is not None:
                _validate_fk(Usuario, usuario_id, "usuario_id")
            _validate_fk(TipoPago, tipo_pago_id, "tipo_pago_id")
            _validate_fk(EstadoOrden, estado_id, "estado_id")
            cliente = _validate_fk(Cliente, cliente_id, "cliente_id")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

        try:
            items = _parse_items(data.get("items"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

        total = sum(item["precio"] * item["cantidad"] for item in items)
        try:
            saldo = _parse_precio(saldo_val, "saldo") if "saldo" in data else None
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if saldo is None:
            saldo = total

        orden = Orden(
            codigo_orden=_generar_codigo_orden(cliente.codigo.strip()),
            fecha=fecha,
            fecha_envio=fecha_envio,
            fecha_pago=fecha_pago,
            usuario_id=usuario_id,
            tipo_pago_id=tipo_pago_id,
            estado_id=estado_id,
            cliente_id=cliente_id,
            total=total,
            saldo=saldo,
        )
        db.session.add(orden)
        db.session.flush()

        for item in items:
            orden_item = OrdenItem(
                orden_id=orden.id,
                producto_id=item["producto_id"],
                precio=item["precio"],
                cantidad=item["cantidad"],
            )
            db.session.add(orden_item)

        db.session.commit()
        return jsonify(orden_to_dict(orden)), 201

    @app.route("/ordenes/<int:orden_id>", methods=["PUT", "PATCH"])
    def actualizar_orden(orden_id: int):
        orden = Orden.query.get_or_404(orden_id)
        data = request.get_json(silent=True) or {}
        estado_anterior_id = orden.estado_id

        if "fecha" in data:
            try:
                orden.fecha = _parse_fecha(data.get("fecha"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        if "fecha_envio" in data:
            try:
                orden.fecha_envio = _parse_fecha(data.get("fecha_envio"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        if "fecha_pago" in data:
            try:
                orden.fecha_pago = _parse_fecha(data.get("fecha_pago"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        if "tipo_pago_id" in data:
            try:
                _validate_fk(TipoPago, data.get("tipo_pago_id"), "tipo_pago_id")
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404
            orden.tipo_pago_id = data.get("tipo_pago_id")

        if "usuario_id" in data:
            usuario_id = data.get("usuario_id")
            try:
                _validate_fk(Usuario, usuario_id, "usuario_id")
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404
            orden.usuario_id = usuario_id

        if "estado_id" in data:
            try:
                _validate_fk(EstadoOrden, data.get("estado_id"), "estado_id")
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404
            orden.estado_id = data.get("estado_id")

        if "codigo_orden" in data:
            codigo_orden = (data.get("codigo_orden") or "").strip()
            if not codigo_orden:
                return jsonify({"error": "El codigo_orden es requerido"}), 400
            conflicto = (
                Orden.query.filter_by(codigo_orden=codigo_orden)
                .filter(Orden.id != orden.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe una orden con ese codigo_orden"}), 409
            orden.codigo_orden = codigo_orden

        if "cliente_id" in data:
            try:
                _validate_fk(Cliente, data.get("cliente_id"), "cliente_id")
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404
            orden.cliente_id = data.get("cliente_id")

        if "items" in data:
            try:
                nuevos_items = _parse_items(data.get("items"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404

            OrdenItem.query.filter_by(orden_id=orden.id).delete()
            for item in nuevos_items:
                db.session.add(
                    OrdenItem(
                        orden_id=orden.id,
                        producto_id=item["producto_id"],
                        precio=item["precio"],
                        cantidad=item["cantidad"],
                    )
                )
            orden.total = sum(
                item["precio"] * item["cantidad"] for item in nuevos_items
            )

        if "saldo" in data:
            try:
                orden.saldo = _parse_precio(data.get("saldo"), "saldo") or 0
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        if "estado_id" in data and data.get("estado_id") == 3:
            cliente = Cliente.query.get(orden.cliente_id)
            if cliente:
                cliente.saldo = (cliente.saldo or 0) + Decimal(orden.saldo)
            orden.fecha_envio = date.today()            

        db.session.commit()
        return jsonify(orden_to_dict(orden))

    @app.route("/ordenes/<int:orden_id>", methods=["DELETE"])
    def eliminar_orden(orden_id: int):
        orden = Orden.query.get_or_404(orden_id)
        total = Decimal(orden.total)
        saldo = Decimal(orden.saldo)
        if total != saldo:
            return (
                jsonify(
                    {
                        "error": "No se puede eliminar la orden porque tiene pagos aplicados"
                    }
                ),
                400,
            )
        if orden.estado_id == 3 and orden.cliente_id:
            cliente = Cliente.query.get(orden.cliente_id)
            if cliente:
                cliente.saldo = (cliente.saldo or 0) - Decimal(orden.saldo)
        OrdenItem.query.filter_by(orden_id=orden.id).delete()
        db.session.delete(orden)
        db.session.commit()
        return jsonify({"message": "Orden eliminada"})

    # ---------- PRODUCCION ----------

    def materia_prima_to_dict(materia_prima: MateriaPrima) -> dict:
        return {
            "id": materia_prima.id,
            "nombre": materia_prima.nombre,
            "codigo": materia_prima.codigo,
            "unidad": materia_prima.unidad,
            "costo_unitario": float(materia_prima.costo_unitario or 0),
            "stock_actual": float(materia_prima.stock_actual or 0),
            "stock_reservado": float(materia_prima.stock_reservado or 0),
            "stock_minimo": float(materia_prima.stock_minimo or 0),
            "activo": materia_prima.activo,
            "creado_en": materia_prima.creado_en.isoformat()
            if materia_prima.creado_en
            else None,
            "actualizado_en": materia_prima.actualizado_en.isoformat()
            if materia_prima.actualizado_en
            else None,
        }

    def producto_materia_prima_to_dict(item: ProductoMateriaPrima) -> dict:
        return {
            "id": item.id,
            "producto_id": item.producto_id,
            "materia_prima_id": item.materia_prima_id,
            "proceso_id": item.proceso_id,
            "cantidad_necesaria": float(item.cantidad_necesaria or 0),
            "merma_estandar": float(item.merma_estandar or 0),
            "notas": item.notas,
            "creado_en": item.creado_en.isoformat() if item.creado_en else None,
            "actualizado_en": item.actualizado_en.isoformat()
            if item.actualizado_en
            else None,
        }

    def producto_componente_to_dict(item: ProductoComponente) -> dict:
        return {
            "id": item.id,
            "producto_id": item.producto_id,
            "componente_id": item.componente_id,
            "proceso_id": item.proceso_id,
            "cantidad_necesaria": float(item.cantidad_necesaria or 0),
            "merma_estandar": float(item.merma_estandar or 0),
            "notas": item.notas,
            "creado_en": item.creado_en.isoformat() if item.creado_en else None,
            "actualizado_en": item.actualizado_en.isoformat()
            if item.actualizado_en
            else None,
        }

    def proceso_to_dict(proceso: Proceso) -> dict:
        return {
            "id": proceso.id,
            "nombre": proceso.nombre,
            "descripcion": proceso.descripcion,
            "activo": proceso.activo,
            "creado_en": proceso.creado_en.isoformat() if proceso.creado_en else None,
            "actualizado_en": proceso.actualizado_en.isoformat()
            if proceso.actualizado_en
            else None,
        }

    def producto_proceso_to_dict(item: ProductoProceso) -> dict:
        return {
            "id": item.id,
            "producto_id": item.producto_id,
            "proceso_id": item.proceso_id,
            "orden": item.orden,
            "tiempo_objetivo_min": item.tiempo_objetivo_min,
            "activo": item.activo,
            "creado_en": item.creado_en.isoformat() if item.creado_en else None,
            "actualizado_en": item.actualizado_en.isoformat()
            if item.actualizado_en
            else None,
        }

    def proceso_orden_to_dict(item: ProcesoOrden) -> dict:
        return {
            "id": item.id,
            "orden_produccion_id": item.orden_produccion_id,
            "proceso_id": item.proceso_id,
            "orden": item.orden,
            "estado": item.estado,
            "inicio": item.inicio.isoformat() if item.inicio else None,
            "fin": item.fin.isoformat() if item.fin else None,
            "cantidad_entrada": float(item.cantidad_entrada or 0)
            if item.cantidad_entrada is not None
            else None,
            "cantidad_salida": float(item.cantidad_salida or 0)
            if item.cantidad_salida is not None
            else None,
            "cantidad_perdida": float(item.cantidad_perdida or 0)
            if item.cantidad_perdida is not None
            else None,
            "motivo_perdida": item.motivo_perdida,
            "observaciones": item.observaciones,
            "creado_en": item.creado_en.isoformat() if item.creado_en else None,
            "actualizado_en": item.actualizado_en.isoformat()
            if item.actualizado_en
            else None,
        }

    def consumo_materia_prima_to_dict(item: ConsumoMateriaPrima) -> dict:
        return {
            "id": item.id,
            "orden_produccion_id": item.orden_produccion_id,
            "proceso_orden_id": item.proceso_orden_id,
            "materia_prima_id": item.materia_prima_id,
            "cantidad_teorica": float(item.cantidad_teorica or 0),
            "cantidad_real": float(item.cantidad_real or 0)
            if item.cantidad_real is not None
            else None,
            "desperdicio": float(item.desperdicio or 0)
            if item.desperdicio is not None
            else None,
            "observaciones": item.observaciones,
            "creado_en": item.creado_en.isoformat() if item.creado_en else None,
            "actualizado_en": item.actualizado_en.isoformat()
            if item.actualizado_en
            else None,
        }

    def consumo_componente_to_dict(item: ConsumoProductoComponente) -> dict:
        return {
            "id": item.id,
            "orden_produccion_id": item.orden_produccion_id,
            "proceso_orden_id": item.proceso_orden_id,
            "componente_id": item.componente_id,
            "cantidad_teorica": float(item.cantidad_teorica or 0),
            "cantidad_real": float(item.cantidad_real or 0)
            if item.cantidad_real is not None
            else None,
            "desperdicio": float(item.desperdicio or 0)
            if item.desperdicio is not None
            else None,
            "observaciones": item.observaciones,
            "creado_en": item.creado_en.isoformat() if item.creado_en else None,
            "actualizado_en": item.actualizado_en.isoformat()
            if item.actualizado_en
            else None,
        }

    def orden_produccion_to_dict(orden: OrdenProduccion, include_detalle=False) -> dict:
        data = {
            "id": orden.id,
            "codigo": orden.codigo,
            "producto_id": orden.producto_id,
            "cantidad_planeada": float(orden.cantidad_planeada or 0),
            "cantidad_final_buena": float(orden.cantidad_final_buena or 0)
            if orden.cantidad_final_buena is not None
            else None,
            "estado": orden.estado,
            "fecha_inicio": orden.fecha_inicio.isoformat()
            if orden.fecha_inicio
            else None,
            "fecha_fin": orden.fecha_fin.isoformat() if orden.fecha_fin else None,
            "prioridad": orden.prioridad,
            "notas": orden.notas,
            "creado_en": orden.creado_en.isoformat() if orden.creado_en else None,
            "actualizado_en": orden.actualizado_en.isoformat()
            if orden.actualizado_en
            else None,
        }
        if include_detalle:
            procesos = (
                orden.procesos.order_by(ProcesoOrden.orden).all()
                if hasattr(orden.procesos, "order_by")
                else orden.procesos
            )
            consumos = (
                orden.consumos.order_by(ConsumoMateriaPrima.id).all()
                if hasattr(orden.consumos, "order_by")
                else orden.consumos
            )
            consumos_componentes = (
                orden.consumos_componentes.order_by(ConsumoProductoComponente.id).all()
                if hasattr(orden.consumos_componentes, "order_by")
                else orden.consumos_componentes
            )
            data["procesos"] = [proceso_orden_to_dict(p) for p in procesos]
            data["consumos"] = [consumo_materia_prima_to_dict(c) for c in consumos]
            data["consumos_componentes"] = [
                consumo_componente_to_dict(c) for c in consumos_componentes
            ]
        return data

    def ajuste_mp_to_dict(ajuste: MateriaPrimaAjuste) -> dict:
        return {
            "id": ajuste.id,
            "materia_prima_id": ajuste.materia_prima_id,
            "tipo": ajuste.tipo,
            "cantidad": float(ajuste.cantidad or 0),
            "motivo": ajuste.motivo,
            "observaciones": ajuste.observaciones,
            "creado_en": ajuste.creado_en.isoformat() if ajuste.creado_en else None,
            "actualizado_en": ajuste.actualizado_en.isoformat()
            if ajuste.actualizado_en
            else None,
        }

    def _calcular_teorico(bom_item: ProductoMateriaPrima, cantidad_planeada: Decimal):
        cantidad_base = Decimal(str(bom_item.cantidad_necesaria or 0))
        merma = Decimal(str(bom_item.merma_estandar or 0))
        return (cantidad_base + merma) * cantidad_planeada

    def _reservado_restante(orden_id: int, materia_prima_id: int):
        consumos = ConsumoMateriaPrima.query.filter_by(
            orden_produccion_id=orden_id, materia_prima_id=materia_prima_id
        ).all()
        total_teorico = sum(
            Decimal(str(c.cantidad_teorica or 0)) for c in consumos
        )
        total_real = sum(Decimal(str(c.cantidad_real or 0)) for c in consumos)
        restante = total_teorico - total_real
        return restante if restante > 0 else Decimal("0")

    def _reservado_restante_componente(orden_id: int, componente_id: int):
        consumos = ConsumoProductoComponente.query.filter_by(
            orden_produccion_id=orden_id, componente_id=componente_id
        ).all()
        total_teorico = sum(
            Decimal(str(c.cantidad_teorica or 0)) for c in consumos
        )
        total_real = sum(Decimal(str(c.cantidad_real or 0)) for c in consumos)
        restante = total_teorico - total_real
        return restante if restante > 0 else Decimal("0")

    def _cantidad_base_proceso(proceso_orden: ProcesoOrden, orden: OrdenProduccion):
        if proceso_orden.cantidad_salida is not None:
            return Decimal(str(proceso_orden.cantidad_salida))
        if proceso_orden.cantidad_entrada is not None:
            return Decimal(str(proceso_orden.cantidad_entrada))
        return Decimal(str(orden.cantidad_planeada or 0))

    def _registrar_consumo_mp_auto(
        orden: OrdenProduccion,
        proceso_orden: ProcesoOrden,
        materia_prima_id: int,
        cantidad_teorica: Decimal,
    ):
        existente = ConsumoMateriaPrima.query.filter_by(
            orden_produccion_id=orden.id,
            proceso_orden_id=proceso_orden.id,
            materia_prima_id=materia_prima_id,
        ).first()
        if existente:
            return
        materia = MateriaPrima.query.get(materia_prima_id)
        if not materia:
            return
        cantidad_real = cantidad_teorica
        disponible = Decimal(str(materia.stock_actual or 0))
        if disponible < cantidad_real:
            raise ValueError("Stock insuficiente")
        restante = _reservado_restante(orden.id, materia_prima_id)
        consumo = ConsumoMateriaPrima(
            orden_produccion_id=orden.id,
            proceso_orden_id=proceso_orden.id,
            materia_prima_id=materia_prima_id,
            cantidad_teorica=cantidad_teorica,
            cantidad_real=cantidad_real,
            desperdicio=Decimal("0"),
            observaciones="Auto-consumo por proceso",
        )
        db.session.add(consumo)
        materia.stock_actual = disponible - cantidad_real
        liberar = cantidad_real if cantidad_real <= restante else restante
        materia.stock_reservado = max(
            Decimal(str(materia.stock_reservado or 0)) - liberar, Decimal("0")
        )

    def _registrar_consumo_componente_auto(
        orden: OrdenProduccion,
        proceso_orden: ProcesoOrden,
        componente_id: int,
        cantidad_teorica: Decimal,
    ):
        existente = ConsumoProductoComponente.query.filter_by(
            orden_produccion_id=orden.id,
            proceso_orden_id=proceso_orden.id,
            componente_id=componente_id,
        ).first()
        if existente:
            return
        componente = Producto.query.get(componente_id)
        if not componente:
            return
        cantidad_real = cantidad_teorica
        disponible = Decimal(str(componente.stock_actual or 0))
        if disponible < cantidad_real:
            raise ValueError("Stock insuficiente")
        restante = _reservado_restante_componente(orden.id, componente_id)
        consumo = ConsumoProductoComponente(
            orden_produccion_id=orden.id,
            proceso_orden_id=proceso_orden.id,
            componente_id=componente_id,
            cantidad_teorica=cantidad_teorica,
            cantidad_real=cantidad_real,
            desperdicio=Decimal("0"),
            observaciones="Auto-consumo por proceso",
        )
        db.session.add(consumo)
        componente.stock_actual = disponible - cantidad_real
        liberar = cantidad_real if cantidad_real <= restante else restante
        componente.stock_reservado = max(
            Decimal(str(componente.stock_reservado or 0)) - liberar, Decimal("0")
        )

    @app.route("/materias-primas", methods=["GET"])
    def listar_materias_primas():
        materias = MateriaPrima.query.order_by(MateriaPrima.id).all()
        return jsonify([materia_prima_to_dict(m) for m in materias])

    @app.route("/materias-primas/<int:materia_prima_id>", methods=["GET"])
    def obtener_materia_prima(materia_prima_id: int):
        materia = MateriaPrima.query.get_or_404(materia_prima_id)
        return jsonify(materia_prima_to_dict(materia))

    @app.route("/materias-primas", methods=["POST"])
    def crear_materia_prima():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        codigo = (data.get("codigo") or "").strip()
        activo = _parse_bool(data.get("activo"), default=True)

        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400
        if not codigo:
            return jsonify({"error": "El código es requerido"}), 400
        if MateriaPrima.query.filter_by(codigo=codigo).first():
            return jsonify({"error": "Ya existe una materia prima con ese código"}), 409

        try:
            costo_unitario = _parse_decimal(
                data.get("costo_unitario", 0), "costo_unitario", default=Decimal("0")
            )
            stock_actual = _parse_decimal(
                data.get("stock_actual", 0), "stock_actual", default=Decimal("0")
            )
            stock_reservado = _parse_decimal(
                data.get("stock_reservado", 0),
                "stock_reservado",
                default=Decimal("0"),
            )
            stock_minimo = _parse_decimal(
                data.get("stock_minimo", 0), "stock_minimo", default=Decimal("0")
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        materia = MateriaPrima(
            nombre=nombre,
            codigo=codigo,
            costo_unitario=costo_unitario or 0,
            stock_actual=stock_actual or 0,
            stock_reservado=stock_reservado or 0,
            stock_minimo=stock_minimo or 0,
            activo=activo,
        )
        db.session.add(materia)
        db.session.commit()
        return jsonify(materia_prima_to_dict(materia)), 201

    @app.route("/materias-primas/<int:materia_prima_id>", methods=["PUT", "PATCH"])
    def actualizar_materia_prima(materia_prima_id: int):
        materia = MateriaPrima.query.get_or_404(materia_prima_id)
        data = request.get_json(silent=True) or {}

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            materia.nombre = nombre
        if "codigo" in data:
            codigo = (data.get("codigo") or "").strip()
            if not codigo:
                return jsonify({"error": "El código es requerido"}), 400
            conflicto = (
                MateriaPrima.query.filter_by(codigo=codigo)
                .filter(MateriaPrima.id != materia.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe una materia prima con ese código"}), 409
            materia.codigo = codigo
        if "unidad" in data:
            unidad = (data.get("unidad") or "").strip()
            if not unidad:
                return jsonify({"error": "La unidad es requerida"}), 400
            materia.unidad = unidad
        if "activo" in data:
            materia.activo = _parse_bool(data.get("activo"), default=materia.activo)

        try:
            if "costo_unitario" in data:
                materia.costo_unitario = _parse_decimal(
                    data.get("costo_unitario"), "costo_unitario"
                )
            if "stock_actual" in data:
                materia.stock_actual = _parse_decimal(
                    data.get("stock_actual"), "stock_actual"
                )
            if "stock_reservado" in data:
                materia.stock_reservado = _parse_decimal(
                    data.get("stock_reservado"), "stock_reservado"
                )
            if "stock_minimo" in data:
                materia.stock_minimo = _parse_decimal(
                    data.get("stock_minimo"), "stock_minimo"
                )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        db.session.commit()
        return jsonify(materia_prima_to_dict(materia))

    @app.route("/materias-primas/<int:materia_prima_id>", methods=["DELETE"])
    def eliminar_materia_prima(materia_prima_id: int):
        materia = MateriaPrima.query.get_or_404(materia_prima_id)
        db.session.delete(materia)
        db.session.commit()
        return jsonify({"message": "Materia prima eliminada"})

    @app.route("/materias-primas/<int:materia_prima_id>/ajustes-stock", methods=["POST"])
    def ajustar_stock_materia_prima(materia_prima_id: int):
        materia = MateriaPrima.query.get_or_404(materia_prima_id)
        data = request.get_json(silent=True) or {}
        tipo = (data.get("tipo") or "").strip().upper()
        motivo = (data.get("motivo") or "").strip() or None
        observaciones = (data.get("observaciones") or "").strip() or None

        if tipo not in {"ENTRADA", "SALIDA", "AJUSTE"}:
            return jsonify({"error": "tipo debe ser ENTRADA, SALIDA o AJUSTE"}), 400

        try:
            cantidad = _parse_decimal(data.get("cantidad"), "cantidad")
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if cantidad is None:
            return jsonify({"error": "cantidad es requerida"}), 400

        delta = cantidad if tipo in {"ENTRADA", "AJUSTE"} else -cantidad
        nuevo_stock = Decimal(str(materia.stock_actual or 0)) + Decimal(str(delta))
        if nuevo_stock < 0:
            return jsonify({"error": "Stock insuficiente para el ajuste"}), 400

        materia.stock_actual = nuevo_stock
        ajuste = MateriaPrimaAjuste(
            materia_prima_id=materia.id,
            tipo=tipo,
            cantidad=cantidad,
            motivo=motivo,
            observaciones=observaciones,
        )
        db.session.add(ajuste)
        db.session.commit()
        return jsonify({"materia_prima": materia_prima_to_dict(materia), "ajuste": ajuste_mp_to_dict(ajuste)})

    @app.route("/productos/<int:producto_id>/bom", methods=["GET"])
    def listar_bom_producto(producto_id: int):
        Producto.query.get_or_404(producto_id)
        items = ProductoMateriaPrima.query.filter_by(producto_id=producto_id).all()
        return jsonify([producto_materia_prima_to_dict(i) for i in items])

    @app.route("/productos/<int:producto_id>/bom", methods=["POST"])
    def crear_bom_producto(producto_id: int):
        Producto.query.get_or_404(producto_id)
        data = request.get_json(silent=True) or {}
        materia_prima_id = data.get("materia_prima_id")
        if materia_prima_id is None:
            return jsonify({"error": "materia_prima_id es requerido"}), 400
        MateriaPrima.query.get_or_404(materia_prima_id)
        proceso_id = data.get("proceso_id")
        if proceso_id is not None:
            Proceso.query.get_or_404(proceso_id)
            en_ruta = ProductoProceso.query.filter_by(
                producto_id=producto_id, proceso_id=proceso_id, activo=True
            ).first()
            if not en_ruta:
                return jsonify({"error": "proceso_id no pertenece a la ruta del producto"}), 400

        existente = ProductoMateriaPrima.query.filter_by(
            producto_id=producto_id, materia_prima_id=materia_prima_id
        ).first()
        if existente:
            return jsonify({"error": "Ya existe esa materia prima en el BOM"}), 409

        try:
            cantidad_necesaria = _parse_decimal(
                data.get("cantidad_necesaria"), "cantidad_necesaria"
            )
            merma_estandar = _parse_decimal(
                data.get("merma_estandar", 0), "merma_estandar", default=Decimal("0")
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if cantidad_necesaria is None:
            return jsonify({"error": "cantidad_necesaria es requerida"}), 400

        item = ProductoMateriaPrima(
            producto_id=producto_id,
            materia_prima_id=materia_prima_id,
            proceso_id=proceso_id,
            cantidad_necesaria=cantidad_necesaria,
            merma_estandar=merma_estandar or 0,
            notas=(data.get("notas") or "").strip() or None,
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(producto_materia_prima_to_dict(item)), 201

    @app.route("/productos/<int:producto_id>/bom/<int:item_id>", methods=["PUT", "PATCH"])
    def actualizar_bom_producto(producto_id: int, item_id: int):
        item = ProductoMateriaPrima.query.filter_by(
            id=item_id, producto_id=producto_id
        ).first_or_404()
        data = request.get_json(silent=True) or {}

        if "materia_prima_id" in data:
            materia_prima_id = data.get("materia_prima_id")
            MateriaPrima.query.get_or_404(materia_prima_id)
            existente = (
                ProductoMateriaPrima.query.filter_by(
                    producto_id=producto_id, materia_prima_id=materia_prima_id
                )
                .filter(ProductoMateriaPrima.id != item.id)
                .first()
            )
            if existente:
                return jsonify({"error": "Ya existe esa materia prima en el BOM"}), 409
            item.materia_prima_id = materia_prima_id

        try:
            if "cantidad_necesaria" in data:
                item.cantidad_necesaria = _parse_decimal(
                    data.get("cantidad_necesaria"), "cantidad_necesaria"
                )
            if "merma_estandar" in data:
                item.merma_estandar = _parse_decimal(
                    data.get("merma_estandar"), "merma_estandar"
                )
            if "proceso_id" in data:
                proceso_id = data.get("proceso_id")
                if proceso_id is None:
                    item.proceso_id = None
                else:
                    Proceso.query.get_or_404(proceso_id)
                    en_ruta = ProductoProceso.query.filter_by(
                        producto_id=producto_id, proceso_id=proceso_id, activo=True
                    ).first()
                    if not en_ruta:
                        return jsonify(
                            {"error": "proceso_id no pertenece a la ruta del producto"}
                        ), 400
                    item.proceso_id = proceso_id
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if "notas" in data:
            item.notas = (data.get("notas") or "").strip() or None

        db.session.commit()
        return jsonify(producto_materia_prima_to_dict(item))

    @app.route("/productos/<int:producto_id>/bom/<int:item_id>", methods=["DELETE"])
    def eliminar_bom_producto(producto_id: int, item_id: int):
        item = ProductoMateriaPrima.query.filter_by(
            id=item_id, producto_id=producto_id
        ).first_or_404()
        db.session.delete(item)
        db.session.commit()
        return jsonify({"message": "BOM eliminado"})

    @app.route("/productos/<int:producto_id>/componentes", methods=["GET"])
    def listar_componentes_producto(producto_id: int):
        Producto.query.get_or_404(producto_id)
        items = ProductoComponente.query.filter_by(producto_id=producto_id).all()
        return jsonify([producto_componente_to_dict(i) for i in items])

    @app.route("/productos/<int:producto_id>/componentes", methods=["POST"])
    def crear_componente_producto(producto_id: int):
        Producto.query.get_or_404(producto_id)
        data = request.get_json(silent=True) or {}
        componente_id = data.get("componente_id")
        if componente_id is None:
            return jsonify({"error": "componente_id es requerido"}), 400
        if componente_id == producto_id:
            return jsonify({"error": "El componente no puede ser el mismo producto"}), 400
        Producto.query.get_or_404(componente_id)
        proceso_id = data.get("proceso_id")
        if proceso_id is not None:
            Proceso.query.get_or_404(proceso_id)
            en_ruta = ProductoProceso.query.filter_by(
                producto_id=producto_id, proceso_id=proceso_id, activo=True
            ).first()
            if not en_ruta:
                return jsonify({"error": "proceso_id no pertenece a la ruta del producto"}), 400

        existente = ProductoComponente.query.filter_by(
            producto_id=producto_id, componente_id=componente_id
        ).first()
        if existente:
            return jsonify({"error": "Ya existe ese componente en el producto"}), 409

        try:
            cantidad_necesaria = _parse_decimal(
                data.get("cantidad_necesaria"), "cantidad_necesaria"
            )
            merma_estandar = _parse_decimal(
                data.get("merma_estandar", 0), "merma_estandar", default=Decimal("0")
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if cantidad_necesaria is None:
            return jsonify({"error": "cantidad_necesaria es requerida"}), 400

        item = ProductoComponente(
            producto_id=producto_id,
            componente_id=componente_id,
            proceso_id=proceso_id,
            cantidad_necesaria=cantidad_necesaria,
            merma_estandar=merma_estandar or 0,
            notas=(data.get("notas") or "").strip() or None,
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(producto_componente_to_dict(item)), 201

    @app.route(
        "/productos/<int:producto_id>/componentes/<int:item_id>",
        methods=["PUT", "PATCH"],
    )
    def actualizar_componente_producto(producto_id: int, item_id: int):
        item = ProductoComponente.query.filter_by(
            id=item_id, producto_id=producto_id
        ).first_or_404()
        data = request.get_json(silent=True) or {}

        if "componente_id" in data:
            componente_id = data.get("componente_id")
            if componente_id == producto_id:
                return (
                    jsonify({"error": "El componente no puede ser el mismo producto"}),
                    400,
                )
            Producto.query.get_or_404(componente_id)
            existente = (
                ProductoComponente.query.filter_by(
                    producto_id=producto_id, componente_id=componente_id
                )
                .filter(ProductoComponente.id != item.id)
                .first()
            )
            if existente:
                return jsonify({"error": "Ya existe ese componente en el producto"}), 409
            item.componente_id = componente_id

        try:
            if "cantidad_necesaria" in data:
                item.cantidad_necesaria = _parse_decimal(
                    data.get("cantidad_necesaria"), "cantidad_necesaria"
                )
            if "merma_estandar" in data:
                item.merma_estandar = _parse_decimal(
                    data.get("merma_estandar"), "merma_estandar"
                )
            if "proceso_id" in data:
                proceso_id = data.get("proceso_id")
                if proceso_id is None:
                    item.proceso_id = None
                else:
                    Proceso.query.get_or_404(proceso_id)
                    en_ruta = ProductoProceso.query.filter_by(
                        producto_id=producto_id, proceso_id=proceso_id, activo=True
                    ).first()
                    if not en_ruta:
                        return jsonify(
                            {"error": "proceso_id no pertenece a la ruta del producto"}
                        ), 400
                    item.proceso_id = proceso_id
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if "notas" in data:
            item.notas = (data.get("notas") or "").strip() or None

        db.session.commit()
        return jsonify(producto_componente_to_dict(item))

    @app.route(
        "/productos/<int:producto_id>/componentes/<int:item_id>",
        methods=["DELETE"],
    )
    def eliminar_componente_producto(producto_id: int, item_id: int):
        item = ProductoComponente.query.filter_by(
            id=item_id, producto_id=producto_id
        ).first_or_404()
        db.session.delete(item)
        db.session.commit()
        return jsonify({"message": "Componente eliminado"})

    @app.route("/procesos", methods=["GET"])
    def listar_procesos():
        procesos = Proceso.query.order_by(Proceso.id).all()
        return jsonify([proceso_to_dict(p) for p in procesos])

    @app.route("/procesos/<int:proceso_id>", methods=["GET"])
    def obtener_proceso(proceso_id: int):
        proceso = Proceso.query.get_or_404(proceso_id)
        return jsonify(proceso_to_dict(proceso))

    @app.route("/procesos", methods=["POST"])
    def crear_proceso():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        descripcion = (data.get("descripcion") or "").strip() or None
        activo = _parse_bool(data.get("activo"), default=True)

        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400
        if Proceso.query.filter_by(nombre=nombre).first():
            return jsonify({"error": "Ya existe un proceso con ese nombre"}), 409

        proceso = Proceso(nombre=nombre, descripcion=descripcion, activo=activo)
        db.session.add(proceso)
        db.session.commit()
        return jsonify(proceso_to_dict(proceso)), 201

    @app.route("/procesos/<int:proceso_id>", methods=["PUT", "PATCH"])
    def actualizar_proceso(proceso_id: int):
        proceso = Proceso.query.get_or_404(proceso_id)
        data = request.get_json(silent=True) or {}

        if "nombre" in data:
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return jsonify({"error": "El nombre es requerido"}), 400
            conflicto = (
                Proceso.query.filter_by(nombre=nombre)
                .filter(Proceso.id != proceso.id)
                .first()
            )
            if conflicto:
                return jsonify({"error": "Ya existe un proceso con ese nombre"}), 409
            proceso.nombre = nombre

        if "descripcion" in data:
            proceso.descripcion = (data.get("descripcion") or "").strip() or None

        if "activo" in data:
            proceso.activo = _parse_bool(data.get("activo"), default=proceso.activo)

        db.session.commit()
        return jsonify(proceso_to_dict(proceso))

    @app.route("/procesos/<int:proceso_id>", methods=["DELETE"])
    def eliminar_proceso(proceso_id: int):
        proceso = Proceso.query.get_or_404(proceso_id)
        db.session.delete(proceso)
        db.session.commit()
        return jsonify({"message": "Proceso eliminado"})

    @app.route("/productos/<int:producto_id>/ruta-procesos", methods=["GET"])
    def listar_ruta_procesos(producto_id: int):
        Producto.query.get_or_404(producto_id)
        items = (
            ProductoProceso.query.filter_by(producto_id=producto_id)
            .order_by(ProductoProceso.orden)
            .all()
        )
        return jsonify([producto_proceso_to_dict(i) for i in items])

    @app.route("/productos/<int:producto_id>/ruta-procesos", methods=["POST"])
    def crear_ruta_proceso(producto_id: int):
        Producto.query.get_or_404(producto_id)
        data = request.get_json(silent=True) or {}
        proceso_id = data.get("proceso_id")
        orden = data.get("orden")
        if proceso_id is None:
            return jsonify({"error": "proceso_id es requerido"}), 400
        if orden is None:
            return jsonify({"error": "orden es requerido"}), 400
        Proceso.query.get_or_404(proceso_id)

        existe_orden = ProductoProceso.query.filter_by(
            producto_id=producto_id, orden=orden
        ).first()
        if existe_orden:
            return jsonify({"error": "Ya existe un proceso con ese orden"}), 409

        existe_proc = ProductoProceso.query.filter_by(
            producto_id=producto_id, proceso_id=proceso_id
        ).first()
        if existe_proc:
            return jsonify({"error": "El proceso ya está asignado al producto"}), 409

        item = ProductoProceso(
            producto_id=producto_id,
            proceso_id=proceso_id,
            orden=orden,
            tiempo_objetivo_min=data.get("tiempo_objetivo_min"),
            activo=_parse_bool(data.get("activo"), default=True),
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(producto_proceso_to_dict(item)), 201

    @app.route(
        "/productos/<int:producto_id>/ruta-procesos/<int:item_id>",
        methods=["PUT", "PATCH"],
    )
    def actualizar_ruta_proceso(producto_id: int, item_id: int):
        item = ProductoProceso.query.filter_by(
            id=item_id, producto_id=producto_id
        ).first_or_404()
        data = request.get_json(silent=True) or {}

        if "proceso_id" in data:
            proceso_id = data.get("proceso_id")
            Proceso.query.get_or_404(proceso_id)
            existe = (
                ProductoProceso.query.filter_by(
                    producto_id=producto_id, proceso_id=proceso_id
                )
                .filter(ProductoProceso.id != item.id)
                .first()
            )
            if existe:
                return jsonify({"error": "El proceso ya está asignado al producto"}), 409
            item.proceso_id = proceso_id

        if "orden" in data:
            orden = data.get("orden")
            existe = (
                ProductoProceso.query.filter_by(producto_id=producto_id, orden=orden)
                .filter(ProductoProceso.id != item.id)
                .first()
            )
            if existe:
                return jsonify({"error": "Ya existe un proceso con ese orden"}), 409
            item.orden = orden

        if "tiempo_objetivo_min" in data:
            item.tiempo_objetivo_min = data.get("tiempo_objetivo_min")

        if "activo" in data:
            item.activo = _parse_bool(data.get("activo"), default=item.activo)

        db.session.commit()
        return jsonify(producto_proceso_to_dict(item))

    @app.route(
        "/productos/<int:producto_id>/ruta-procesos/<int:item_id>",
        methods=["DELETE"],
    )
    def eliminar_ruta_proceso(producto_id: int, item_id: int):
        item = ProductoProceso.query.filter_by(
            id=item_id, producto_id=producto_id
        ).first_or_404()
        db.session.delete(item)
        db.session.commit()
        return jsonify({"message": "Ruta de proceso eliminada"})

    @app.route("/ordenes-produccion", methods=["GET"])
    def listar_ordenes_produccion():
        ordenes = OrdenProduccion.query.order_by(OrdenProduccion.id).all()
        return jsonify([orden_produccion_to_dict(o) for o in ordenes])

    @app.route("/ordenes-produccion/<int:orden_id>", methods=["GET"])
    def obtener_orden_produccion(orden_id: int):
        orden = OrdenProduccion.query.get_or_404(orden_id)
        return jsonify(orden_produccion_to_dict(orden, include_detalle=True))

    @app.route("/ordenes-produccion", methods=["POST"])
    def crear_orden_produccion():
        data = request.get_json(silent=True) or {}
        codigo = (data.get("codigo") or "").strip()
        producto_id = data.get("producto_id")
        prioridad = data.get("prioridad")
        notas = (data.get("notas") or "").strip() or None
        estado = (data.get("estado") or "PLANIFICADA").strip().upper()

        if not codigo:
            return jsonify({"error": "El código es requerido"}), 400
        if OrdenProduccion.query.filter_by(codigo=codigo).first():
            return jsonify({"error": "Ya existe una orden con ese código"}), 409

        try:
            cantidad_planeada = _parse_decimal(
                data.get("cantidad_planeada"), "cantidad_planeada"
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if cantidad_planeada is None or cantidad_planeada <= 0:
            return jsonify({"error": "cantidad_planeada debe ser mayor que cero"}), 400

        producto = Producto.query.get(producto_id)
        if not producto:
            return jsonify({"error": "producto_id no encontrado"}), 404

        bom_items = ProductoMateriaPrima.query.filter_by(producto_id=producto_id).all()
        componentes = ProductoComponente.query.filter_by(producto_id=producto_id).all()
        if not bom_items and not componentes:
            return (
                jsonify(
                    {"error": "El producto no tiene BOM ni componentes configurados"}
                ),
                400,
            )

        ruta = (
            ProductoProceso.query.filter_by(producto_id=producto_id, activo=True)
            .order_by(ProductoProceso.orden)
            .all()
        )
        if not ruta:
            return jsonify({"error": "El producto no tiene ruta de procesos"}), 400

        for item in bom_items:
            materia = MateriaPrima.query.get(item.materia_prima_id)
            if not materia:
                return jsonify({"error": "Materia prima no encontrada en BOM"}), 404
            teorico = _calcular_teorico(item, cantidad_planeada)
            disponible = Decimal(str(materia.stock_actual or 0)) - Decimal(
                str(materia.stock_reservado or 0)
            )
            if disponible < teorico:
                return (
                    jsonify(
                        {
                            "error": f"Stock insuficiente para {materia.codigo}",
                            "disponible": float(disponible),
                            "requerido": float(teorico),
                        }
                    ),
                    400,
                )

        for item in componentes:
            componente = Producto.query.get(item.componente_id)
            if not componente:
                return jsonify({"error": "Componente no encontrado en producto"}), 404
            teorico = _calcular_teorico(item, cantidad_planeada)
            disponible = Decimal(str(componente.stock_actual or 0)) - Decimal(
                str(componente.stock_reservado or 0)
            )
            if disponible < teorico:
                return (
                    jsonify(
                        {
                            "error": f"Stock insuficiente para {componente.codigo}",
                            "disponible": float(disponible),
                            "requerido": float(teorico),
                        }
                    ),
                    400,
                )

        orden = OrdenProduccion(
            codigo=codigo,
            producto_id=producto_id,
            cantidad_planeada=cantidad_planeada,
            estado=estado,
            prioridad=prioridad,
            notas=notas,
        )
        db.session.add(orden)
        db.session.flush()

        for item in bom_items:
            teorico = _calcular_teorico(item, cantidad_planeada)
            consumo = ConsumoMateriaPrima(
                orden_produccion_id=orden.id,
                materia_prima_id=item.materia_prima_id,
                cantidad_teorica=teorico,
            )
            db.session.add(consumo)
            materia = MateriaPrima.query.get(item.materia_prima_id)
            materia.stock_reservado = Decimal(str(materia.stock_reservado or 0)) + teorico

        for item in componentes:
            teorico = _calcular_teorico(item, cantidad_planeada)
            consumo = ConsumoProductoComponente(
                orden_produccion_id=orden.id,
                componente_id=item.componente_id,
                cantidad_teorica=teorico,
            )
            db.session.add(consumo)
            componente = Producto.query.get(item.componente_id)
            componente.stock_reservado = Decimal(
                str(componente.stock_reservado or 0)
            ) + teorico

        for item in ruta:
            proceso_orden = ProcesoOrden(
                orden_produccion_id=orden.id,
                proceso_id=item.proceso_id,
                orden=item.orden,
                estado="PENDIENTE",
            )
            db.session.add(proceso_orden)

        db.session.commit()
        return jsonify(orden_produccion_to_dict(orden, include_detalle=True)), 201

    @app.route("/ordenes-produccion/<int:orden_id>", methods=["PUT", "PATCH"])
    def actualizar_orden_produccion(orden_id: int):
        orden = OrdenProduccion.query.get_or_404(orden_id)
        data = request.get_json(silent=True) or {}

        if "notas" in data:
            orden.notas = (data.get("notas") or "").strip() or None
        if "prioridad" in data:
            orden.prioridad = data.get("prioridad")

        if "cantidad_planeada" in data:
            return jsonify({"error": "No se permite cambiar cantidad_planeada"}), 400

        if "estado" in data:
            estado = (data.get("estado") or "").strip().upper()
            if estado in {"CANCELADA", "COMPLETADA"}:
                return jsonify({"error": "Use los endpoints de acciones"}), 400
            orden.estado = estado

        db.session.commit()
        return jsonify(orden_produccion_to_dict(orden, include_detalle=True))

    @app.route("/ordenes-produccion/<int:orden_id>", methods=["DELETE"])
    def eliminar_orden_produccion(orden_id: int):
        orden = OrdenProduccion.query.get_or_404(orden_id)
        if orden.estado not in {"BORRADOR", "PLANIFICADA", "CANCELADA"}:
            return jsonify({"error": "No se puede eliminar una orden en proceso"}), 400
        for consumo in orden.consumos.all():
            teorico = Decimal(str(consumo.cantidad_teorica or 0))
            real = Decimal(str(consumo.cantidad_real or 0))
            restante = teorico - real
            if restante > 0:
                materia = MateriaPrima.query.get(consumo.materia_prima_id)
                materia.stock_reservado = max(
                    Decimal(str(materia.stock_reservado or 0)) - restante, Decimal("0")
                )
        for consumo in orden.consumos_componentes.all():
            teorico = Decimal(str(consumo.cantidad_teorica or 0))
            real = Decimal(str(consumo.cantidad_real or 0))
            restante = teorico - real
            if restante > 0:
                componente = Producto.query.get(consumo.componente_id)
                componente.stock_reservado = max(
                    Decimal(str(componente.stock_reservado or 0)) - restante,
                    Decimal("0"),
                )
        ConsumoMateriaPrima.query.filter_by(orden_produccion_id=orden.id).delete()
        ConsumoProductoComponente.query.filter_by(
            orden_produccion_id=orden.id
        ).delete()
        ProcesoOrden.query.filter_by(orden_produccion_id=orden.id).delete()
        db.session.delete(orden)
        db.session.commit()
        return jsonify({"message": "Orden de producción eliminada"})

    @app.route("/ordenes-produccion/<int:orden_id>/iniciar", methods=["POST"])
    def iniciar_orden_produccion(orden_id: int):
        orden = OrdenProduccion.query.get_or_404(orden_id)
        if orden.estado in {"CANCELADA", "COMPLETADA"}:
            return jsonify({"error": "La orden no se puede iniciar"}), 400
        orden.estado = "EN_PROCESO"
        if not orden.fecha_inicio:
            orden.fecha_inicio = datetime.utcnow()
        db.session.commit()
        return jsonify(orden_produccion_to_dict(orden, include_detalle=True))

    @app.route("/ordenes-produccion/<int:orden_id>/pausar", methods=["POST"])
    def pausar_orden_produccion(orden_id: int):
        orden = OrdenProduccion.query.get_or_404(orden_id)
        if orden.estado != "EN_PROCESO":
            return jsonify({"error": "La orden no está en proceso"}), 400
        orden.estado = "PAUSADA"
        db.session.commit()
        return jsonify(orden_produccion_to_dict(orden, include_detalle=True))

    @app.route("/ordenes-produccion/<int:orden_id>/cancelar", methods=["POST"])
    def cancelar_orden_produccion(orden_id: int):
        orden = OrdenProduccion.query.get_or_404(orden_id)
        if orden.estado == "CANCELADA":
            return jsonify({"error": "La orden ya está cancelada"}), 400
        orden.estado = "CANCELADA"
        if not orden.fecha_fin:
            orden.fecha_fin = datetime.utcnow()
        for consumo in orden.consumos.all():
            teorico = Decimal(str(consumo.cantidad_teorica or 0))
            real = Decimal(str(consumo.cantidad_real or 0))
            restante = teorico - real
            if restante > 0:
                materia = MateriaPrima.query.get(consumo.materia_prima_id)
                materia.stock_reservado = max(
                    Decimal(str(materia.stock_reservado or 0)) - restante, Decimal("0")
                )
        for consumo in orden.consumos_componentes.all():
            teorico = Decimal(str(consumo.cantidad_teorica or 0))
            real = Decimal(str(consumo.cantidad_real or 0))
            restante = teorico - real
            if restante > 0:
                componente = Producto.query.get(consumo.componente_id)
                componente.stock_reservado = max(
                    Decimal(str(componente.stock_reservado or 0)) - restante,
                    Decimal("0"),
                )
        db.session.commit()
        return jsonify(orden_produccion_to_dict(orden, include_detalle=True))

    @app.route("/ordenes-produccion/<int:orden_id>/cerrar", methods=["POST"])
    def cerrar_orden_produccion(orden_id: int):
        orden = OrdenProduccion.query.get_or_404(orden_id)
        data = request.get_json(silent=True) or {}
        if orden.estado == "CANCELADA":
            return jsonify({"error": "La orden está cancelada"}), 400
        orden.estado = "COMPLETADA"
        if not orden.fecha_fin:
            orden.fecha_fin = datetime.utcnow()
        if "cantidad_final_buena" in data:
            try:
                orden.cantidad_final_buena = _parse_decimal(
                    data.get("cantidad_final_buena"), "cantidad_final_buena"
                )
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        else:
            ultimo = (
                orden.procesos.order_by(ProcesoOrden.orden.desc()).first()
                if hasattr(orden.procesos, "order_by")
                else None
            )
            if ultimo and ultimo.cantidad_salida is not None:
                orden.cantidad_final_buena = ultimo.cantidad_salida
        db.session.commit()
        return jsonify(orden_produccion_to_dict(orden, include_detalle=True))

    @app.route("/ordenes-produccion/<int:orden_id>/procesos", methods=["GET"])
    def listar_procesos_orden(orden_id: int):
        OrdenProduccion.query.get_or_404(orden_id)
        procesos = (
            ProcesoOrden.query.filter_by(orden_produccion_id=orden_id)
            .order_by(ProcesoOrden.orden)
            .all()
        )
        return jsonify([proceso_orden_to_dict(p) for p in procesos])

    def _validar_proceso_orden(orden_id: int, proceso_orden_id: int):
        proceso_orden = ProcesoOrden.query.get_or_404(proceso_orden_id)
        if proceso_orden.orden_produccion_id != orden_id:
            return None
        return proceso_orden

    @app.route(
        "/ordenes-produccion/<int:orden_id>/procesos/<int:proceso_orden_id>/iniciar",
        methods=["POST"],
    )
    def iniciar_proceso_orden(orden_id: int, proceso_orden_id: int):
        proceso_orden = _validar_proceso_orden(orden_id, proceso_orden_id)
        if not proceso_orden:
            return jsonify({"error": "Proceso no pertenece a la orden"}), 400
        if proceso_orden.estado == "COMPLETADO":
            return jsonify({"error": "El proceso ya fue completado"}), 400

        previo = ProcesoOrden.query.filter_by(
            orden_produccion_id=orden_id, orden=proceso_orden.orden - 1
        ).first()
        if previo and previo.estado != "COMPLETADO":
            salida_prev = Decimal(str(previo.cantidad_salida or 0))
            if salida_prev <= 0:
                return (
                    jsonify(
                        {
                            "error": "Debe registrar salida en el proceso anterior para iniciar este proceso"
                        }
                    ),
                    400,
                )

        proceso_orden.estado = "EN_PROCESO"
        if not proceso_orden.inicio:
            proceso_orden.inicio = datetime.utcnow()

        orden = OrdenProduccion.query.get(orden_id)
        if orden and orden.estado not in {"EN_PROCESO", "COMPLETADA"}:
            orden.estado = "EN_PROCESO"
            if not orden.fecha_inicio:
                orden.fecha_inicio = datetime.utcnow()

        db.session.commit()
        return jsonify(proceso_orden_to_dict(proceso_orden))

    @app.route(
        "/ordenes-produccion/<int:orden_id>/procesos/<int:proceso_orden_id>/pausar",
        methods=["POST"],
    )
    def pausar_proceso_orden(orden_id: int, proceso_orden_id: int):
        proceso_orden = _validar_proceso_orden(orden_id, proceso_orden_id)
        if not proceso_orden:
            return jsonify({"error": "Proceso no pertenece a la orden"}), 400
        if proceso_orden.estado != "EN_PROCESO":
            return jsonify({"error": "El proceso no está en curso"}), 400
        proceso_orden.estado = "PAUSADO"
        db.session.commit()
        return jsonify(proceso_orden_to_dict(proceso_orden))

    @app.route(
        "/ordenes-produccion/<int:orden_id>/procesos/<int:proceso_orden_id>/completar",
        methods=["POST"],
    )
    def completar_proceso_orden(orden_id: int, proceso_orden_id: int):
        proceso_orden = _validar_proceso_orden(orden_id, proceso_orden_id)
        if not proceso_orden:
            return jsonify({"error": "Proceso no pertenece a la orden"}), 400
        if proceso_orden.estado not in {"EN_PROCESO", "PAUSADO"}:
            return jsonify({"error": "El proceso no está activo"}), 400

        data = request.get_json(silent=True) or {}
        parcial = _parse_bool(data.get("parcial"), default=False)
        try:
            if "cantidad_entrada" in data:
                proceso_orden.cantidad_entrada = _parse_decimal(
                    data.get("cantidad_entrada"), "cantidad_entrada"
                )
            if "cantidad_salida" in data:
                proceso_orden.cantidad_salida = _parse_decimal(
                    data.get("cantidad_salida"), "cantidad_salida"
                )
            if "cantidad_perdida" in data:
                proceso_orden.cantidad_perdida = _parse_decimal(
                    data.get("cantidad_perdida"), "cantidad_perdida"
                )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        previo = ProcesoOrden.query.filter_by(
            orden_produccion_id=orden_id, orden=proceso_orden.orden - 1
        ).first()
        if (
            previo
            and proceso_orden.cantidad_entrada is not None
            and previo.cantidad_salida is not None
            and proceso_orden.cantidad_entrada > previo.cantidad_salida
        ):
            return (
                jsonify(
                    {
                        "error": "cantidad_entrada supera la salida del proceso anterior"
                    }
                ),
                400,
            )

        if proceso_orden.cantidad_perdida is None:
            if (
                proceso_orden.cantidad_entrada is not None
                and proceso_orden.cantidad_salida is not None
            ):
                perdida = proceso_orden.cantidad_entrada - proceso_orden.cantidad_salida
                proceso_orden.cantidad_perdida = perdida if perdida > 0 else 0

        if "motivo_perdida" in data:
            proceso_orden.motivo_perdida = (
                (data.get("motivo_perdida") or "").strip() or None
            )
        if "observaciones" in data:
            proceso_orden.observaciones = (
                (data.get("observaciones") or "").strip() or None
            )

        if parcial:
            db.session.commit()
            return jsonify(proceso_orden_to_dict(proceso_orden))

        proceso_orden.estado = "COMPLETADO"
        if not proceso_orden.fin:
            proceso_orden.fin = datetime.utcnow()

        orden = OrdenProduccion.query.get(orden_id)
        if orden:
            cantidad_base = _cantidad_base_proceso(proceso_orden, orden)
            if cantidad_base > 0:
                mp_items = ProductoMateriaPrima.query.filter_by(
                    producto_id=orden.producto_id, proceso_id=proceso_orden.proceso_id
                ).all()
                comp_items = ProductoComponente.query.filter_by(
                    producto_id=orden.producto_id, proceso_id=proceso_orden.proceso_id
                ).all()
                try:
                    for item in mp_items:
                        teorico = _calcular_teorico(item, cantidad_base)
                        _registrar_consumo_mp_auto(
                            orden, proceso_orden, item.materia_prima_id, teorico
                        )
                    for item in comp_items:
                        teorico = _calcular_teorico(item, cantidad_base)
                        _registrar_consumo_componente_auto(
                            orden, proceso_orden, item.componente_id, teorico
                        )
                except ValueError as exc:
                    return jsonify({"error": str(exc)}), 400
        restantes = ProcesoOrden.query.filter_by(
            orden_produccion_id=orden_id
        ).filter(ProcesoOrden.estado != "COMPLETADO")
        if not restantes.first() and orden and orden.estado != "CANCELADA":
            orden.estado = "COMPLETADA"
            if not orden.fecha_fin:
                orden.fecha_fin = datetime.utcnow()
            if orden.cantidad_final_buena is None and proceso_orden.cantidad_salida:
                orden.cantidad_final_buena = proceso_orden.cantidad_salida

        db.session.commit()
        return jsonify(proceso_orden_to_dict(proceso_orden))

    @app.route("/ordenes-produccion/<int:orden_id>/consumos", methods=["GET"])
    def listar_consumos_orden(orden_id: int):
        OrdenProduccion.query.get_or_404(orden_id)
        consumos = ConsumoMateriaPrima.query.filter_by(
            orden_produccion_id=orden_id
        ).all()
        return jsonify([consumo_materia_prima_to_dict(c) for c in consumos])

    @app.route("/ordenes-produccion/<int:orden_id>/consumos", methods=["POST"])
    def crear_consumo_orden(orden_id: int):
        OrdenProduccion.query.get_or_404(orden_id)
        data = request.get_json(silent=True) or {}
        materia_prima_id = data.get("materia_prima_id")
        if materia_prima_id is None:
            return jsonify({"error": "materia_prima_id es requerido"}), 400
        materia = MateriaPrima.query.get(materia_prima_id)
        if not materia:
            return jsonify({"error": "materia_prima_id no encontrado"}), 404

        proceso_orden_id = data.get("proceso_orden_id")
        if proceso_orden_id is not None:
            proceso_orden = ProcesoOrden.query.get(proceso_orden_id)
            if not proceso_orden or proceso_orden.orden_produccion_id != orden_id:
                return jsonify({"error": "proceso_orden_id inválido"}), 400

        try:
            cantidad_real = _parse_decimal(
                data.get("cantidad_real"), "cantidad_real"
            )
            cantidad_teorica = _parse_decimal(
                data.get("cantidad_teorica", 0),
                "cantidad_teorica",
                default=Decimal("0"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if cantidad_real is None or cantidad_real <= 0:
            return jsonify({"error": "cantidad_real debe ser mayor que cero"}), 400

        disponible = Decimal(str(materia.stock_actual or 0))
        if disponible < cantidad_real:
            return jsonify({"error": "Stock insuficiente"}), 400

        restante = _reservado_restante(orden_id, materia_prima_id)

        consumo = ConsumoMateriaPrima(
            orden_produccion_id=orden_id,
            proceso_orden_id=proceso_orden_id,
            materia_prima_id=materia_prima_id,
            cantidad_teorica=cantidad_teorica or 0,
            cantidad_real=cantidad_real,
            desperdicio=(cantidad_real - (cantidad_teorica or 0)),
            observaciones=(data.get("observaciones") or "").strip() or None,
        )
        db.session.add(consumo)

        materia.stock_actual = disponible - cantidad_real
        liberar = cantidad_real if cantidad_real <= restante else restante
        materia.stock_reservado = max(
            Decimal(str(materia.stock_reservado or 0)) - liberar, Decimal("0")
        )

        db.session.commit()
        return jsonify(consumo_materia_prima_to_dict(consumo)), 201

    @app.route(
        "/ordenes-produccion/<int:orden_id>/consumos/<int:consumo_id>",
        methods=["PUT", "PATCH"],
    )
    def actualizar_consumo_orden(orden_id: int, consumo_id: int):
        consumo = ConsumoMateriaPrima.query.get_or_404(consumo_id)
        if consumo.orden_produccion_id != orden_id:
            return jsonify({"error": "Consumo no pertenece a la orden"}), 400
        data = request.get_json(silent=True) or {}

        if "proceso_orden_id" in data:
            proceso_orden_id = data.get("proceso_orden_id")
            if proceso_orden_id is not None:
                proceso_orden = ProcesoOrden.query.get(proceso_orden_id)
                if not proceso_orden or proceso_orden.orden_produccion_id != orden_id:
                    return jsonify({"error": "proceso_orden_id inválido"}), 400
            consumo.proceso_orden_id = proceso_orden_id

        old_real = Decimal(str(consumo.cantidad_real or 0))
        old_teorico = Decimal(str(consumo.cantidad_teorica or 0))

        new_teorico = old_teorico
        new_real = old_real
        try:
            if "cantidad_teorica" in data:
                parsed = _parse_decimal(data.get("cantidad_teorica"), "cantidad_teorica")
                new_teorico = Decimal(str(parsed or 0))
            if "cantidad_real" in data:
                parsed = _parse_decimal(data.get("cantidad_real"), "cantidad_real")
                new_real = Decimal(str(parsed or 0))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        materia = MateriaPrima.query.get(consumo.materia_prima_id)
        total_teorico = sum(
            Decimal(str(c.cantidad_teorica or 0))
            for c in ConsumoMateriaPrima.query.filter_by(
                orden_produccion_id=orden_id, materia_prima_id=consumo.materia_prima_id
            ).all()
        )
        total_real = sum(
            Decimal(str(c.cantidad_real or 0))
            for c in ConsumoMateriaPrima.query.filter_by(
                orden_produccion_id=orden_id, materia_prima_id=consumo.materia_prima_id
            ).all()
        )
        total_teorico_after = total_teorico - old_teorico + new_teorico
        total_real_after = total_real - old_real + new_real

        delta_real = new_real - old_real
        if delta_real != 0:
            disponible = Decimal(str(materia.stock_actual or 0))
            if delta_real > 0 and disponible < delta_real:
                return jsonify({"error": "Stock insuficiente"}), 400
            materia.stock_actual = disponible - delta_real

        reservado_before = total_teorico - total_real
        reservado_before = reservado_before if reservado_before > 0 else Decimal("0")
        reservado_after = total_teorico_after - total_real_after
        reservado_after = reservado_after if reservado_after > 0 else Decimal("0")
        delta_reservado = reservado_after - reservado_before
        if delta_reservado != 0:
            materia.stock_reservado = max(
                Decimal(str(materia.stock_reservado or 0)) + delta_reservado, Decimal("0")
            )

        consumo.cantidad_teorica = new_teorico
        consumo.cantidad_real = new_real
        consumo.desperdicio = new_real - new_teorico

        if "observaciones" in data:
            consumo.observaciones = (data.get("observaciones") or "").strip() or None

        db.session.commit()
        return jsonify(consumo_materia_prima_to_dict(consumo))

    @app.route(
        "/ordenes-produccion/<int:orden_id>/consumos/<int:consumo_id>",
        methods=["DELETE"],
    )
    def eliminar_consumo_orden(orden_id: int, consumo_id: int):
        consumo = ConsumoMateriaPrima.query.get_or_404(consumo_id)
        if consumo.orden_produccion_id != orden_id:
            return jsonify({"error": "Consumo no pertenece a la orden"}), 400

        materia = MateriaPrima.query.get(consumo.materia_prima_id)
        old_real = Decimal(str(consumo.cantidad_real or 0))
        if old_real > 0:
            materia.stock_actual = Decimal(str(materia.stock_actual or 0)) + old_real

            total_teorico = sum(
                Decimal(str(c.cantidad_teorica or 0))
                for c in ConsumoMateriaPrima.query.filter_by(
                    orden_produccion_id=orden_id,
                    materia_prima_id=consumo.materia_prima_id,
                ).all()
            )
            total_real = sum(
                Decimal(str(c.cantidad_real or 0))
                for c in ConsumoMateriaPrima.query.filter_by(
                    orden_produccion_id=orden_id,
                    materia_prima_id=consumo.materia_prima_id,
                ).all()
            )
            reservado_before = total_teorico - total_real
            reservado_before = reservado_before if reservado_before > 0 else Decimal("0")
            reservado_after = total_teorico - (total_real - old_real)
            reservado_after = reservado_after if reservado_after > 0 else Decimal("0")
            delta_reservado = reservado_after - reservado_before
            materia.stock_reservado = max(
                Decimal(str(materia.stock_reservado or 0)) + delta_reservado, Decimal("0")
            )

        db.session.delete(consumo)
        db.session.commit()
        return jsonify({"message": "Consumo eliminado"})

    @app.route("/ordenes-produccion/<int:orden_id>/consumos-componentes", methods=["GET"])
    def listar_consumos_componentes_orden(orden_id: int):
        OrdenProduccion.query.get_or_404(orden_id)
        consumos = ConsumoProductoComponente.query.filter_by(
            orden_produccion_id=orden_id
        ).all()
        return jsonify([consumo_componente_to_dict(c) for c in consumos])

    @app.route("/ordenes-produccion/<int:orden_id>/consumos-componentes", methods=["POST"])
    def crear_consumo_componente_orden(orden_id: int):
        OrdenProduccion.query.get_or_404(orden_id)
        data = request.get_json(silent=True) or {}
        componente_id = data.get("componente_id")
        if componente_id is None:
            return jsonify({"error": "componente_id es requerido"}), 400
        componente = Producto.query.get(componente_id)
        if not componente:
            return jsonify({"error": "componente_id no encontrado"}), 404

        proceso_orden_id = data.get("proceso_orden_id")
        if proceso_orden_id is not None:
            proceso_orden = ProcesoOrden.query.get(proceso_orden_id)
            if not proceso_orden or proceso_orden.orden_produccion_id != orden_id:
                return jsonify({"error": "proceso_orden_id inválido"}), 400

        try:
            cantidad_real = _parse_decimal(
                data.get("cantidad_real"), "cantidad_real"
            )
            cantidad_teorica = _parse_decimal(
                data.get("cantidad_teorica", 0),
                "cantidad_teorica",
                default=Decimal("0"),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        if cantidad_real is None or cantidad_real <= 0:
            return jsonify({"error": "cantidad_real debe ser mayor que cero"}), 400

        disponible = Decimal(str(componente.stock_actual or 0))
        if disponible < cantidad_real:
            return jsonify({"error": "Stock insuficiente"}), 400

        restante = _reservado_restante_componente(orden_id, componente_id)

        consumo = ConsumoProductoComponente(
            orden_produccion_id=orden_id,
            proceso_orden_id=proceso_orden_id,
            componente_id=componente_id,
            cantidad_teorica=cantidad_teorica or 0,
            cantidad_real=cantidad_real,
            desperdicio=(cantidad_real - (cantidad_teorica or 0)),
            observaciones=(data.get("observaciones") or "").strip() or None,
        )
        db.session.add(consumo)

        componente.stock_actual = disponible - cantidad_real
        liberar = cantidad_real if cantidad_real <= restante else restante
        componente.stock_reservado = max(
            Decimal(str(componente.stock_reservado or 0)) - liberar, Decimal("0")
        )

        db.session.commit()
        return jsonify(consumo_componente_to_dict(consumo)), 201

    @app.route(
        "/ordenes-produccion/<int:orden_id>/consumos-componentes/<int:consumo_id>",
        methods=["PUT", "PATCH"],
    )
    def actualizar_consumo_componente_orden(orden_id: int, consumo_id: int):
        consumo = ConsumoProductoComponente.query.get_or_404(consumo_id)
        if consumo.orden_produccion_id != orden_id:
            return jsonify({"error": "Consumo no pertenece a la orden"}), 400
        data = request.get_json(silent=True) or {}

        if "proceso_orden_id" in data:
            proceso_orden_id = data.get("proceso_orden_id")
            if proceso_orden_id is not None:
                proceso_orden = ProcesoOrden.query.get(proceso_orden_id)
                if not proceso_orden or proceso_orden.orden_produccion_id != orden_id:
                    return jsonify({"error": "proceso_orden_id inválido"}), 400
            consumo.proceso_orden_id = proceso_orden_id

        old_real = Decimal(str(consumo.cantidad_real or 0))
        old_teorico = Decimal(str(consumo.cantidad_teorica or 0))

        new_teorico = old_teorico
        new_real = old_real
        try:
            if "cantidad_teorica" in data:
                parsed = _parse_decimal(data.get("cantidad_teorica"), "cantidad_teorica")
                new_teorico = Decimal(str(parsed or 0))
            if "cantidad_real" in data:
                parsed = _parse_decimal(data.get("cantidad_real"), "cantidad_real")
                new_real = Decimal(str(parsed or 0))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        componente = Producto.query.get(consumo.componente_id)
        total_teorico = sum(
            Decimal(str(c.cantidad_teorica or 0))
            for c in ConsumoProductoComponente.query.filter_by(
                orden_produccion_id=orden_id, componente_id=consumo.componente_id
            ).all()
        )
        total_real = sum(
            Decimal(str(c.cantidad_real or 0))
            for c in ConsumoProductoComponente.query.filter_by(
                orden_produccion_id=orden_id, componente_id=consumo.componente_id
            ).all()
        )
        total_teorico_after = total_teorico - old_teorico + new_teorico
        total_real_after = total_real - old_real + new_real

        delta_real = new_real - old_real
        if delta_real != 0:
            disponible = Decimal(str(componente.stock_actual or 0))
            if delta_real > 0 and disponible < delta_real:
                return jsonify({"error": "Stock insuficiente"}), 400
            componente.stock_actual = disponible - delta_real

        reservado_before = total_teorico - total_real
        reservado_before = reservado_before if reservado_before > 0 else Decimal("0")
        reservado_after = total_teorico_after - total_real_after
        reservado_after = reservado_after if reservado_after > 0 else Decimal("0")
        delta_reservado = reservado_after - reservado_before
        if delta_reservado != 0:
            componente.stock_reservado = max(
                Decimal(str(componente.stock_reservado or 0)) + delta_reservado,
                Decimal("0"),
            )

        consumo.cantidad_teorica = new_teorico
        consumo.cantidad_real = new_real
        consumo.desperdicio = new_real - new_teorico

        if "observaciones" in data:
            consumo.observaciones = (data.get("observaciones") or "").strip() or None

        db.session.commit()
        return jsonify(consumo_componente_to_dict(consumo))

    @app.route(
        "/ordenes-produccion/<int:orden_id>/consumos-componentes/<int:consumo_id>",
        methods=["DELETE"],
    )
    def eliminar_consumo_componente_orden(orden_id: int, consumo_id: int):
        consumo = ConsumoProductoComponente.query.get_or_404(consumo_id)
        if consumo.orden_produccion_id != orden_id:
            return jsonify({"error": "Consumo no pertenece a la orden"}), 400

        componente = Producto.query.get(consumo.componente_id)
        old_real = Decimal(str(consumo.cantidad_real or 0))
        if old_real > 0:
            componente.stock_actual = Decimal(str(componente.stock_actual or 0)) + old_real

            total_teorico = sum(
                Decimal(str(c.cantidad_teorica or 0))
                for c in ConsumoProductoComponente.query.filter_by(
                    orden_produccion_id=orden_id,
                    componente_id=consumo.componente_id,
                ).all()
            )
            total_real = sum(
                Decimal(str(c.cantidad_real or 0))
                for c in ConsumoProductoComponente.query.filter_by(
                    orden_produccion_id=orden_id,
                    componente_id=consumo.componente_id,
                ).all()
            )
            reservado_before = total_teorico - total_real
            reservado_before = reservado_before if reservado_before > 0 else Decimal("0")
            reservado_after = total_teorico - (total_real - old_real)
            reservado_after = reservado_after if reservado_after > 0 else Decimal("0")
            delta_reservado = reservado_after - reservado_before
            componente.stock_reservado = max(
                Decimal(str(componente.stock_reservado or 0)) + delta_reservado,
                Decimal("0"),
            )

        db.session.delete(consumo)
        db.session.commit()
        return jsonify({"message": "Consumo eliminado"})

    # ---------- REPORTES ----------

    @app.route("/reportes/tiempo-total-orden", methods=["GET"])
    def reporte_tiempo_total_orden():
        desde = request.args.get("desde")
        hasta = request.args.get("hasta")
        try:
            desde_dt = _parse_datetime(desde, "desde") if desde else None
            hasta_dt = _parse_datetime(hasta, "hasta") if hasta else None
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        ordenes = OrdenProduccion.query.all()
        resultados = []
        now = datetime.utcnow()
        for orden in ordenes:
            if desde_dt and orden.fecha_inicio and orden.fecha_inicio < desde_dt:
                continue
            if hasta_dt and orden.fecha_inicio and orden.fecha_inicio > hasta_dt:
                continue
            if not orden.fecha_inicio:
                duracion_min = None
            else:
                fin = orden.fecha_fin or now
                duracion_min = (fin - orden.fecha_inicio).total_seconds() / 60
            resultados.append(
                {
                    "orden_id": orden.id,
                    "codigo": orden.codigo,
                    "duracion_min": duracion_min,
                }
            )
        return jsonify(resultados)

    @app.route("/reportes/tiempo-por-proceso", methods=["GET"])
    def reporte_tiempo_por_proceso():
        procesos = Proceso.query.all()
        proceso_map = {p.id: p.nombre for p in procesos}
        items = ProcesoOrden.query.filter(
            ProcesoOrden.inicio.isnot(None), ProcesoOrden.fin.isnot(None)
        ).all()
        detalle = []
        agregados = {}
        for item in items:
            duracion = (item.fin - item.inicio).total_seconds() / 60
            detalle.append(
                {
                    "orden_produccion_id": item.orden_produccion_id,
                    "proceso_id": item.proceso_id,
                    "proceso_nombre": proceso_map.get(item.proceso_id),
                    "duracion_min": duracion,
                }
            )
            agg = agregados.setdefault(item.proceso_id, {"total": 0, "count": 0})
            agg["total"] += duracion
            agg["count"] += 1

        promedios = []
        for proceso_id, agg in agregados.items():
            promedios.append(
                {
                    "proceso_id": proceso_id,
                    "proceso_nombre": proceso_map.get(proceso_id),
                    "promedio_min": agg["total"] / agg["count"]
                    if agg["count"]
                    else None,
                    "total_registros": agg["count"],
                }
            )
        return jsonify({"promedios": promedios, "detalle": detalle})

    @app.route("/reportes/perdidas-por-proceso", methods=["GET"])
    def reporte_perdidas_por_proceso():
        procesos = Proceso.query.all()
        proceso_map = {p.id: p.nombre for p in procesos}
        items = ProcesoOrden.query.all()
        acumulado = {}
        for item in items:
            perdida = Decimal(str(item.cantidad_perdida or 0))
            acumulado[item.proceso_id] = acumulado.get(item.proceso_id, Decimal("0")) + perdida
        respuesta = [
            {
                "proceso_id": pid,
                "proceso_nombre": proceso_map.get(pid),
                "cantidad_perdida": float(total),
            }
            for pid, total in acumulado.items()
        ]
        return jsonify(respuesta)

    @app.route("/reportes/consumo-teorico-vs-real", methods=["GET"])
    def reporte_consumo_teorico_vs_real():
        orden_id = request.args.get("orden_id")
        if not orden_id:
            return jsonify({"error": "orden_id es requerido"}), 400
        orden = OrdenProduccion.query.get(orden_id)
        if not orden:
            return jsonify({"error": "Orden no encontrada"}), 404
        consumos = ConsumoMateriaPrima.query.filter_by(
            orden_produccion_id=orden_id
        ).all()
        total_teorico = sum(Decimal(str(c.cantidad_teorica or 0)) for c in consumos)
        total_real = sum(Decimal(str(c.cantidad_real or 0)) for c in consumos)
        return jsonify(
            {
                "orden_id": orden.id,
                "codigo": orden.codigo,
                "total_teorico": float(total_teorico),
                "total_real": float(total_real),
                "delta": float(total_real - total_teorico),
            }
        )

    @app.route("/reportes/ordenes-atascadas", methods=["GET"])
    def reporte_ordenes_atascadas():
        minutos = request.args.get("minutos", 120)
        try:
            minutos = int(minutos)
        except (TypeError, ValueError):
            return jsonify({"error": "minutos debe ser entero"}), 400
        limite = datetime.utcnow() - timedelta(minutes=minutos)
        procesos = ProcesoOrden.query.filter(
            ProcesoOrden.estado == "EN_PROCESO", ProcesoOrden.inicio < limite
        ).all()
        respuesta = [
            {
                "orden_produccion_id": p.orden_produccion_id,
                "proceso_id": p.proceso_id,
                "proceso_orden_id": p.id,
                "inicio": p.inicio.isoformat() if p.inicio else None,
            }
            for p in procesos
        ]
        return jsonify(respuesta)

    prefix = app.config.get("URL_PREFIX", "/coproda")
    if prefix:
        # Montar la app bajo un prefijo (por ejemplo /coproda)
        def _not_found(environ, start_response):
            return Response("Not Found", status=404)(environ, start_response)

        app.wsgi_app = DispatcherMiddleware(_not_found, {prefix: app.wsgi_app})

    return app



if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
