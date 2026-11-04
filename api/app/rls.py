"""Row-level security for the Postgres database (Supabase or any other Postgres).

The API is the only path to the data: it connects with an owner role that bypasses RLS. Turning RLS on for every table
with no policy, and revoking grants from Supabase's `anon` and `authenticated` roles, means nothing can be read or
written through Supabase's own auto-generated REST API even if its public key leaks.
"""


def enable_statements(tables: list[str]) -> list[str]:
    out: list[str] = []
    for table in sorted(tables):
        if table == "alembic_version":
            continue
        out.append(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        out.append(f'REVOKE ALL ON "{table}" FROM anon, authenticated')
    return out


def disable_statements(tables: list[str]) -> list[str]:
    return [f'ALTER TABLE "{t}" DISABLE ROW LEVEL SECURITY' for t in sorted(tables) if t != "alembic_version"]
