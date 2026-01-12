from datetime import datetime

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
    EstadoOrden,
    Permiso,
    Producto,
    TipoPago,
    Usuario,
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
            "precio_cf": float(producto.precio_cf),
            "precio_minorista": float(producto.precio_minorista),
            "precio_mayorista": float(producto.precio_mayorista),
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

    @app.route("/productos", methods=["POST"])
    def crear_producto():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        codigo = (data.get("codigo") or "").strip()
        foto = (data.get("foto") or "").strip() or None
        categoria_id = data.get("categoria_id")

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
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        producto = Producto(
            nombre=nombre,
            codigo=codigo,
            foto=foto,
            categoria_id=categoria_id,
            precio_cf=precio_cf,
            precio_minorista=precio_minorista,
            precio_mayorista=precio_mayorista,
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

        if "foto" in data:
            producto.foto = (data.get("foto") or "").strip() or None

        if "categoria_id" in data:
            categoria_id = data.get("categoria_id")
            categoria = CategoriaProducto.query.get(categoria_id)
            if not categoria:
                return jsonify({"error": "Categoría no encontrada"}), 404
            producto.categoria_id = categoria_id

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
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        cliente = Cliente(
            codigo=codigo,
            nombre=nombre,
            telefono=telefono,
            direccion=direccion,
            clasificacion_precio=clasificacion_precio,
            saldo=saldo,
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
        db.session.delete(pago)
        db.session.commit()
        return jsonify({"message": "Pago eliminado"})

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
            "fecha": orden.fecha.isoformat() if orden.fecha else None,
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
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        tipo_pago_id = data.get("tipo_pago_id")
        estado_id = data.get("estado_id")
        cliente_id = data.get("cliente_id")
        saldo_val = data.get("saldo")

        try:
            _validate_fk(TipoPago, tipo_pago_id, "tipo_pago_id")
            _validate_fk(EstadoOrden, estado_id, "estado_id")
            _validate_fk(Cliente, cliente_id, "cliente_id")
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
            fecha=fecha,
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

        if "fecha" in data:
            try:
                orden.fecha = _parse_fecha(data.get("fecha"))
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

        if "estado_id" in data:
            try:
                _validate_fk(EstadoOrden, data.get("estado_id"), "estado_id")
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            except LookupError as exc:
                return jsonify({"error": str(exc)}), 404
            orden.estado_id = data.get("estado_id")

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

        db.session.commit()
        return jsonify(orden_to_dict(orden))

    @app.route("/ordenes/<int:orden_id>", methods=["DELETE"])
    def eliminar_orden(orden_id: int):
        orden = Orden.query.get_or_404(orden_id)
        OrdenItem.query.filter_by(orden_id=orden.id).delete()
        db.session.delete(orden)
        db.session.commit()
        return jsonify({"message": "Orden eliminada"})

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
