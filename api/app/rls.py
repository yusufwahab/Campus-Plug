"""Row-level security for Supabase Postgres.

The API is the only path to the data: it connects with a role that bypasses RLS. Turning RLS on for every table with
no policy for `anon` and `authenticated` means a leaked anon key (which ships in the browser) can read nothing.
The single exception is chat: Supabase Realtime needs to read `messages` as the signed-in user, so participants get a
read-only policy. Writes always go through the API.
"""

# Tables a signed-in user may read through Supabase directly (for Realtime). Value = SQL condition on the table's rows.
PARTICIPANT_READ = {
    "messages": (
        "EXISTS (SELECT 1 FROM conversations c JOIN users u ON u.auth_id = auth.uid()::text "
        "WHERE c.id = messages.conversation_id AND u.id IN (c.buyer_id, c.seller_user_id))"
    ),
}


def enable_statements(tables: list[str]) -> list[str]:
    out: list[str] = []
    for table in sorted(tables):
        if table == "alembic_version":
            continue
        out.append(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        out.append(f'REVOKE ALL ON "{table}" FROM anon, authenticated')
        condition = PARTICIPANT_READ.get(table)
        if condition:
            out.append(f'GRANT SELECT ON "{table}" TO authenticated')
            out.append(f'CREATE POLICY "{table}_participants_read" ON "{table}" FOR SELECT TO authenticated USING ({condition})')
    return out


def disable_statements(tables: list[str]) -> list[str]:
    out: list[str] = []
    for table in sorted(tables):
        if table == "alembic_version":
            continue
        if table in PARTICIPANT_READ:
            out.append(f'DROP POLICY IF EXISTS "{table}_participants_read" ON "{table}"')
        out.append(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    return out
