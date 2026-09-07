"""Add login attempt throttling.

Revision ID: 9c71e8b3a201
Revises: 8b6f1d2c9a4e
"""
from alembic import op
import sqlalchemy as sa


revision = "9c71e8b3a201"
down_revision = "8b6f1d2c9a4e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("client_address", sa.String(length=64), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("last_failed_at", sa.DateTime(), nullable=True),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier", "client_address", name="uq_login_attempt_identity_address"),
    )
    op.create_index(op.f("ix_login_attempts_identifier"), "login_attempts", ["identifier"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_login_attempts_identifier"), table_name="login_attempts")
    op.drop_table("login_attempts")
