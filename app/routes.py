from flask import Blueprint, jsonify, redirect, url_for
from flask_login import current_user


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    if current_user.is_reviewer:
        return redirect(url_for("reviewer.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/health")
def health():
    return jsonify(status="ok")
