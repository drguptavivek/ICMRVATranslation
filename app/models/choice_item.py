from app.extensions import db


class ChoiceItem(db.Model):
    __tablename__ = "choice_items"
    __table_args__ = (
        db.UniqueConstraint("xlsform_id", "row_number", name="uq_choice_item_xlsform_row"),
    )

    id = db.Column(db.Integer, primary_key=True)
    xlsform_id = db.Column(db.Integer, db.ForeignKey("xlsforms.id"), nullable=False, index=True)
    row_number = db.Column(db.Integer, nullable=False)
    list_name = db.Column(db.String(255), nullable=True, index=True)
    name = db.Column(db.String(255), nullable=True)
    english_label = db.Column(db.Text, nullable=True)
    raw_row_data = db.Column(db.JSON, nullable=True)

    xlsform = db.relationship("XLSForm", back_populates="choice_items")
