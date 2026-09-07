from datetime import datetime, timezone

from app.extensions import db


class XLSForm(db.Model):
    __tablename__ = "xlsforms"

    STATUS_IMPORTED = "imported"

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    form_title = db.Column(db.String(255), nullable=True)
    form_id = db.Column(db.String(255), nullable=True)
    version = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(40), nullable=False, default=STATUS_IMPORTED)
    survey_row_count = db.Column(db.Integer, nullable=False, default=0)
    choices_row_count = db.Column(db.Integer, nullable=False, default=0)
    detected_language_count = db.Column(db.Integer, nullable=False, default=0)

    uploader = db.relationship("User", back_populates="uploaded_xlsforms")
    survey_items = db.relationship(
        "SurveyItem",
        back_populates="xlsform",
        cascade="all, delete-orphan",
        order_by="SurveyItem.row_number",
    )
    choice_items = db.relationship(
        "ChoiceItem",
        back_populates="xlsform",
        cascade="all, delete-orphan",
        order_by="ChoiceItem.row_number",
    )
    translation_reviews = db.relationship(
        "TranslationReview",
        back_populates="xlsform",
        cascade="all, delete-orphan",
    )
    translation_history = db.relationship(
        "TranslationHistory",
        back_populates="xlsform",
        cascade="all, delete-orphan",
    )
    reviewer_assignments = db.relationship(
        "ReviewerFormAssignment",
        back_populates="xlsform",
        cascade="all, delete-orphan",
    )
