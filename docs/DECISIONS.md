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
| 15 | Server pages fetch the API uncached (`cache: "no-store"`); `htmlLimitedBots: /.*/` keeps SEO metadata in `<head>`. | Stale shop and category pages after edits; streamed metadata hid titles. | `web/src/lib/server-api.ts`, `next.config.ts` |
| 16 | Commission rate precedence: seller override > premium plan > category > default. The rate is frozen on each order when it is created. | Rate changes must never alter existing orders. | Admin > Commission, Plans |
| 17 | Append-only ledger; every movement's legs sum to zero (accounts: provider_clearing, escrow, seller_payable, platform_revenue, provider_fees, promo_cost). | Auditable money; reconciles against the provider. | n/a |
| 18 | Seller discount codes lower the price commission is charged on. Platform campaign codes are paid by Campus Plug (promo_cost), so the seller payout is unchanged. | Fair to sellers; clear cost to the platform. | Admin > Promo codes |
| 19 | Boosts need payment first, then Admin approval. Rejecting a paid boost refunds it. Boosted listings sort first and carry a Sponsored label. | Prompt: sponsored placement must be labelled and moderated. | Admin > Sponsored |
| 20 | Review weighting: confirmed-deal reviews count double, reviews from deals outside the app count once and are labelled "Unconfirmed deal". A chat with no order gets a "Did you buy?" prompt after 24h of quiet. | Discourages fake or retaliatory reviews while still hearing from cash deals. | `catalogue/service.py: rating_avg` |
| 21 | A promo is refused when the listing price was raised by more than `listing_price_spike_pct` in the past 7 days. | Stops "discount" on an inflated price. | Admin > Settings |
| 22 | E2E runs each viewport against its own fresh database, one after the other. | Journeys change shared state (stock, orders), which made later viewports fail for the wrong reasons. | `web/scripts/e2e.mjs` |
| 23 | Plan renewal marks the old subscription `expired` and creates a new row; changing plans marks the old one `cancelled`. Only one stays active. | Cancelling must end the plan, not one of several overlapping rows. | `promotions/purchases.py` |
| 24 | Row-level security is enabled on every table by migration 0008 (PostgreSQL only; a no-op on SQLite). `anon` and `authenticated` get no grants, so a leaked browser key reads nothing. The one exception is a read-only policy on `messages` for the two chat participants, which Supabase Realtime needs. | The API is the only data path; the anon key ships in the browser. | `app/rls.py`, migration 0008 |
| 25 | The API refuses to start in production with local auth, a placeholder secret, SQLite, the fake payment provider, dev OTP codes, a raised rate limit, or localhost URLs. | A misconfigured deploy should fail loudly, not run unsafely. | `app/config.py: production_problems` |
| 26 | `zod` is overridden to ^4.6.7 in `web/package.json`. | Serwist pinned 4.6.5, which has a high-severity advisory (memory exhaustion). Fixes all high findings; 22 moderate findings remain, all in lint and build tooling. | Remove the override once Serwist updates. |
| 27 | Web and API send security headers (CSP, nosniff, frame deny, referrer policy; HSTS in production). CSP allows inline scripts and styles because Next injects them. | Defence in depth. A stricter nonce-based CSP is possible later. | `web/next.config.ts`, `app/main.py` |
