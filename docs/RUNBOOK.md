# Runbook

## Run locally (Windows, no Docker)
API (from `api/`, Python 3.12):
```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\alembic upgrade head
.venv\Scripts\python -m app.seed_dev
.venv\Scripts\uvicorn app.main:app --port 8000
```
Scheduled jobs (payout, auto-confirm, reminders, boost expiry, review prompts) run with `python -m app.jobs.run_due`. Locally run it in a loop, or by hand. In production a Render cron job runs it every few minutes.

Web (from `web/`, Node 22):
```
copy .env.example .env.local
npm install
npm run gen:api     # only after API changes
npm run dev
```

## Checks
- API: `ruff format --check . && ruff check . && mypy app && pytest` and `alembic check` against a migrated empty database.
- Web: `npx tsc --noEmit`, `npx eslint src tests`, `npm test`, `npm run build`.
- End to end: `npm run e2e` (builds, then runs Playwright at 390, 768 and 1440 wide, each against its own freshly seeded database on ports 8100 and 3100).

## Operations
- **A payment looks stuck**: find it in Admin > Payments. The buyer returning to the checkout result page re-verifies a pending payment with the provider. Webhooks are idempotent, so a replayed webhook is safe.
- **A payout is held**: Admin > Payouts shows the reason. Release or return it with a reason (logged).
- **Provider cannot hold funds**: turn on the `instant_split` setting in Admin > Settings. New orders then split at payment time.
- **Suspected abuse**: suspend the user (Admin > Users), hide the listing (Admin > Listings). Both need a reason and appear in the activity log.
- **Rollback a deploy**: redeploy the previous Render or Vercel release. Migrations are forward only in production; write a new migration to undo a schema change.
- **Backups**: rely on Supabase point-in-time backups. Test a restore on staging before launch.
