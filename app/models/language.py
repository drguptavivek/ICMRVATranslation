from app.extensions import db


class Language(db.Model):
    __tablename__ = "languages"

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(120), nullable=False)
    excel_header = db.Column(db.String(120), nullable=False, unique=True)
    language_code = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    user_assignments = db.relationship(
        "UserLanguageAssignment",
        back_populates="language",
        cascade="all, delete-orphan",
    )
    users = db.relationship(
        "User",
        secondary="user_language_assignments",
        back_populates="languages",
        viewonly=True,
    )
    translation_reviews = db.relationship("TranslationReview", back_populates="language")
    translation_history = db.relationship("TranslationHistory", back_populates="language")
    form_assignments = db.relationship(
        "ReviewerFormAssignment",
        back_populates="language",
        cascade="all, delete-orphan",
    )
