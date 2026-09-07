from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    ROLE_ADMIN = "admin"
    ROLE_REVIEWER = "reviewer"
    VALID_ROLES = (ROLE_ADMIN, ROLE_REVIEWER)

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_REVIEWER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    language_assignments = db.relationship(
        "UserLanguageAssignment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    languages = db.relationship(
        "Language",
        secondary="user_language_assignments",
        back_populates="users",
        viewonly=True,
    )
    uploaded_xlsforms = db.relationship("XLSForm", back_populates="uploader")
    form_assignments = db.relationship(
        "ReviewerFormAssignment",
        back_populates="reviewer",
        cascade="all, delete-orphan",
    )
    translation_history = db.relationship(
        "TranslationHistory",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def is_reviewer(self):
        return self.role == self.ROLE_REVIEWER
