from datetime import datetime

from app.extensions import db


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"
    __table_args__ = (
        db.UniqueConstraint("identifier", "client_address", name="uq_login_attempt_identity_address"),
    )

    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(255), nullable=False, index=True)
    client_address = db.Column(db.String(64), nullable=False)
    failure_count = db.Column(db.Integer, nullable=False, default=0)
    last_failed_at = db.Column(db.DateTime, nullable=True)
    locked_until = db.Column(db.DateTime, nullable=True)

    def is_locked(self):
        return self.locked_until is not None and self.locked_until > datetime.now()
