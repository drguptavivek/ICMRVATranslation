from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.services.display_text import clean_html_for_display, clean_text_for_display
from app.services.translation_links import google_translate_language_code
from app.services.review_workflow import (
    assigned_language_for_user,
    build_review_rows,
    changed_reviews_for_assignment,
    get_or_create_form_assignment,
    history_entries_for_assignment,
    latest_xlsform,
    reviewable_count,
    save_complete_form,
    save_question_with_choices,
)


reviewer_bp = Blueprint("reviewer", __name__, url_prefix="/reviewer")


@reviewer_bp.route("/")
@login_required
def dashboard():
    if not current_user.is_reviewer:
        abort(403)

    language = assigned_language_for_user(current_user)
    xlsform = latest_xlsform()
    assignment = None
    total_questions = 0
    if language is not None and xlsform is not None:
        assignment = get_or_create_form_assignment(current_user, xlsform, language)
        total_questions = reviewable_count(xlsform)
        db.session.commit()

    return render_template(
        "reviewer/dashboard.html",
        language=language,
        xlsform=xlsform,
        assignment=assignment,
        total_questions=total_questions,
    )


@reviewer_bp.route("/review", methods=["GET", "POST"])
@login_required
def review():
    if not current_user.is_reviewer:
        abort(403)

    language = assigned_language_for_user(current_user)
    xlsform = latest_xlsform()
    if language is None:
        abort(403)
    if xlsform is None:
        flash("No XLSForm has been imported yet.", "info")
        return redirect(url_for("reviewer.dashboard"))

    assignment = get_or_create_form_assignment(current_user, xlsform, language)
    if request.method == "POST":
        save_complete_form(current_user, xlsform, language, request.form)
        saved_change_count = len(changed_reviews_for_assignment(assignment))
        db.session.commit()
        flash(
            f"Form review saved successfully. {saved_change_count} translation changes are currently saved.",
            "success",
        )
        return redirect(url_for("reviewer.review"))

    assignment.mark_opened()
    db.session.commit()

    review_rows = build_review_rows(xlsform, language, current_user)
    history_entries = history_entries_for_assignment(assignment)

    return render_template(
        "reviewer/review_form.html",
        language=language,
        translation_language_code=google_translate_language_code(language.language_code),
        xlsform=xlsform,
        assignment=assignment,
        review_rows=review_rows,
        history_entries=history_entries,
    )


@reviewer_bp.route("/review/<int:item_id>", methods=["GET", "POST"])
@login_required
def review_item(item_id):
    return redirect(url_for("reviewer.review"))


@reviewer_bp.route("/review/<int:item_id>/save", methods=["POST"])
@login_required
def save_review_item(item_id):
    if not current_user.is_reviewer:
        abort(403)

    language = assigned_language_for_user(current_user)
    xlsform = latest_xlsform()
    if language is None or xlsform is None:
        abort(403)

    choice_values = {}
    for key, value in request.form.items():
        if key.startswith("choice_"):
            try:
                choice_values[int(key.removeprefix("choice_"))] = str(clean_html_for_display(value))
            except ValueError:
                continue

    item, changed_count, is_edited = save_question_with_choices(
        current_user,
        xlsform,
        language,
        item_id,
        str(clean_html_for_display(request.form.get("question_translation", ""))),
        choice_values,
    )
    if item is None:
        abort(404)
    db.session.commit()
    return jsonify(
        {
            "status": "saved",
            "changed_count": changed_count,
            "question_id": item.id,
            "translation": request.form.get("question_translation", "").strip(),
            "translation_html": str(clean_html_for_display(request.form.get("question_translation", "").strip())),
            "choices": {str(key): value.strip() for key, value in choice_values.items()},
            "choice_html": {str(key): str(clean_html_for_display(value.strip())) for key, value in choice_values.items()},
            "is_edited": is_edited,
        }
    )
