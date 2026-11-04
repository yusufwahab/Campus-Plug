# Owner actions (in order)

Nothing here blocks local development. Every external service runs behind an adapter with a labelled local test implementation. Login, sign-up codes and password reset are built into the platform; Supabase is only the database.

1. **Database (PostgreSQL)**: create a Postgres database. Supabase works: create a project, then Connect > pooler connection string. Change the start to `postgresql+psycopg://` and end it with `?sslmode=require`. Use a **separate staging project** for testing and keep the production one for launch. Never point tests or `seed_dev` at production.
2. **Brevo (email)**: create an account, verify your sender address or domain, add the DKIM and SPF records Brevo shows you (otherwise mail goes to spam), then create an **API key**. Set `EMAIL_PROVIDER=brevo`, `BREVO_API_KEY`, `EMAIL_FROM` (the verified sender) and `EMAIL_FROM_NAME`. These send sign-up codes and password-reset links.
3. **Cloudinary (photos and documents)**: create an account (the free plan is fine to start). On the dashboard copy the **cloud name**, **API key** and **API secret** (Settings > API Keys). Set `STORAGE_PROVIDER=cloudinary`, `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` on Render. Listing and chat photos are public assets; ID documents and dispute evidence are uploaded as **private** assets and are only ever served through our API with a short-lived link. Check in Settings > Security that "Restricted media types" does not block images, and that strict transformations are not required for delivery (we add `f_auto,q_auto`).
4. **Paystack** (or Flutterwave): create an account, copy the TEST secret key, set the webhook URL to `https://<render-host>/api/v1/webhooks/paystack`. Set `PAYMENT_PROVIDER=paystack` and `PAYSTACK_SECRET_KEY`.
5. **Confirm with Paystack and a legal/tax adviser** that holding funds, taking commission and issuing refunds work as implemented. If not, enable the Admin "instant split" setting.
6. **Legal review** of Terms, Privacy and Seller Rules (starter text is editable in Admin > Settings).
7. **Render**: create a Blueprint from `render.yaml` (API web service + a cron job every 5 minutes). Render asks for each secret marked `sync: false`. The API refuses to start until the production checks in `app/config.py` pass (random `JWT_SECRET`, Postgres URL, Paystack and Brevo keys, real site URLs, dev codes off). If you create the service by hand, set `PYTHON_VERSION` to `3.12.9` (the version the tests ran on; Render otherwise picks the newest, 3.14), and set `WEB_URL` and `CORS_ORIGINS` to your real Vercel address, or the API stops at start-up with "CORS_ORIGINS and WEB_URL must be the real site, not localhost". `render.yaml` shares env vars between the two services with a YAML anchor; it parses locally but has not been tried on Render.
8. **Vercel**: import the repo with root directory `web/` (`web/vercel.json` is included) and add env vars from `web/.env.example`. Set `NEXT_PUBLIC_API_URL` to the Render API URL plus `/api/v1`. The Content-Security-Policy is built from that variable at build time.
9. **Web push (optional)**: `npx web-push generate-vapid-keys`; set the private key on Render and the public key on both Render and Vercel.
10. **Create the first Admin** with `python -m app.cli create-admin` (never seeded in production) and enrol the authenticator app on first sign-in. Create a second Admin the same way.
11. **Go live** only after a full run on staging (including a real sign-up code email and a Paystack TEST payment): switch to live Paystack keys.

## Known limitations (honest list)
- **Cloudinary is only mock-tested.** Uploads, signed private downloads and deletes are covered by tests against mocked HTTP and have never run against a real account. The signing follows Cloudinary's documented rule (sorted parameters, secret appended, SHA-1), but test a real upload, a real ID-document upload and an Admin viewing it on staging before launch. Without `STORAGE_PROVIDER=cloudinary` the API refuses to start in production, because the local disk is wiped on every Render deploy.
- **Deleted photos** are removed from Cloudinary on a best-effort basis. Photos of deleted listings, chats and accounts are not purged automatically.
- **Paystack and Brevo are only mock-tested.** Both adapters are covered by tests against mocked HTTP and have never talked to the real services. Test them on staging with a Paystack TEST key and a real mailbox.
- **Supabase has not been tried by the tests.** The whole test suite and every migration now pass on a real local PostgreSQL 16 (this found and fixed one Postgres-only bug), but not on Supabase itself or through its connection pooler. Prepared statements are switched off for the pooler.
- **Phone numbers are not confirmed.** Sign-up confirms the email address by code. The phone number is collected and only shared in chat by agreement or after payment. Phone confirmation needs an SMS provider.
- **Chat is near-live by polling** every few seconds, not push or WebSockets.
- **Web push** uses `pywebpush` behind an adapter. Only the local test sender has been exercised.
- **Bank codes** for payout recipients should be confirmed against the provider's current bank list.
- **SMS and WhatsApp** are off (`FEATURE_SMS=false`).
- **Migrations are forward only** from 0009. SQLite cannot downgrade foreign-key changes, and 0009 deliberately has no downgrade.
- **Legal text** (Terms, Privacy, Seller Rules) is starter wording and needs review.
