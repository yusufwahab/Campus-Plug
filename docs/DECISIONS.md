# Decisions made without the owner

Each entry: decision, reason, how to change it later.

| # | Decision | Reason | Reversible via |
|---|----------|--------|----------------|
| 1 | Old Lovable build moved to `_legacy_lovable/` (git-ignored), not deleted. | Prompt says not to reuse it; deleting is irreversible. | Delete the folder when happy. |
| 2 | Monorepo: `web/` (Next.js), `api/` (FastAPI), `docs/`. | Required by prompt. | n/a |
| 3 | API auth accepts Supabase JWTs in production, and a clearly labelled **local auth adapter** (`AUTH_PROVIDER=local`) that issues its own JWTs so the full flow runs without a Supabase project. | No Supabase account exists yet. | `AUTH_PROVIDER=supabase` |
| 4 | Automated tests run on SQLite via SQLAlchemy 2; production uses Supabase Postgres via the pooler. Models use portable types only. Row-level-security SQL ships as an Alembic migration that only runs on PostgreSQL. | Tests must never touch a live database; Windows without Docker. | n/a |
| 5 | Money is integer kobo. Percentages are basis points (20% = 2000). Commission = floor(item_paid * bps / 10000); seller share = item_paid - commission (+ delivery fee, which carries no commission). | Avoids float error; worked examples verified in tests. | Admin settings (rates). |
| 6 | Payments: `PaymentProvider` adapter with `paystack` (test keys, real HTTP, signature check) and `local` (deterministic fake). Default `local` until keys exist. Held funds are modelled in our own ledger; payouts go via the adapter. Admin flag `instant_split` is the fallback if the provider cannot safely hold funds. | Holding funds needs provider and legal confirmation (see OWNER_ACTIONS). | `PAYMENT_PROVIDER`, admin flag |
| 7 | Provider fee absorbed by platform out of its commission by default (`provider_fee_absorbed=true`). | Prompt default. | Admin setting. |
| 8 | Scheduled jobs: rows in `jobs` table, run by `python -m app.jobs.run_due` from a Render cron job. No Redis. | Prompt requirement. | n/a |
| 9 | Realtime chat: Supabase Realtime in production; the local adapter polls the API at a short interval so two sessions work live without Supabase. | No Supabase project yet. | `NEXT_PUBLIC_REALTIME=supabase` |
| 10 | Admin two-step sign-in: TOTP enforced by the API for admin roles. Local adapter implements TOTP itself; Supabase mode requires an `aal2` claim. | Prompt requirement. | n/a |
| 11 | Non-student vendors disabled by default (`allow_vendors=false`). | Prompt requirement. | Admin settings. |
| 12 | Roles: `buyer`, `seller`, `admin` plus reserved `super_admin` (treated as admin superset). Add-ons `verifier` and `hall_rep` live in `user_permissions`. | Prompt: model for future Super Admin. | n/a |
| 13 | Frontend API client is typed from FastAPI's OpenAPI schema via `openapi-typescript` and a thin fetch wrapper. | Prompt requirement. | n/a |
| 14 | TypeScript pinned to 5.x in `web/`. | openapi-typescript peer range excludes TS 7. | Bump when supported. |
