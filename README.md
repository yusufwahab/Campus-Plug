# Campus Plug

A campus marketplace for students: products and services, buyer-seller chat, protected in-app payments with held funds, seller verification, reviews, and an Admin back office.

- `web/`: Next.js (App Router, TypeScript, Tailwind v4, TanStack Query, installable PWA)
- `api/`: FastAPI, SQLAlchemy 2, Alembic, Pydantic
- `docs/`: PROGRESS, DECISIONS, OWNER_ACTIONS, API, DATA_MODEL, RUNBOOK, SEED_ACCOUNTS

Status and what is verified: [docs/PROGRESS.md](docs/PROGRESS.md). What you must do before launch: [docs/OWNER_ACTIONS.md](docs/OWNER_ACTIONS.md).

## Run it on Windows (no Docker)
Needs Python 3.12 and Node 22.

```
cd api
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env
.venv\Scripts\alembic upgrade head
.venv\Scripts\python -m app.seed_dev
.venv\Scripts\uvicorn app.main:app --port 8000
```
```
cd web
copy .env.example .env.local
npm install
npm run dev
```
Open http://localhost:3000. Sign in with the accounts in [docs/SEED_ACCOUNTS.md](docs/SEED_ACCOUNTS.md).

Nothing external is needed locally. Payments, email, SMS, push, storage and auth each run behind an adapter with a clearly labelled local test implementation, switched by environment variables (see the `.env.example` files). The local payment page says "Test mode: no real money".

## Checks
```
cd api && .venv\Scripts\ruff check . && .venv\Scripts\ruff format --check . && .venv\Scripts\mypy app && .venv\Scripts\pytest
cd web && npx tsc --noEmit && npm run lint && npm test && npm run build && npm run e2e
```
`npm run e2e` needs Playwright's Chromium (`npx playwright install chromium`) and takes a while: it builds the app, then runs each screen size (390, 768, 1440) against its own fresh database.

## Money in one paragraph
Everything is integer kobo. Commission is a percentage in basis points of what the buyer paid for the item (not delivery), frozen on each order when it is created. Paid orders sit in escrow until the buyer confirms (or auto-confirm after 48 hours), then the seller's payout is queued. Every movement is written to an append-only ledger whose legs sum to zero.
