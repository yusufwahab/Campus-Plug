"""row level security (PostgreSQL / Supabase only; a no-op elsewhere)

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

from app.rls import disable_statements, enable_statements

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _tables() -> list[str]:
    return sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # Local Postgres without Supabase has no anon/authenticated roles; create them so the statements still apply.
    for role in ("anon", "authenticated"):
        op.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN CREATE ROLE {role} NOLOGIN; END IF; END $$")
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'auth' AND p.proname = 'uid') THEN "
        "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $f$ SELECT NULL::uuid $f$; END IF; END $$"
    )
    for statement in enable_statements(_tables()):
        op.execute(statement)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for statement in disable_statements(_tables()):
        op.execute(statement)
