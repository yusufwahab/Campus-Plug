# Progress

Legend: [x] built and the checks listed ran and passed. "Not verified" items are listed honestly below and in OWNER_ACTIONS.md.

| Phase | Status | What it covers |
|-------|--------|----------------|
| 0 Plan | [x] | docs, CI workflow, repo layout |
| 1 Design system | [x] | tokens, UI components, layouts, PWA shell |
| 2 Accounts and roles | [x] | sign-up, login, email code confirmation, onboarding, password reset, admin two-step (TOTP), roles and add-on permissions |
| 3 Marketplace | [x] | listings, search, categories, shops, seller dashboard, saved items, reports |
| 4 Verification and Admin | [x] | identity verification, verifier and hall rep, trust levels, Admin back office with reasons and activity log |
| 5 Chat and notifications | [x] | chat with read receipts, phone sharing by agreement, Plug Me requests, in-app, push and email channels |
| 6 Payments and orders | [x] | orders, held funds, ledger, payouts, refunds, disputes, job runner |
| 7 Promotions and growth | [x] | seller and campaign promo codes, premium plans, boosts, reviews, analytics |
| 8 Hardening | [x] | row-level security migration, production startup checks, security headers, dependency audit, test isolation |
| 9 Deployment readiness | [x] | `render.yaml`, `web/vercel.json`, env examples, docs, runbook |

## Evidence (last full run)
| Check | Result |
|-------|--------|
| API `pytest` (SQLite, in-memory, environment pinned) | 207 passed |
| API `ruff check`, `ruff format --check`, `mypy app` | clean |
| `alembic upgrade head` then `alembic check` (SQLite, through migration 0009) | clean |
| Web `tsc --noEmit`, `eslint src tests` | clean |
| Web Vitest | 6 passed |
| Web `npm run build` | succeeded |
| Playwright, tablet (768) | 91 passed |
| Playwright, desktop (1440) | 90 passed, 1 skipped on purpose (mobile-only filters test) |
| Playwright, mobile (390) | 89 passed, 2 failed on the first pass (60 second stalls: a login and a payment button); the same tests passed on an immediate re-run (9 of 9) |
| `pip-audit` | no known vulnerabilities |
| `npm audit --audit-level=high` | passes (22 moderate findings remain, all in lint and build tooling) |

Each screen size runs against its own freshly seeded database. Every journey runs axe accessibility checks and a horizontal-scroll check.

## Not verified (never run against the real thing)
- PostgreSQL (all tests used SQLite), including the row-level-security migration
- Brevo email, Paystack payments, web push delivery
- Render and Vercel deploys (`render.yaml` and `vercel.json` only parse)
- Cloudinary uploads and private downloads (mock-tested only)

## Next
A staging deploy (see OWNER_ACTIONS.md).
