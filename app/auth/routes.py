from datetime import datetime, timedelta
from urllib.parse import urlsplit

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.forms import LoginForm
from app.extensions import db
from app.models import LoginAttempt, User


auth_bp = Blueprint("auth", __name__)
DUMMY_PASSWORD_HASH = generate_password_hash("login-timing-placeholder")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_post_login_url(current_user))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username_or_email.data.strip()
        normalized_identifier = identifier.casefold()
        client_address = request.remote_addr or "unknown"
        attempt = LoginAttempt.query.filter_by(
            identifier=normalized_identifier,
            client_address=client_address,
        ).first()
        if attempt is not None and attempt.is_locked():
            flash("Too many unsuccessful login attempts. Please try again later.", "danger")
            return render_template("auth/login.html", form=form), 429

        user = User.query.filter(
            or_(User.username.ilike(identifier), User.email.ilike(identifier))
        ).first()

        password_matches = (
            user.check_password(form.password.data)
            if user is not None
            else check_password_hash(DUMMY_PASSWORD_HASH, form.password.data)
        )
        if user is None or not password_matches or not user.is_active:
            if attempt is None:
                attempt = LoginAttempt(
                    identifier=normalized_identifier,
                    client_address=client_address,
                    failure_count=0,
                )
                db.session.add(attempt)
            attempt.failure_count += 1
            attempt.last_failed_at = datetime.now()
            if attempt.failure_count >= current_app.config.get("LOGIN_MAX_FAILURES", 5):
                attempt.locked_until = datetime.now() + timedelta(
                    minutes=current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15)
                )
            db.session.commit()
            if attempt.is_locked():
                flash("Too many unsuccessful login attempts. Please try again later.", "danger")
                return render_template("auth/login.html", form=form), 429
            flash("Invalid username, email, or password.", "danger")
            return render_template("auth/login.html", form=form), 401

        if attempt is not None:
            db.session.delete(attempt)
            db.session.commit()
        login_user(user)
        return redirect(_post_login_url(user))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


def _post_login_url(user):
    next_url = request.args.get("next")
    if next_url and next_url.startswith("/") and not urlsplit(next_url).netloc:
        return next_url
    if user.is_admin:
        return url_for("admin.dashboard")
    return url_for("reviewer.dashboard")
