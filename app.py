from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_migrate import Migrate

from config import Config
from models import CategoriaProducto, Cliente, Producto, db



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

        if not codigo:
            return jsonify({"error": "El código es requerido"}), 400
        if not nombre:
            return jsonify({"error": "El nombre es requerido"}), 400

        conflicto = Cliente.query.filter_by(codigo=codigo).first()
        if conflicto:
            return jsonify({"error": "Ya existe un cliente con ese código"}), 409

        cliente = Cliente(
            codigo=codigo, nombre=nombre, telefono=telefono, direccion=direccion
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

        db.session.commit()
        return jsonify(cliente_to_dict(cliente))

    @app.route("/clientes/<int:cliente_id>", methods=["DELETE"])
    def eliminar_cliente(cliente_id: int):
        cliente = Cliente.query.get_or_404(cliente_id)
        db.session.delete(cliente)
        db.session.commit()
        return jsonify({"message": "Cliente eliminado"})

    return app



if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
