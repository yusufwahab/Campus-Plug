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

## Rehearse with real services on your own computer (before deploying)
Goal: run the real API against real Postgres, Brevo, Cloudinary and Paystack, from `localhost`, without anyone reading your keys.

**Use a separate staging database, Paystack TEST keys, and your own email address.** A rehearsal sends real emails to whatever address you sign up with, uploads real files to Cloudinary, and writes real rows to the database you point it at. Do not point it at the database your launch will use.

Run these in your own terminal, from `api/` (PowerShell). The first three lines only override settings for this one window; nothing is written to `.env`.
```
$env:APP_ENV = "staging"                 # real services, but without the production-only rules (those need real site URLs)
$env:WEB_URL = "http://localhost:3000"
$env:CORS_ORIGINS = "http://localhost:3000"

.venv\Scripts\python -m app.cli preflight            # checks the settings; prints no secret
.venv\Scripts\python -m app.cli preflight --online   # also makes one read-only call to each service
.venv\Scripts\alembic upgrade head                   # creates the tables in the database named in .env
.venv\Scripts\python -m app.cli create-admin --email you@example.com --name "Your Name"
.venv\Scripts\uvicorn app.main:app --port 8000
```
Then run the web app as usual (`npm run dev` in `web/`).

What the preflight prints is only names and OK / WARN / FAIL with short reasons (for example `[OK  ] PAYSTACK_SECRET_KEY  TEST key (no real money)`). It never prints a key, a password or the connection string, and it never prints a database error, because those can contain the connection string. The output is safe to paste into a support chat. A `LIVE key` warning means payments would move real money: switch to the `sk_test_` key for rehearsals.

- `python -m app.seed_dev` refuses to run on PostgreSQL (it creates fake accounts with a known password). Do not set `ALLOW_DEV_SEED=1` on a database you care about.
- To see how the real production rules treat your settings, read the "Production start-up rules" row of the preflight: it lists which production rules would still block a start. Over a local rehearsal the only expected one is the localhost URLs.
- Never paste `.env`, a screenshot of it, or a connection string into a chat, issue or commit. If a secret was ever shown anywhere, rotate it in the provider's dashboard.
