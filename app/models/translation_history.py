from datetime import datetime, timezone

from app.extensions import db


class TranslationHistory(db.Model):
    __tablename__ = "translation_history"

    ITEM_TYPE_QUESTION = "Question"
    ITEM_TYPE_CHOICE = "Choice"
    ITEM_TYPE_GROUP = "Group"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    xlsform_id = db.Column(db.Integer, db.ForeignKey("xlsforms.id"), nullable=False, index=True)
    language_id = db.Column(db.Integer, db.ForeignKey("languages.id"), nullable=False, index=True)
    sheet_name = db.Column(db.String(40), nullable=False)
    row_number = db.Column(db.Integer, nullable=False)
    item_type = db.Column(db.String(40), nullable=False)
    question_id = db.Column(db.String(255), nullable=True)
    english_value = db.Column(db.Text, nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = db.relationship("User", back_populates="translation_history")
    xlsform = db.relationship("XLSForm", back_populates="translation_history")
    language = db.relationship("Language", back_populates="translation_history")
