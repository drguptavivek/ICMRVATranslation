from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.admin.forms import ReviewerForm, XLSFormUploadForm
from app.extensions import db
from app.models import (
    ChoiceItem,
    Language,
    ReviewerFormAssignment,
    SurveyItem,
    User,
    UserLanguageAssignment,
    XLSForm,
)
from app.services.xlsform_importer import ensure_detected_languages, import_questionnaire_content
from app.services.xlsform_parser import english_header
from app.services.xlsform_parser import XLSFormValidationError, parse_xlsform
from app.services.review_workflow import changed_reviews_for_assignment
from app.services.xlsform_exporter import XLSFormExportError, export_reviewed_xlsform


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped_view


@admin_bp.route("/")
@admin_required
def dashboard():
    reviewer_count = User.query.filter_by(role=User.ROLE_REVIEWER).count()
    language_count = Language.query.count()
    form_assignments = ReviewerFormAssignment.query.order_by(
        ReviewerFormAssignment.language_id,
        ReviewerFormAssignment.user_id,
        ReviewerFormAssignment.xlsform_id,
    ).all()
    return render_template(
        "admin/dashboard.html",
        reviewer_count=reviewer_count,
        language_count=language_count,
        form_assignments=form_assignments,
    )


@admin_bp.route("/users")
@admin_required
def users():
    users = User.query.order_by(User.role, User.username).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/xlsforms", methods=["GET", "POST"])
@admin_required
def xlsforms():
    form = XLSFormUploadForm()
    import_summary = None

    if form.validate_on_submit():
        uploaded_file = form.xlsform_file.data
        original_filename = secure_filename(uploaded_file.filename or "")
        if not original_filename.lower().endswith(".xlsx"):
            flash("Upload a valid .xlsx file.", "danger")
            return redirect(url_for("admin.xlsforms"))

        try:
            parse_result = parse_xlsform(uploaded_file.stream)
        except XLSFormValidationError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.xlsforms"))

        previous_xlsform = XLSForm.query.order_by(
            XLSForm.uploaded_at.desc(),
            XLSForm.id.desc(),
        ).first()
        uploaded_file.stream.seek(0)
        stored_filename = _save_uploaded_xlsform(uploaded_file, original_filename)
        xlsform = XLSForm(
            original_filename=original_filename,
            stored_filename=stored_filename,
            uploaded_by=current_user.id,
            form_title=parse_result.form_title,
            form_id=parse_result.form_id,
            version=parse_result.version,
            status=XLSForm.STATUS_IMPORTED,
            survey_row_count=parse_result.survey_row_count,
            choices_row_count=parse_result.choices_row_count,
            detected_language_count=len(parse_result.languages),
        )
        db.session.add(xlsform)
        ensure_detected_languages(parse_result.languages)
        db.session.flush()
        import_result = import_questionnaire_content(
            xlsform,
            parse_result,
            previous_xlsform=previous_xlsform,
        )
        db.session.commit()

        import_summary = {
            "xlsform": xlsform,
            "languages": parse_result.languages,
            "import_result": import_result,
        }
        flash("XLSForm uploaded and inspected.", "success")

    elif form.is_submitted():
        flash("Upload a valid .xlsx file.", "danger")

    xlsforms = XLSForm.query.order_by(XLSForm.uploaded_at.desc()).all()
    return render_template(
        "admin/xlsforms.html",
        form=form,
        import_summary=import_summary,
        xlsforms=xlsforms,
    )


@admin_bp.route("/xlsforms/<int:xlsform_id>/import", methods=["POST"])
@admin_required
def import_xlsform_content(xlsform_id):
    xlsform = db.session.get(XLSForm, xlsform_id)
    if xlsform is None:
        abort(404)

    workbook_path = Path(current_app.config["UPLOAD_FOLDER"]) / xlsform.stored_filename
    if not workbook_path.exists():
        flash("The stored XLSForm file could not be found.", "danger")
        return redirect(url_for("admin.xlsforms"))

    with workbook_path.open("rb") as workbook_file:
        try:
            parse_result = parse_xlsform(workbook_file)
        except XLSFormValidationError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.xlsforms"))

    xlsform.form_title = parse_result.form_title
    xlsform.form_id = parse_result.form_id
    xlsform.version = parse_result.version
    xlsform.survey_row_count = parse_result.survey_row_count
    xlsform.choices_row_count = parse_result.choices_row_count
    xlsform.detected_language_count = len(parse_result.languages)
    ensure_detected_languages(parse_result.languages)
    db.session.flush()
    import_result = import_questionnaire_content(xlsform, parse_result)
    db.session.commit()
    flash(
        (
            f"Imported {import_result.reviewable_survey_items} reviewable survey items "
            f"and {import_result.choice_items} choices. "
            f"Skipped {import_result.skipped_survey_items} non-reviewable survey rows."
        ),
        "success",
    )
    return redirect(url_for("admin.xlsforms"))


@admin_bp.route("/assignments/<int:assignment_id>/changes")
@admin_required
def view_assignment_changes(assignment_id):
    assignment = db.session.get(ReviewerFormAssignment, assignment_id)
    if assignment is None:
        abort(404)
    changed_reviews = changed_reviews_for_assignment(assignment)
    survey_items = {
        item.row_number: item
        for item in SurveyItem.query.filter_by(xlsform_id=assignment.xlsform_id).all()
    }
    choice_items = {
        item.row_number: item
        for item in ChoiceItem.query.filter_by(xlsform_id=assignment.xlsform_id).all()
    }
    rows = []
    for review in changed_reviews:
        if review.sheet_name == "survey":
            source_item = survey_items.get(review.row_number)
            variable = source_item.name if source_item else ""
            english = (
                source_item.english_label
                if source_item and review.field_name == "label"
                else (source_item.raw_row_data or {}).get(english_header(review.field_name), "")
                if source_item
                else ""
            )
        else:
            source_item = choice_items.get(review.row_number)
            variable = source_item.name if source_item else ""
            english = source_item.english_label if source_item else ""
        rows.append(
            {
                "review": review,
                "variable": variable,
                "english": english,
                "field_name": review.field_name,
            }
        )
    return render_template(
        "admin/assignment_changes.html",
        assignment=assignment,
        rows=rows,
    )


@admin_bp.route("/assignments/<int:assignment_id>/download")
@admin_required
def download_assignment_xlsform(assignment_id):
    assignment = db.session.get(ReviewerFormAssignment, assignment_id)
    if assignment is None:
        abort(404)
    if assignment.status != ReviewerFormAssignment.STATUS_SAVED:
        abort(404)
    try:
        export_path = export_reviewed_xlsform(
            assignment,
            upload_folder=current_app.config["UPLOAD_FOLDER"],
            export_folder=current_app.config["EXPORT_FOLDER"],
        )
        if not export_path.is_file():
            raise XLSFormExportError("The reviewed XLSForm was not created.")
    except XLSFormExportError:
        current_app.logger.exception("Unable to generate reviewed XLSForm for assignment %s", assignment.id)
        flash("Unable to generate the reviewed XLSForm. Please check the server log.", "danger")
        return redirect(url_for("admin.dashboard"))
    except Exception:
        current_app.logger.exception("Unexpected error generating reviewed XLSForm for assignment %s", assignment.id)
        flash("Unable to generate the reviewed XLSForm. Please check the server log.", "danger")
        return redirect(url_for("admin.dashboard"))

    return send_file(
        export_path,
        as_attachment=True,
        download_name=export_path.name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@admin_bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user():
    languages = Language.query.filter_by(is_active=True).order_by(Language.display_name).all()
    form = ReviewerForm(require_password=True)
    _set_language_choices(form, languages)

    if form.validate_on_submit():
        user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip(),
            role=User.ROLE_REVIEWER,
            is_active=form.is_active.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        _sync_language_assignments(user, form.language_ids.data)
        db.session.commit()
        flash("Reviewer created.", "success")
        return redirect(url_for("admin.users"))

    if not form.is_submitted():
        form.is_active.data = True

    return render_template(
        "admin/user_form.html",
        form=form,
        languages=languages,
        title="Create reviewer",
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if user is None or not user.is_reviewer:
        abort(404)

    languages = Language.query.filter_by(is_active=True).order_by(Language.display_name).all()
    form = ReviewerForm(user=user)
    _set_language_choices(form, languages)

    if form.validate_on_submit():
        user.username = form.username.data.strip()
        user.email = form.email.data.strip()
        user.is_active = form.is_active.data
        if form.password.data:
            user.set_password(form.password.data)
        _sync_language_assignments(user, form.language_ids.data)
        db.session.commit()
        flash("Reviewer updated.", "success")
        return redirect(url_for("admin.users"))

    if not form.is_submitted():
        form.username.data = user.username
        form.email.data = user.email
        form.is_active.data = user.is_active
        form.language_ids.data = [assignment.language_id for assignment in user.language_assignments]

    return render_template(
        "admin/user_form.html",
        form=form,
        languages=languages,
        title="Edit reviewer",
        user=user,
    )


def _set_language_choices(form, languages):
    form.language_ids.choices = [
        (language.id, language.display_name) for language in languages
    ]


def _sync_language_assignments(user, language_ids):
    selected_ids = set(language_ids or [])
    existing = {assignment.language_id: assignment for assignment in user.language_assignments}

    for language_id in selected_ids - set(existing):
        user.language_assignments.append(UserLanguageAssignment(language_id=language_id))

    for language_id in set(existing) - selected_ids:
        db.session.delete(existing[language_id])


def _save_uploaded_xlsform(uploaded_file, original_filename):
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}_{original_filename}"
    uploaded_file.save(upload_dir / stored_filename)
    return stored_filename
