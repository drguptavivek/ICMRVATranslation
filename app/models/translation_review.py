from datetime import datetime, timezone

from app.extensions import db


class TranslationReview(db.Model):
    __tablename__ = "translation_reviews"
    __table_args__ = (
        db.UniqueConstraint(
            "xlsform_id",
            "sheet_name",
            "row_number",
            "field_name",
            "language_id",
            name="uq_translation_review_row_field_language",
        ),
    )

    STATUS_PENDING = "Pending"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_REVIEWED = "Reviewed"

    id = db.Column(db.Integer, primary_key=True)
    xlsform_id = db.Column(db.Integer, db.ForeignKey("xlsforms.id"), nullable=False, index=True)
    sheet_name = db.Column(db.String(40), nullable=False)
    row_number = db.Column(db.Integer, nullable=False)
    field_name = db.Column(db.String(40), nullable=False, default="label")
    language_id = db.Column(db.Integer, db.ForeignKey("languages.id"), nullable=False, index=True)
    original_cell_value = db.Column(db.Text, nullable=True)
    extracted_translation = db.Column(db.Text, nullable=True)
    edited_translation = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), nullable=False, default=STATUS_PENDING)
    edited_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    edited_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    xlsform = db.relationship("XLSForm", back_populates="translation_reviews")
    language = db.relationship("Language", back_populates="translation_reviews")
    editor = db.relationship("User", foreign_keys=[edited_by])

    def mark_edited(self, user_id):
        self.edited_by = user_id
        self.edited_at = datetime.now(timezone.utc)

    def mark_reviewed(self, user_id):
        self.mark_edited(user_id)
        self.reviewed_at = datetime.now(timezone.utc)
