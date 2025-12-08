import os

class Config:
    # Cambia esto por tu string real de conexión a Postgres
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://alexis:Alexis2012@localhost:5432/astridbackend"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False  # para soportar bien acentos en JSON
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")
