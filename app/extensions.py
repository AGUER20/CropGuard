"""
Central place for Flask extension instances.

Kept separate from __init__.py to avoid circular imports: blueprints and
models import `db`, `bcrypt`, `login_manager` from here rather than from
the app factory itself.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"
