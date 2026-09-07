from datetime import datetime, timezone

from app.extensions import db


class SurveyItem(db.Model):
    __tablename__ = "survey_items"
    __table_args__ = (
        db.UniqueConstraint("xlsform_id", "row_number", name="uq_survey_item_xlsform_row"),
    )

    id = db.Column(db.Integer, primary_key=True)
    xlsform_id = db.Column(db.Integer, db.ForeignKey("xlsforms.id"), nullable=False, index=True)
    sheet_name = db.Column(db.String(40), nullable=False, default="survey")
    row_number = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(255), nullable=True)
    list_name = db.Column(db.String(255), nullable=True, index=True)
    english_label = db.Column(db.Text, nullable=True)
    raw_row_data = db.Column(db.JSON, nullable=True)
    relevant = db.Column(db.Text, nullable=True)
    appearance = db.Column(db.String(255), nullable=True)
    is_group = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    xlsform = db.relationship("XLSForm", back_populates="survey_items")
