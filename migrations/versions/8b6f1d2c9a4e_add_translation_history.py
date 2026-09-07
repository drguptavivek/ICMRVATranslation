"""Add translation history

Revision ID: 8b6f1d2c9a4e
Revises: 4459c4d00b23
Create Date: 2026-09-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8b6f1d2c9a4e'
down_revision = '4459c4d00b23'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'translation_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('xlsform_id', sa.Integer(), nullable=False),
        sa.Column('language_id', sa.Integer(), nullable=False),
        sa.Column('sheet_name', sa.String(length=40), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('item_type', sa.String(length=40), nullable=False),
        sa.Column('question_id', sa.String(length=255), nullable=True),
        sa.Column('english_value', sa.Text(), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['language_id'], ['languages.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['xlsform_id'], ['xlsforms.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('translation_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_translation_history_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_translation_history_language_id'), ['language_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_translation_history_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_translation_history_xlsform_id'), ['xlsform_id'], unique=False)


def downgrade():
    with op.batch_alter_table('translation_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_translation_history_xlsform_id'))
        batch_op.drop_index(batch_op.f('ix_translation_history_user_id'))
        batch_op.drop_index(batch_op.f('ix_translation_history_language_id'))
        batch_op.drop_index(batch_op.f('ix_translation_history_created_at'))

    op.drop_table('translation_history')
