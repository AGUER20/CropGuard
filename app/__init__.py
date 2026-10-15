"""
Application factory. Wires together the Flask app, extensions, blueprints
(Controller layer) and error handlers, per the MVC architecture in
proposal section 3.8.
"""
import os
from flask import Flask, render_template
from app.config import config_by_name
from app.extensions import db, bcrypt, login_manager


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # --- init extensions ---
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # --- user loader for Flask-Login ---
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- register blueprints (Controller layer, grouped by role/module) ---
    from app.auth.routes import auth_bp
    from app.farmer.routes import farmer_bp
    from app.researcher.routes import researcher_bp
    from app.admin.routes import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(farmer_bp, url_prefix="/farmer")
    app.register_blueprint(researcher_bp, url_prefix="/researcher")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # --- public landing page ---
    @app.route("/")
    def index():
        return render_template("index.html")

    # --- error handlers ---
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    # --- template helpers ---
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        return {"current_year": datetime.utcnow().year, "app_name": "CropGuard"}

    return app
