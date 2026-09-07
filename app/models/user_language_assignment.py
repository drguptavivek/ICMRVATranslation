from datetime import datetime, timezone

from app.extensions import db


class UserLanguageAssignment(db.Model):
    __tablename__ = "user_language_assignments"
    __table_args__ = (
        db.UniqueConstraint("user_id", "language_id", name="uq_user_language_assignment"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    language_id = db.Column(
        db.Integer,
        db.ForeignKey("languages.id"),
        nullable=False,
        index=True,
    )
    assigned_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="language_assignments")
    language = db.relationship("Language", back_populates="user_assignments")
