# API

Base path `/api/v1`. OpenAPI at `/openapi.json`, interactive docs at `/docs`. Every endpoint declares an auth dependency (public, current user, role, or add-on permission).

| Area | Endpoints |
|------|-----------|
| auth | POST /auth/signup, /auth/login, /auth/mfa/verify, /auth/phone/send, /auth/phone/verify, GET/PATCH/DELETE /me |
| catalogue | GET /campuses, /locations, /categories, /listings, /listings/{id}, /shops/{slug}, /search; POST/PATCH /listings |
| seller | POST /seller/start, GET /seller/overview, /seller/orders, /seller/earnings, PATCH /seller/settings, POST /seller/verification |
| verify/rep | GET /verify/queue, POST /verify/{id}/decision, GET /rep/sellers, /rep/requests, POST /rep/vouch |
| chat | GET/POST /conversations, GET/POST /conversations/{id}/messages, POST payment requests |
| requests | GET/POST /requests, POST /requests/{id}/respond |
| orders | POST /orders, /orders/{id}/pay, accept, status, confirm, cancel, dispute, review |
| webhooks | POST /webhooks/paystack |
| admin | /admin/* users, sellers, listings, orders, payments, payouts, promos, plans, reports, disputes, campuses, team, settings, activity-log, CSV exports |
| jobs | `python -m app.jobs.run_due` (cron, not HTTP) |

Detailed request/response shapes are in the generated OpenAPI schema; this file is updated per phase.
