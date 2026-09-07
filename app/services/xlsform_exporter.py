from pathlib import Path

from openpyxl import load_workbook
from werkzeug.utils import secure_filename

from app.models import TranslationReview
from app.services.review_workflow import choice_items_by_list_name, displayed_survey_items_query
from app.services.xlsform_parser import reconstruct_translation_cell


class XLSFormExportError(Exception):
    """Raised when a reviewed XLSForm cannot be generated safely."""


def export_reviewed_xlsform(assignment, upload_folder, export_folder):
    source_path = (Path(upload_folder).expanduser().resolve() / assignment.xlsform.stored_filename).resolve()
    if not source_path.is_file():
        raise XLSFormExportError("The original uploaded XLSForm could not be found.")

    export_dir = Path(export_folder).expanduser().resolve()
    export_dir.mkdir(parents=True, exist_ok=True)

    workbook = load_workbook(source_path)
    allowed_keys = _exportable_review_keys(assignment)
    reviews = TranslationReview.query.filter_by(
        xlsform_id=assignment.xlsform_id,
        language_id=assignment.language_id,
        edited_by=assignment.user_id,
    ).all()
    reviews_by_sheet_row = {
        (review.sheet_name, review.row_number): review
        for review in reviews
        if (review.sheet_name, review.row_number) in allowed_keys
    }

    for sheet_name in ("survey", "choices"):
        sheet = _sheet_by_name(workbook, sheet_name)
        if sheet is None:
            raise XLSFormExportError(f"The original XLSForm is missing the {sheet_name} sheet.")
        target_column = _column_for_header(sheet, assignment.language.excel_header)
        english_column = _column_for_header(sheet, "label::English (en)")
        if target_column is None:
            raise XLSFormExportError(
                f"The target language column {assignment.language.excel_header!r} is missing from {sheet_name}."
            )
        for row_number in range(2, sheet.max_row + 1):
            review = reviews_by_sheet_row.get((sheet_name, row_number))
            if review is None:
                continue
            english_reference = sheet.cell(row=row_number, column=english_column).value if english_column else None
            sheet.cell(row=row_number, column=target_column).value = reconstruct_translation_cell(
                english_reference,
                review.original_cell_value,
                review.edited_translation,
            )

    export_filename = _export_filename(assignment)
    export_path = export_dir / export_filename
    workbook.save(export_path)
    if not export_path.is_file():
        raise XLSFormExportError("The reviewed XLSForm was not created.")
    return export_path


def _sheet_by_name(workbook, sheet_name):
    for actual_name in workbook.sheetnames:
        if actual_name.casefold() == sheet_name.casefold():
            return workbook[actual_name]
    return None


def _column_for_header(sheet, header):
    for cell in sheet[1]:
        if cell.value == header:
            return cell.column
    return None


def _exportable_review_keys(assignment):
    keys = set()
    choices_by_list = choice_items_by_list_name(assignment.xlsform)
    for item in displayed_survey_items_query(assignment.xlsform).all():
        keys.add(("survey", item.row_number))
        for choice in choices_by_list.get(item.list_name, []):
            keys.add(("choices", choice.row_number))
    return keys


def _export_filename(assignment):
    original_stem = Path(assignment.xlsform.original_filename).stem
    code = assignment.language.language_code or assignment.language.display_name
    filename = f"{original_stem}_{code}_{assignment.reviewer.username}_reviewed.xlsx"
    return secure_filename(filename)
