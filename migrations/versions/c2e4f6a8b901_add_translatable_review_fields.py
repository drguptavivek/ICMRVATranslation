"""Add field-level translation reviews.

Revision ID: c2e4f6a8b901
Revises: 9c71e8b3a201
"""

from alembic import op
import sqlalchemy as sa


revision = "c2e4f6a8b901"
down_revision = "9c71e8b3a201"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("translation_reviews") as batch_op:
        batch_op.add_column(sa.Column("field_name", sa.String(length=40), nullable=False, server_default="label"))
        batch_op.drop_constraint("uq_translation_review_row_language", type_="unique")
        batch_op.create_unique_constraint(
            "uq_translation_review_row_field_language",
            ["xlsform_id", "sheet_name", "row_number", "field_name", "language_id"],
        )
    with op.batch_alter_table("translation_history") as batch_op:
        batch_op.add_column(sa.Column("field_name", sa.String(length=40), nullable=False, server_default="label"))


def downgrade():
    with op.batch_alter_table("translation_history") as batch_op:
        batch_op.drop_column("field_name")
    op.execute("DELETE FROM translation_reviews WHERE field_name != 'label'")
    with op.batch_alter_table("translation_reviews") as batch_op:
        batch_op.drop_constraint("uq_translation_review_row_field_language", type_="unique")
        batch_op.create_unique_constraint(
            "uq_translation_review_row_language",
            ["xlsform_id", "sheet_name", "row_number", "language_id"],
        )
        batch_op.drop_column("field_name")
