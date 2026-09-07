from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from sqlalchemy import func
from wtforms import BooleanField, PasswordField, SelectMultipleField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional

from app.models import User


class ReviewerForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Length(max=255)])
    password = PasswordField("Password", validators=[Optional(), Length(min=12, max=128)])
    password_confirm = PasswordField(
        "Confirm password",
        validators=[EqualTo("password", message="Passwords must match.")],
    )
    is_active = BooleanField("Active")
    language_ids = SelectMultipleField("Languages", coerce=int)
    submit = SubmitField("Save reviewer")

    def __init__(self, *args, user=None, require_password=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.require_password = require_password

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        valid = True
        username = self.username.data.strip()
        email = self.email.data.strip()

        if self.require_password and not self.password.data:
            self.password.errors.append("Password is required.")
            valid = False

        user_id = self.user.id if self.user else None
        username_exists = User.query.filter(
            func.lower(User.username) == username.lower(),
            User.id != user_id,
        ).first()
        if username_exists:
            self.username.errors.append("Username is already in use.")
            valid = False

        email_exists = User.query.filter(
            func.lower(User.email) == email.lower(),
            User.id != user_id,
        ).first()
        if email_exists:
            self.email.errors.append("Email is already in use.")
            valid = False

        if "@" not in email:
            self.email.errors.append("Enter a valid email address.")
            valid = False

        return valid


class XLSFormUploadForm(FlaskForm):
    xlsform_file = FileField(
        "XLSForm file",
        validators=[
            FileRequired(),
            FileAllowed(["xlsx"], "Upload a valid .xlsx file."),
        ],
    )
    submit = SubmitField("Upload XLSForm")
