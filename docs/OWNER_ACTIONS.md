# Owner actions (in order)

Nothing here blocks local development. Every external service runs behind an adapter with a labelled local test implementation.

1. **Supabase**: create a project (dev, later prod). Copy the pooler connection string, project URL, anon key, service key and JWT secret into `api/.env` and `web/.env.local`. Run `alembic upgrade head`. Create private bucket `identity-docs` and public bucket `listing-images`. Enable Realtime on `messages`. Then set `AUTH_PROVIDER=supabase`.
2. **Paystack** (or Flutterwave): create an account, copy the TEST secret key, set the webhook URL to `https://<render-host>/api/v1/webhooks/paystack`. Set `PAYMENT_PROVIDER=paystack`.
3. **Confirm with Paystack and a legal/tax adviser** that holding funds, taking commission and issuing refunds work as implemented. If not, enable the Admin "instant split" setting.
4. **Legal review** of Terms, Privacy and Seller Rules (starter text is editable in Admin > Settings).
5. **Vercel**: import `web/`, add env vars from `web/.env.example`.
6. **Render**: create services from `render.yaml` (web service + cron), add env vars from `api/.env.example`.
7. **Messaging**: email (SMTP/Resend), web-push VAPID keys (`npx web-push generate-vapid-keys`), optional SMS/WhatsApp provider.
8. **Create the first Admin** with `python -m app.cli create-admin` (never seeded in production) and enrol TOTP. Create a second Admin the same way.
9. **Go live** only after steps 1-8 pass on staging: switch to live Paystack keys.

## Known limitations
(filled in as phases complete)
