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

    return app



if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
