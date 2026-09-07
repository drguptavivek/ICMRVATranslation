from datetime import datetime, timezone

from app.extensions import db


class ReviewerFormAssignment(db.Model):
    __tablename__ = "reviewer_form_assignments"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "xlsform_id",
            "language_id",
            name="uq_reviewer_form_assignment",
        ),
    )

    STATUS_NOT_STARTED = "Not Started"
    STATUS_EDITING = "Editing"
    STATUS_SAVED = "Saved"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    xlsform_id = db.Column(db.Integer, db.ForeignKey("xlsforms.id"), nullable=False, index=True)
    language_id = db.Column(db.Integer, db.ForeignKey("languages.id"), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default=STATUS_NOT_STARTED)
    first_opened_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_saved_at = db.Column(db.DateTime(timezone=True), nullable=True)

    reviewer = db.relationship("User", back_populates="form_assignments")
    xlsform = db.relationship("XLSForm", back_populates="reviewer_assignments")
    language = db.relationship("Language", back_populates="form_assignments")

    def mark_opened(self):
        if self.first_opened_at is None:
            self.first_opened_at = datetime.now(timezone.utc)
        if self.status == self.STATUS_NOT_STARTED:
            self.status = self.STATUS_EDITING

    def mark_saved(self):
        if self.first_opened_at is None:
            self.first_opened_at = datetime.now(timezone.utc)
        self.last_saved_at = datetime.now(timezone.utc)
        self.status = self.STATUS_SAVED
