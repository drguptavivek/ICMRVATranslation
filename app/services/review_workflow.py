import re

from app.extensions import db
from app.models import (
    ChoiceItem,
    ReviewerFormAssignment,
    SurveyItem,
    TranslationHistory,
    TranslationReview,
    XLSForm,
)
from app.services.display_text import clean_html_for_display, clean_text_for_display, sanitize_rich_html
from app.services.xlsform_parser import (
    ENGLISH_LABEL_HEADER,
    find_localized_header,
    parse_translation_cell,
)


SUPPORTING_FIELDS = {
    "hint": "Hint",
    "guidance_hint": "Guidance",
    "constraint_message": "Validation",
    "required_message": "Required Message",
}


TECHNICAL_TYPES = {"begin_group", "begin repeat", "end_group", "end repeat"}
INTERVIEW_LANGUAGE_LIST_NAME = "language"
INTERVIEW_LANGUAGE_LABEL = "interview language"
ENGLISH_LANGUAGE_NAME = "english"


def assigned_language_for_user(user):
    for assignment in user.language_assignments:
        if assignment.language.is_active:
            return assignment.language
    return None


def latest_xlsform():
    return XLSForm.query.order_by(XLSForm.uploaded_at.desc(), XLSForm.id.desc()).first()


def get_or_create_form_assignment(user, xlsform, language):
    assignment = ReviewerFormAssignment.query.filter_by(
        user_id=user.id,
        xlsform_id=xlsform.id,
        language_id=language.id,
    ).first()
    if assignment is None:
        assignment = ReviewerFormAssignment(
            user_id=user.id,
            xlsform_id=xlsform.id,
            language_id=language.id,
        )
        db.session.add(assignment)
    return assignment


def reviewable_survey_items_query(xlsform):
    return SurveyItem.query.filter(
        SurveyItem.xlsform_id == xlsform.id,
        SurveyItem.english_label.isnot(None),
        SurveyItem.type.notin_(TECHNICAL_TYPES),
    ).order_by(SurveyItem.row_number)


def displayed_survey_items_query(xlsform):
    """Return every reviewable survey item in its original XLSForm row order."""
    return reviewable_survey_items_query(xlsform)


def group_headings_by_next_question(xlsform):
    headings = {}
    current_heading = None
    survey_rows = SurveyItem.query.filter_by(xlsform_id=xlsform.id).order_by(SurveyItem.row_number).all()
    for item in survey_rows:
        if item.is_group and item.english_label:
            current_heading = item
            continue
        if is_reviewable_survey_item(item) and current_heading is not None:
            headings[item.id] = current_heading
    return headings


def build_review_layout(xlsform, language, user=None):
    displayed_items = displayed_survey_items_query(xlsform).all()
    displayed_ids = {item.id for item in displayed_items}
    choices_by_list = choice_items_by_list_name(xlsform)
    reviews = reviews_by_key(xlsform, language)
    edited_question_ids = edited_question_ids_for_reviews(displayed_items, choices_by_list, reviews, user)
    roots = []
    stack = []

    for item in SurveyItem.query.filter_by(xlsform_id=xlsform.id).order_by(SurveyItem.row_number).all():
        if item.type in {"begin_group", "begin repeat"}:
            group_node = {
                "kind": "group",
                "group": item,
                "english": clean_text_for_display(item.english_label),
                "value": clean_text_for_display(value_for_item(item, language, reviews, "survey")),
                "children": [],
            }
            _append_node(roots, stack, group_node)
            stack.append(group_node)
            continue

        if item.type in {"end_group", "end repeat"}:
            if stack:
                stack.pop()
            continue

        if item.id not in displayed_ids:
            continue

        choice_rows = []
        for choice in visible_choices_for_item(item, choices_by_list, language):
            choice_value = value_for_item(choice, language, reviews, "choices")
            choice_rows.append(
                {
                    "choice": choice,
                    "english": clean_text_for_display(choice.english_label or choice.name),
                    "value": clean_text_for_display(choice_value),
                    "value_html": clean_html_for_display(choice_value),
                    "editor_html": str(sanitize_rich_html(choice_value)),
                }
            )
        question_value = value_for_item(item, language, reviews, "survey")
        question_node = {
            "kind": "question",
            "question": item,
            "english": display_question_label(item),
            "value": clean_text_for_display(question_value),
            "control_type": choice_control_type(item),
            "is_edited": item.id in edited_question_ids,
            "choices": choice_rows,
            "modal_choices": [
                {
                    "id": choice_row["choice"].id,
                    "english": choice_row["english"],
                    "value": choice_row["value"],
                }
                for choice_row in choice_rows
            ],
        }
        _append_node(roots, stack, question_node)

    return _prune_empty_groups(roots)


def build_review_rows(xlsform, language, user=None, offset=0, limit=None):
    query = displayed_survey_items_query(xlsform)
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    items = query.all()
    choices_by_list = choice_items_by_list_name(xlsform)
    reviews = reviews_by_key(xlsform, language)
    edited_question_ids = edited_question_ids_for_reviews(items, choices_by_list, reviews, user)
    rows = []

    for serial, item in enumerate(items, start=offset + 1):
        choice_rows = []
        for choice in visible_choices_for_item(item, choices_by_list, language):
            choice_value = value_for_item(choice, language, reviews, "choices")
            choice_rows.append(
                {
                    "choice": choice,
                    "english": clean_html_for_display(choice.english_label or choice.name),
                    "english_text": clean_text_for_display(choice.english_label or choice.name),
                    "value": clean_text_for_display(choice_value),
                    "value_html": clean_html_for_display(choice_value),
                    "editor_html": str(sanitize_rich_html(choice_value)),
                }
            )
        value = value_for_item(item, language, reviews, "survey")
        supporting_fields = build_supporting_fields(item, language, reviews)
        translate_parts = [display_question_label(item)]
        translate_parts.extend(
            f'Option: {choice["english_text"]}'
            for choice in choice_rows
            if choice["english_text"]
        )
        translate_parts.extend(
            f'{field["label"]}: {field["english_text"]}'
            for field in supporting_fields
            if field["english_text"]
        )
        rows.append(
            {
                "serial": serial,
                "question": item,
                "english": clean_html_for_display(_question_label_source(item)),
                "english_text": display_question_label(item),
                "translate_text": "\n\n".join(translate_parts),
                "value": clean_text_for_display(value),
                "value_html": clean_html_for_display(value),
                "editor_html": str(sanitize_rich_html(value)),
                "type_label": "Note" if (item.type or "").split(maxsplit=1)[0] == "note" else None,
                "control_type": choice_control_type(item),
                "is_edited": item.id in edited_question_ids,
                "choices": choice_rows,
                "modal_choices": [
                    {
                        "id": row["choice"].id,
                        "english": row["english_text"],
                        "english_html": str(row["english"]),
                        "value": row["editor_html"],
                    }
                    for row in choice_rows
                ],
                "supporting_fields": supporting_fields,
                "english_messages": [
                    {"label": field["label"], "value_html": field["english_html"]}
                    for field in supporting_fields
                ],
                "local_messages": [
                    {"label": field["label"], "value_html": field["value_html"], "field_name": field["field_name"]}
                    for field in supporting_fields
                ],
            }
        )
    return rows


def build_supporting_fields(item, language, reviews):
    fields = []
    raw_row_data = item.raw_row_data or {}
    for field_name, label in SUPPORTING_FIELDS.items():
        english_value = raw_row_data.get(find_localized_header(raw_row_data, field_name, ENGLISH_LABEL_HEADER))
        target_header = find_localized_header(raw_row_data, field_name, language.excel_header)
        review = reviews.get(("survey", item.row_number, field_name))
        if english_value is None and raw_row_data.get(target_header) is None and review is None:
            continue
        value = value_for_item(item, language, reviews, "survey", field_name)
        fields.append(
            {
                "field_name": field_name,
                "label": label,
                "english_text": clean_text_for_display(english_value),
                "english_html": clean_html_for_display(english_value),
                "value_html": clean_html_for_display(value),
                "editor_html": str(sanitize_rich_html(value)),
            }
        )
    return fields


def supporting_messages(raw_row_data, language_marker, language_code=None):
    markers = {language_marker.casefold()}
    if language_code:
        markers.add(f"({language_code.casefold()})")
    messages = []
    labels = {
        "hint": "Hint",
        "constraint_message": "Validation",
        "required_message": "Required",
        "guidance_hint": "Guidance",
    }
    for header, value in raw_row_data.items():
        if not value:
            continue
        normalized = header.casefold().replace(" ", "_")
        field = next((key for key in labels if normalized.startswith(key)), None)
        if field is None:
            continue
        if "::" in header and not any(marker in header.casefold() for marker in markers):
            continue
        messages.append({"label": labels[field], "value": clean_text_for_display(value)})
    return messages


def reviewable_count(xlsform):
    if xlsform is None:
        return 0
    return displayed_survey_items_query(xlsform).count()


def choice_items_by_list_name(xlsform):
    choices = ChoiceItem.query.filter_by(xlsform_id=xlsform.id).order_by(ChoiceItem.row_number).all()
    grouped = {}
    for choice in choices:
        grouped.setdefault(choice.list_name, []).append(choice)
    return grouped


def reviews_by_key(xlsform, language):
    reviews = TranslationReview.query.filter_by(
        xlsform_id=xlsform.id,
        language_id=language.id,
    ).all()
    return {(review.sheet_name, review.row_number, review.field_name): review for review in reviews}


def edited_question_ids_for_reviews(displayed_items, choices_by_list, reviews, user=None):
    survey_parent_by_row = {item.row_number: item.id for item in displayed_items}
    choice_parent_by_row = {}
    for item in displayed_items:
        for choice in choices_by_list.get(item.list_name, []):
            choice_parent_by_row.setdefault(choice.row_number, set()).add(item.id)

    edited_question_ids = set()
    for (sheet_name, row_number, _field_name), review in reviews.items():
        if not review_is_changed(review):
            continue
        if user is not None and review.edited_by != user.id:
            continue
        if sheet_name == "survey" and row_number in survey_parent_by_row:
            edited_question_ids.add(survey_parent_by_row[row_number])
        elif sheet_name == "choices" and row_number in choice_parent_by_row:
            edited_question_ids.update(choice_parent_by_row[row_number])
    return edited_question_ids


def review_is_changed(review):
    return sanitize_rich_html(review.edited_translation or "") != sanitize_rich_html(review.extracted_translation or "")


def value_for_item(item, language, reviews, sheet_name, field_name="label"):
    review = reviews.get((sheet_name, item.row_number, field_name))
    if review is not None and review.edited_translation is not None:
        return review.edited_translation
    raw_row_data = item.raw_row_data or {}
    english_value = (
        item.english_label
        if field_name == "label"
        else raw_row_data.get(find_localized_header(raw_row_data, field_name, ENGLISH_LABEL_HEADER))
    )
    target_header = find_localized_header(raw_row_data, field_name, language.excel_header)
    parsed = parse_translation_cell(english_value, (item.raw_row_data or {}).get(target_header))
    return parsed.extracted_translation or ""


def save_complete_form(user, xlsform, language, form_data):
    assignment = get_or_create_form_assignment(user, xlsform, language)
    survey_items = displayed_survey_items_query(xlsform).all()
    choices_by_list = choice_items_by_list_name(xlsform)
    reviews = reviews_by_key(xlsform, language)
    changed_count = 0

    for item in survey_items:
        if f"question_{item.id}" not in form_data:
            continue
        submitted = (form_data.get(f"question_{item.id}") or "").strip()
        review, changed = _save_item_value(
            user=user,
            xlsform=xlsform,
            language=language,
            sheet_name="survey",
            row_number=item.row_number,
            item_type=TranslationHistory.ITEM_TYPE_QUESTION,
            question_id=item.name,
            english_label=item.english_label,
            raw_row_data=item.raw_row_data or {},
            submitted=submitted,
            existing=reviews.get(("survey", item.row_number, "label")),
            field_name="label",
        )
        reviews[("survey", item.row_number, "label")] = review
        changed_count += int(changed)

        for choice in visible_choices_for_item(item, choices_by_list, language):
            if f"choice_{choice.id}" not in form_data:
                continue
            submitted_choice = (form_data.get(f"choice_{choice.id}") or "").strip()
            review, changed = _save_item_value(
                user=user,
                xlsform=xlsform,
                language=language,
                sheet_name="choices",
                row_number=choice.row_number,
                item_type=TranslationHistory.ITEM_TYPE_CHOICE,
                question_id=item.name,
                english_label=choice.english_label,
                raw_row_data=choice.raw_row_data or {},
                submitted=submitted_choice,
                existing=reviews.get(("choices", choice.row_number, "label")),
                field_name="label",
            )
            reviews[("choices", choice.row_number, "label")] = review
            changed_count += int(changed)

    assignment.mark_saved()
    return changed_count


def save_question_with_choices(
    user,
    xlsform,
    language,
    question_id,
    question_value,
    choice_values,
    supporting_values=None,
):
    assignment = get_or_create_form_assignment(user, xlsform, language)
    displayed_items = displayed_survey_items_query(xlsform).all()
    editable_questions = {item.id: item for item in displayed_items}
    item = editable_questions.get(question_id)
    if item is None:
        return None, 0, False, set(), set(), {}

    choices_by_list = choice_items_by_list_name(xlsform)
    choices_by_id = {
        choice.id: choice
        for choice in visible_choices_for_item(item, choices_by_list, language)
    }
    reviews = reviews_by_key(xlsform, language)
    changed_count = 0
    saved_choice_values = {}
    review, changed = _save_item_value(
        user=user,
        xlsform=xlsform,
        language=language,
        sheet_name="survey",
        row_number=item.row_number,
        item_type=TranslationHistory.ITEM_TYPE_QUESTION,
        question_id=item.name,
        english_label=item.english_label,
        raw_row_data=item.raw_row_data or {},
        submitted=(question_value or "").strip(),
        existing=reviews.get(("survey", item.row_number, "label")),
        field_name="label",
    )
    reviews[("survey", item.row_number, "label")] = review
    changed_count += int(changed)

    for field_name, submitted_value in (supporting_values or {}).items():
        if field_name not in SUPPORTING_FIELDS:
            continue
        raw_row_data = item.raw_row_data or {}
        english_value = raw_row_data.get(find_localized_header(raw_row_data, field_name, ENGLISH_LABEL_HEADER))
        if english_value is None:
            continue
        review, changed = _save_item_value(
            user=user,
            xlsform=xlsform,
            language=language,
            sheet_name="survey",
            row_number=item.row_number,
            field_name=field_name,
            item_type=SUPPORTING_FIELDS[field_name],
            question_id=item.name,
            english_label=english_value,
            raw_row_data=item.raw_row_data or {},
            submitted=(submitted_value or "").strip(),
            existing=reviews.get(("survey", item.row_number, field_name)),
        )
        reviews[("survey", item.row_number, field_name)] = review
        changed_count += int(changed)

    for choice_id, submitted_value in choice_values.items():
        choice = choices_by_id.get(choice_id)
        if choice is None:
            continue
        saved_choice_values[choice_id] = submitted_value
        review, changed = _save_item_value(
            user=user,
            xlsform=xlsform,
            language=language,
            sheet_name="choices",
            row_number=choice.row_number,
            item_type=TranslationHistory.ITEM_TYPE_CHOICE,
            question_id=item.name,
            english_label=choice.english_label,
            raw_row_data=choice.raw_row_data or {},
            submitted=(submitted_value or "").strip(),
            existing=reviews.get(("choices", choice.row_number, "label")),
            field_name="label",
        )
        reviews[("choices", choice.row_number, "label")] = review
        changed_count += int(changed)

    assignment.mark_saved()
    edited_question_ids = edited_question_ids_for_reviews(
        displayed_items,
        choices_by_list,
        reviews,
        user,
    )
    affected_question_ids = {item.id}
    saved_choice_ids = set(saved_choice_values)
    if saved_choice_ids:
        for candidate in displayed_items:
            if any(
                choice.id in saved_choice_ids
                for choice in visible_choices_for_item(candidate, choices_by_list, language)
            ):
                affected_question_ids.add(candidate.id)
    return (
        item,
        changed_count,
        item.id in edited_question_ids,
        affected_question_ids,
        edited_question_ids,
        saved_choice_values,
    )


def changed_reviews_for_assignment(assignment):
    reviews = TranslationReview.query.filter_by(
        xlsform_id=assignment.xlsform_id,
        language_id=assignment.language_id,
        edited_by=assignment.user_id,
    ).order_by(TranslationReview.sheet_name, TranslationReview.row_number).all()
    return [review for review in reviews if review_is_changed(review)]


def history_entries_for_assignment(assignment):
    histories = TranslationHistory.query.filter_by(
        user_id=assignment.user_id,
        xlsform_id=assignment.xlsform_id,
        language_id=assignment.language_id,
    ).order_by(TranslationHistory.created_at.desc(), TranslationHistory.id.desc()).all()
    return [
        {
            "question_id": history.question_id,
            "item_type": history.item_type,
            "english": clean_history_source(history),
            "old_value": clean_text_for_display(history.old_value),
            "new_value": clean_text_for_display(history.new_value),
            "created_at": history.created_at,
        }
        for history in histories
    ]


def choice_control_type(item):
    if not item.type:
        return None
    first_token = item.type.split(maxsplit=1)[0]
    if first_token == "select_one":
        return "radio"
    if first_token == "select_multiple":
        return "checkbox"
    return None


def visible_choices_for_item(item, choices_by_list, language):
    choices = choices_by_list.get(item.list_name, [])
    if not is_interview_language_question(item):
        return choices
    english_choice = next((choice for choice in choices if is_english_language_choice(choice)), None)
    if english_choice is None:
        # Keep the question usable if an unusual workbook labels English differently.
        return choices

    visible = [english_choice]
    assigned_choice = next(
        (
            choice
            for choice in choices
            if choice.id != english_choice.id and choice_matches_language(choice, language)
        ),
        None,
    )
    if assigned_choice is not None:
        visible.append(assigned_choice)
    return visible


def is_interview_language_question(item):
    if item.list_name != INTERVIEW_LANGUAGE_LIST_NAME:
        return False
    return clean_text_for_display(item.english_label).strip().casefold() == INTERVIEW_LANGUAGE_LABEL


def interview_language_choice_allowed(choice, language):
    return is_english_language_choice(choice) or choice_matches_language(choice, language)


def is_english_language_choice(choice):
    return canonical_language_name(choice.english_label) == ENGLISH_LANGUAGE_NAME


def choice_matches_language(choice, language):
    choice_name = canonical_language_name(choice.english_label)
    assigned_name = normalize_language_token(language.display_name) if language is not None else None
    return bool(choice_name and assigned_name and choice_name == assigned_name)


def normalize_language_token(value):
    if value is None:
        return None
    return clean_text_for_display(value).strip().casefold()


def canonical_language_name(value):
    """Return the source-language name from labels such as ``Hindi (हिन्दी)``."""
    cleaned = clean_text_for_display(value).strip()
    if not cleaned:
        return None
    return normalize_language_token(cleaned.split("(", 1)[0].strip())


def display_question_label(item):
    text = clean_text_for_display(item.english_label)
    if not _has_technical_id_prefix(item.name):
        return text
    id_prefix = re.compile(rf"^\s*{re.escape(item.name)}(?=\s|:|-|\.|\)|$)\s*[:\-.)]?\s*")
    return id_prefix.sub("", text, count=1)


def _question_label_source(item):
    source = item.english_label or ""
    if not _has_technical_id_prefix(item.name):
        return source
    id_prefix = re.compile(rf"^\s*(?:<[^>]+>\s*)*{re.escape(item.name)}(?=\s|:|-|\.|\)|$)\s*[:\-.)]?\s*", re.IGNORECASE)
    return id_prefix.sub("", source, count=1)


def _has_technical_id_prefix(name):
    """Only hide identifier-like names, not ordinary words that begin a label."""
    return bool(name and re.search(r"\d", name))


def clean_history_source(history):
    source = clean_text_for_display(history.english_value)
    if history.item_type != TranslationHistory.ITEM_TYPE_QUESTION:
        return source
    item = type("HistoryItem", (), {"name": history.question_id, "english_label": history.english_value})()
    return display_question_label(item)


def _save_item_value(
    user,
    xlsform,
    language,
    sheet_name,
    row_number,
    item_type,
    question_id,
    english_label,
    raw_row_data,
    submitted,
    existing,
    field_name="label",
):
    target_header = find_localized_header(raw_row_data, field_name, language.excel_header)
    parsed = parse_translation_cell(english_label, raw_row_data.get(target_header))
    baseline = parsed.extracted_translation or ""
    review = existing
    if review is None:
        review = TranslationReview(
            xlsform_id=xlsform.id,
            sheet_name=sheet_name,
            row_number=row_number,
            field_name=field_name,
            language_id=language.id,
            original_cell_value=parsed.original_cell_value,
            extracted_translation=parsed.extracted_translation,
            edited_translation=baseline,
            status=TranslationReview.STATUS_PENDING,
        )
        db.session.add(review)

    current = review.edited_translation if review.edited_translation is not None else baseline
    submitted = str(sanitize_rich_html(submitted))
    if sanitize_rich_html(submitted) == sanitize_rich_html(current):
        return review, False

    db.session.add(
        TranslationHistory(
            user_id=user.id,
            xlsform_id=xlsform.id,
            language_id=language.id,
            sheet_name=sheet_name,
            row_number=row_number,
            field_name=field_name,
            item_type=item_type,
            question_id=question_id,
            english_value=english_label,
            old_value=current,
            new_value=submitted,
        )
    )
    review.edited_translation = submitted
    review.edited_by = user.id
    review.mark_edited(user.id)
    return review, True


def is_reviewable_survey_item(item):
    if not item.english_label:
        return False
    if item.type in TECHNICAL_TYPES:
        return False
    return True


def _append_node(roots, stack, node):
    if stack:
        stack[-1]["children"].append(node)
    else:
        roots.append(node)


def _prune_empty_groups(nodes):
    pruned = []
    for node in nodes:
        if node["kind"] == "group":
            node["children"] = _prune_empty_groups(node["children"])
            if node["children"]:
                pruned.append(node)
        else:
            pruned.append(node)
    return pruned
