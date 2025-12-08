from flask import Flask, jsonify, request
from config import Config
from models import db, Producto, Cliente, Orden, OrdenItem, Usuario, CategoriaProducto, MarcaProducto, Tienda, Talla
from flask_migrate import Migrate
from datetime import datetime
from flask_cors import CORS
from datetime import datetime



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




    return app



if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
