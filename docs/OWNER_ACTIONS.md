# Owner actions (in order)

Nothing here blocks local development. Every external service runs behind an adapter with a labelled local test implementation.

1. **Supabase**: create a project (dev, later prod). Copy the pooler connection string, project URL, anon key, service key and JWT secret into `api/.env` and `web/.env.local`. Run `alembic upgrade head`. Create private bucket `identity-docs` and public bucket `listing-images`. Enable Realtime on `messages`. Then set `AUTH_PROVIDER=supabase`.
2. **Paystack** (or Flutterwave): create an account, copy the TEST secret key, set the webhook URL to `https://<render-host>/api/v1/webhooks/paystack`. Set `PAYMENT_PROVIDER=paystack`.
3. **Confirm with Paystack and a legal/tax adviser** that holding funds, taking commission and issuing refunds work as implemented. If not, enable the Admin "instant split" setting.
4. **Legal review** of Terms, Privacy and Seller Rules (starter text is editable in Admin > Settings).
5. **Vercel**: import the repo with root directory `web/` (`web/vercel.json` is included) and add env vars from `web/.env.example`. Set `NEXT_PUBLIC_API_URL` to the Render API URL plus `/api/v1`. The Content-Security-Policy is built from that variable at build time.
6. **Render**: create a Blueprint from `render.yaml` (API web service + a cron job every 5 minutes). Render will ask for each secret marked `sync: false`. The API will refuse to start until the production checks in `app/config.py` pass (real Supabase, Postgres URL, Paystack key, no localhost URLs). `render.yaml` uses a YAML anchor to share env vars between the two services; it parses locally but has not been tried on Render.
7. **Messaging**: email (SMTP/Resend), web-push VAPID keys (`npx web-push generate-vapid-keys`), optional SMS/WhatsApp provider.
8. **Create the first Admin** with `python -m app.cli create-admin` (never seeded in production) and enrol TOTP. Create a second Admin the same way.
9. **Go live** only after steps 1-8 pass on staging: switch to live Paystack keys.

## Known limitations (honest list)
- **Paystack is only mock-tested.** The adapter signs and verifies webhooks (HMAC-SHA512) and is covered by 8 unit tests against mocked HTTP, but it has never talked to Paystack. Test it with a TEST key on staging before anything else.
- **Supabase is not verified.** Supabase JWT verification, the Postgres row-level-security migration and Storage are written but have never run against a real project. SQLite is what the automated tests use.
- **Chat is near-live by polling**, not Supabase Realtime. Enabling Realtime is documented but not implemented.
- **Web push** uses `pywebpush` behind an adapter. Only the local test sender has been exercised.
- **Bank codes** for payout recipients should be confirmed against the provider's current bank list.
- **Email and SMS** go to local test adapters (written to a log) until real providers are configured.
- **SQLite cannot downgrade** migrations that touch foreign keys. Production Postgres can; the test database only moves forward.
- **Legal text** (Terms, Privacy, Seller Rules) is starter wording and needs review.
