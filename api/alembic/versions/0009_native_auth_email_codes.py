"""native auth: email verification codes replace phone codes; drop the Supabase auth id

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

import app.db

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=100), nullable=False),
        sa.Column("expires_at", app.db.UTCDateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("email_codes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_email_codes_user_id"), ["user_id"], unique=False)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    # People who confirmed a phone before this change stay confirmed.
    op.execute("UPDATE users SET email_verified = phone_verified")
    op.execute("UPDATE shops SET trust_level = 'email_confirmed' WHERE trust_level = 'phone_confirmed'")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("auth_id")
    op.drop_table("phone_codes")


def downgrade() -> None:
    raise NotImplementedError("Forward only: write a new migration to change this.")
