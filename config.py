import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///xlsform_review.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "/")
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0").lower() in {
        "1",
        "true",
        "yes",
    }
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("SESSION_TIMEOUT_HOURS", 8))
    )
    SESSION_REFRESH_EACH_REQUEST = True
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", 5))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", 15))
    DISPLAY_TIMEZONE = os.environ.get("DISPLAY_TIMEZONE", "Asia/Kolkata")
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads"))
    EXPORT_FOLDER = os.environ.get("EXPORT_FOLDER", str(BASE_DIR / "instance" / "exports"))
