import os
import secrets
from pathlib import Path

from flask import Flask, g, request
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

from .extensions import csrf, db, login_manager, migrate
from .routes import main_bp
from .services.datetime_display import format_datetime_for_display


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1,
    )
    if app.config.get("SECRET_KEY") in {
        None,
        "",
        "dev-change-me",
        "change-this-in-development",
        "replace-with-a-long-random-private-value",
    }:
        raise RuntimeError("Set SECRET_KEY to a strong, private value before starting the application.")

    os.makedirs(app.instance_path, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["EXPORT_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    @app.before_request
    def create_content_security_policy_nonce():
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def add_content_security_policy_nonce():
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def add_security_headers(response):
        csp_nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{csp_nonce}' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.endpoint == "static":
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response

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
