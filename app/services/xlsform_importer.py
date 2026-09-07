from dataclasses import dataclass

from sqlalchemy import and_

from app.extensions import db
from app.models import ChoiceItem, Language, SurveyItem, TranslationReview
from app.services.xlsform_parser import (
    ENGLISH_LABEL_HEADER,
    TRANSLATABLE_FIELDS,
    find_localized_header,
    parse_translation_cell,
)


@dataclass(frozen=True)
class XLSFormImportResult:
    survey_items: int
    reviewable_survey_items: int
    choice_items: int
    skipped_survey_items: int
    translation_reviews: int


def import_questionnaire_content(xlsform, parse_result, previous_xlsform=None):
    existing_reviews = _snapshot_reviews_for_import(xlsform, previous_xlsform)
    _clear_existing_imported_content(xlsform)
    languages = _languages_by_header(parse_result.languages)
    unique_survey_identities = _unique_identities(
        parse_result.survey_items,
        _survey_identity,
    )
    unique_choice_identities = _unique_identities(
        parse_result.choice_items,
        _choice_identity,
    )
    survey_count = 0
    reviewable_count = 0
    choice_count = 0
    review_count = 0

    for parsed_item in parse_result.survey_items:
        survey_item = SurveyItem(
            xlsform=xlsform,
            sheet_name="survey",
            row_number=parsed_item.row_number,
            type=parsed_item.type,
            name=parsed_item.name,
            list_name=parsed_item.list_name,
            english_label=parsed_item.english_label,
            raw_row_data=parsed_item.raw_row_data,
            relevant=parsed_item.relevant,
            appearance=parsed_item.appearance,
            is_group=parsed_item.is_group,
        )
        db.session.add(survey_item)
        survey_count += 1
        if _is_reviewable_survey_item(parsed_item):
            reviewable_count += 1
        review_count += _add_translation_reviews(
            xlsform=xlsform,
            sheet_name="survey",
            row_number=parsed_item.row_number,
            english_label=parsed_item.english_label,
            raw_row_data=parsed_item.raw_row_data,
            languages=languages,
            existing_reviews=existing_reviews,
            field_names=TRANSLATABLE_FIELDS,
            identity=_survey_identity(parsed_item),
            unique_identities=unique_survey_identities,
        )

    for parsed_item in parse_result.choice_items:
        choice_item = ChoiceItem(
            xlsform=xlsform,
            row_number=parsed_item.row_number,
            list_name=parsed_item.list_name,
            name=parsed_item.name,
            english_label=parsed_item.english_label,
            raw_row_data=parsed_item.raw_row_data,
        )
        db.session.add(choice_item)
        choice_count += 1
        review_count += _add_translation_reviews(
            xlsform=xlsform,
            sheet_name="choices",
            row_number=parsed_item.row_number,
            english_label=parsed_item.english_label,
            raw_row_data=parsed_item.raw_row_data,
            languages=languages,
            existing_reviews=existing_reviews,
            field_names=("label",),
            identity=_choice_identity(parsed_item),
            unique_identities=unique_choice_identities,
        )
    return XLSFormImportResult(
        survey_items=survey_count,
        reviewable_survey_items=reviewable_count,
        choice_items=choice_count,
        skipped_survey_items=survey_count - reviewable_count,
        translation_reviews=review_count,
    )


def ensure_detected_languages(detected_languages):
    headers = [language.excel_header for language in detected_languages]
    if not headers:
        return
    existing_headers = {
        language.excel_header
        for language in Language.query.filter(Language.excel_header.in_(headers)).all()
    }
    for detected_language in detected_languages:
        if detected_language.excel_header in existing_headers:
            continue
        db.session.add(
            Language(
                display_name=detected_language.display_name,
                language_code=detected_language.language_code,
                excel_header=detected_language.excel_header,
                is_active=True,
            )
        )


def _clear_existing_imported_content(xlsform):
    for review in TranslationReview.query.filter_by(xlsform_id=xlsform.id).all():
        db.session.delete(review)
    for choice_item in ChoiceItem.query.filter_by(xlsform_id=xlsform.id).all():
        db.session.delete(choice_item)
    for survey_item in SurveyItem.query.filter_by(xlsform_id=xlsform.id).all():
        db.session.delete(survey_item)
    db.session.flush()


def _snapshot_reviews_for_import(xlsform, previous_xlsform):
    """Capture continuity metadata using stable XLSForm identities.

    A newly-created upload has no imported rows yet, so its explicitly supplied
    predecessor is used. Re-imports already have rows belonging to the same
    upload and must snapshot those rows before they are cleared.
    """
    if _has_imported_rows(xlsform):
        return _snapshot_reviews(xlsform)
    if previous_xlsform is not None:
        return _snapshot_reviews(previous_xlsform)
    return {}


def _has_imported_rows(xlsform):
    if xlsform is None or xlsform.id is None:
        return False
    return any(
        query.first() is not None
        for query in (
            db.session.query(SurveyItem.id).filter_by(xlsform_id=xlsform.id),
            db.session.query(ChoiceItem.id).filter_by(xlsform_id=xlsform.id),
        )
    )


def _snapshot_reviews(xlsform):
    if xlsform is None or xlsform.id is None:
        return {}

    survey_items = SurveyItem.query.filter_by(xlsform_id=xlsform.id).all()
    choice_items = ChoiceItem.query.filter_by(xlsform_id=xlsform.id).all()
    survey_by_id = {
        item.id: item
        for item in survey_items
        if _survey_identity(item) is not None
    }
    choice_by_id = {
        item.id: item
        for item in choice_items
        if _choice_identity(item) is not None
    }
    unique_survey_ids = _unique_identities(survey_items, _survey_identity)
    unique_choice_ids = _unique_identities(choice_items, _choice_identity)
    snapshots = {}

    survey_review_rows = (
        db.session.query(TranslationReview, SurveyItem)
        .join(
            SurveyItem,
            and_(
                SurveyItem.xlsform_id == TranslationReview.xlsform_id,
                SurveyItem.row_number == TranslationReview.row_number,
                SurveyItem.sheet_name == TranslationReview.sheet_name,
            ),
        )
        .filter(
            TranslationReview.xlsform_id == xlsform.id,
            TranslationReview.sheet_name == "survey",
        )
        .all()
    )
    for review, item in survey_review_rows:
        identity = _survey_identity(item)
        if item.id not in survey_by_id or identity not in unique_survey_ids:
            continue
        snapshots[("survey", identity, review.field_name, review.language_id)] = _review_snapshot(
            review,
            _english_value(item, review.field_name),
        )

    choice_review_rows = (
        db.session.query(TranslationReview, ChoiceItem)
        .join(
            ChoiceItem,
            and_(
                ChoiceItem.xlsform_id == TranslationReview.xlsform_id,
                ChoiceItem.row_number == TranslationReview.row_number,
            ),
        )
        .filter(
            TranslationReview.xlsform_id == xlsform.id,
            TranslationReview.sheet_name == "choices",
        )
        .all()
    )
    for review, item in choice_review_rows:
        identity = _choice_identity(item)
        if item.id not in choice_by_id or identity not in unique_choice_ids:
            continue
        snapshots[("choices", identity, review.field_name, review.language_id)] = _review_snapshot(
            review,
            _english_value(item, review.field_name),
        )
    return snapshots


def _review_snapshot(review, source_value):
    return {
        "source_value": source_value,
        "extracted_translation": review.extracted_translation,
        "edited_translation": review.edited_translation,
        "edited_by": review.edited_by,
        "edited_at": review.edited_at,
        "reviewed_at": review.reviewed_at,
        "status": review.status,
    }


def _unique_identities(items, identity_fn):
    identities = {}
    duplicates = set()
    for item in items:
        identity = identity_fn(item)
        if identity is None:
            continue
        if identity in identities:
            duplicates.add(identity)
        else:
            identities[identity] = item
    return set(identities) - duplicates


def _survey_identity(item):
    item_type = (getattr(item, "type", None) or "").strip().casefold()
    if item_type in {"end_group", "end group", "end_repeat", "end repeat"}:
        return None
    return _identity_part(getattr(item, "name", None))


def _choice_identity(item):
    list_name = _identity_part(getattr(item, "list_name", None))
    name = _identity_part(getattr(item, "name", None))
    if list_name is None or name is None:
        return None
    return (list_name, name)


def _identity_part(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _english_value(item, field_name):
    if field_name == "label":
        return item.english_label
    raw_row_data = item.raw_row_data or {}
    english_header = find_localized_header(raw_row_data, field_name, ENGLISH_LABEL_HEADER)
    return raw_row_data.get(english_header)


def _languages_by_header(detected_languages):
    headers = [language.excel_header for language in detected_languages]
    if not headers:
        return {}
    return {
        language.excel_header: language
        for language in Language.query.filter(Language.excel_header.in_(headers)).all()
    }


def _add_translation_reviews(
    xlsform,
    sheet_name,
    row_number,
    english_label,
    raw_row_data,
    languages,
    existing_reviews,
    field_names,
    identity,
    unique_identities,
):
    count = 0
    for excel_header, language in languages.items():
        for field_name in field_names:
            english_field_header = find_localized_header(raw_row_data, field_name, ENGLISH_LABEL_HEADER)
            english_value = english_label if field_name == "label" else raw_row_data.get(english_field_header)
            target_header = find_localized_header(raw_row_data, field_name, excel_header)
            original_value = raw_row_data.get(target_header)
            if english_value is None and original_value is None:
                continue
            parsed_translation = parse_translation_cell(english_value, original_value)
            existing = {}
            if identity in unique_identities:
                existing = existing_reviews.get(
                    (sheet_name, identity, field_name, language.id),
                    {},
                )
            restored = _restored_review_fields(
                existing,
                extracted_translation=parsed_translation.extracted_translation,
                source_value=english_value,
            )
            db.session.add(
                TranslationReview(
                    xlsform=xlsform,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field_name=field_name,
                    language_id=language.id,
                    original_cell_value=parsed_translation.original_cell_value,
                    extracted_translation=parsed_translation.extracted_translation,
                    edited_translation=restored["edited_translation"],
                    edited_by=restored["edited_by"],
                    edited_at=restored["edited_at"],
                    reviewed_at=restored["reviewed_at"],
                    status=restored["status"],
                )
            )
            count += 1
    return count


def _restored_review_fields(existing, extracted_translation, source_value):
    if not existing or not _review_was_touched(existing):
        return {
            "edited_translation": extracted_translation,
            "edited_by": None,
            "edited_at": None,
            "reviewed_at": None,
            "status": TranslationReview.STATUS_PENDING,
        }

    source_changed = existing.get("source_value") != source_value
    return {
        "edited_translation": existing.get("edited_translation"),
        "edited_by": existing.get("edited_by"),
        "edited_at": existing.get("edited_at"),
        "reviewed_at": None if source_changed else existing.get("reviewed_at"),
        "status": (
            TranslationReview.STATUS_PENDING
            if source_changed
            else existing.get("status") or TranslationReview.STATUS_PENDING
        ),
    }


def _review_was_touched(review):
    return (
        _translation_values_differ(
            review.get("edited_translation"),
            review.get("extracted_translation"),
        )
        or review.get("edited_by") is not None
        or review.get("edited_at") is not None
        or review.get("reviewed_at") is not None
        or review.get("status") not in (None, TranslationReview.STATUS_PENDING)
    )


def _translation_values_differ(first, second):
    return (first or "").strip() != (second or "").strip()


def _is_reviewable_survey_item(parsed_item):
    if not parsed_item.english_label:
        return False
    if parsed_item.type in {"begin_group", "begin repeat", "end_group", "end repeat"}:
        return False
    return True
