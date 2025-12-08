from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


