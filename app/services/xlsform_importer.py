from dataclasses import dataclass

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


def import_questionnaire_content(xlsform, parse_result):
    existing_reviews = _clear_existing_imported_content(xlsform)
    languages = _languages_by_header(parse_result.languages)
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
    existing_reviews = {
        (review.sheet_name, review.row_number, review.field_name, review.language_id): {
            "edited_translation": review.edited_translation,
            "edited_by": review.edited_by,
            "edited_at": review.edited_at,
            "reviewed_at": review.reviewed_at,
            "status": review.status,
        }
        for review in TranslationReview.query.filter_by(xlsform_id=xlsform.id).all()
    }
    for review in TranslationReview.query.filter_by(xlsform_id=xlsform.id).all():
        db.session.delete(review)
    for choice_item in ChoiceItem.query.filter_by(xlsform_id=xlsform.id).all():
        db.session.delete(choice_item)
    for survey_item in SurveyItem.query.filter_by(xlsform_id=xlsform.id).all():
        db.session.delete(survey_item)
    db.session.flush()
    return existing_reviews


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
            existing = existing_reviews.get((sheet_name, row_number, field_name, language.id), {})
            edited_translation = existing.get("edited_translation")
            if edited_translation is None:
                edited_translation = parsed_translation.extracted_translation
            db.session.add(
                TranslationReview(
                    xlsform=xlsform,
                    sheet_name=sheet_name,
                    row_number=row_number,
                    field_name=field_name,
                    language_id=language.id,
                    original_cell_value=parsed_translation.original_cell_value,
                    extracted_translation=parsed_translation.extracted_translation,
                    edited_translation=edited_translation,
                    edited_by=existing.get("edited_by"),
                    edited_at=existing.get("edited_at"),
                    reviewed_at=existing.get("reviewed_at"),
                    status=existing.get("status") or TranslationReview.STATUS_PENDING,
                )
            )
            count += 1
    return count


def _is_reviewable_survey_item(parsed_item):
    if not parsed_item.english_label:
        return False
    if parsed_item.type in {"begin_group", "begin repeat", "end_group", "end repeat"}:
        return False
    return True
