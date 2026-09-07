import os
from pathlib import Path

from flask import Flask

from config import Config

from .extensions import csrf, db, login_manager, migrate
from .routes import main_bp
from .services.datetime_display import format_datetime_for_display


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["EXPORT_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    @app.template_filter("display_datetime")
    def display_datetime(value):
        return format_datetime_for_display(value, app.config.get("DISPLAY_TIMEZONE", "Asia/Kolkata"))

    from . import models
    from .admin.routes import admin_bp
    from .auth.routes import auth_bp
    from .cli import register_cli
    from .reviewer.routes import reviewer_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(reviewer_bp)
    register_cli(app)

    return app
