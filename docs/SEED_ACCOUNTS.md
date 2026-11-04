# Seed accounts (local and staging ONLY, never production)

Created by `python -m app.seed_dev` (run from `api/`). The command refuses to run when `APP_ENV=production`.
All fake accounts use `@example.com` addresses and the shared password `Passw0rd!test`.

| Email | Role | Notes |
|-------|------|-------|
| admin1@example.com | admin | Two-step sign-in. TOTP secret `JBSWY3DPEHPK3PXP` (add it to any authenticator app, or use the `totp()` helper in `web/tests/e2e/helpers.ts`). |
| admin2@example.com | admin | Same secret. A second admin so two-person checks can be tried. |
| verifier@example.com | buyer + verifier permission | Can review identity submissions, cannot verify themself. |
| rep@example.com | buyer + hall rep permission | Can onboard sellers and vouch for them. |
| buyer1@example.com | buyer ("Tolu Buyer") | Phone confirmed. |
| buyer2@example.com | buyer ("Chidi Buyer") | |
| seller.verified@example.com | seller ("Kemi's Corner") | Verified, payout details present, has listings including "Meat pie box (6)". |
| seller.new@example.com | seller ("Femi Fresh Finds") | Not verified: in-app payment is off for this shop. |

Seed data also includes the reference data (UNILAG as the launch campus with halls and locations, and categories) and listings for the shops above.

## Test payment page
With `PAYMENT_PROVIDER=local` checkout opens `/checkout/local`, a clearly labelled test page. No real money moves.
