# Data model

All money columns are integer kobo. Rates are basis points. Tables have `id`, `created_at`; user-content tables have `deleted_at` (soft delete).

## Identity
- **users**: auth_id, email, phone, phone_verified, full_name, role (buyer|seller|admin|super_admin), status (active|suspended|banned), campus_id, location_id, mfa_secret, mfa_enabled, deleted_at
- **user_permissions**: user_id, permission (verifier|hall_rep), hall_location_id, granted_by
- **shops**: public_id (CP-SL-n), user_id, slug, name, bio, campus_id, location_id, vendor_type, verification_status, trust_level, holiday_mode, payout details, payout_review_required, commission_override_bps, plan_id
- **verification_submissions**: shop_id, student_id_path, status, assigned_verifier_id, reviewer_id, reason
- **vouches**: hall_rep_id, shop_id

## Catalogue
- **campuses**, **locations** (campus_id, name, kind), **categories** (slug, name, tint, requires_verification, commission_override_bps)
- **listings**: public_id (CP-P-n / CP-S-n), shop_id, type, category_id, title, description, price_kobo, price_max_kobo, negotiable, campus_id, location_id, status, condition, quantity, variants, fulfilment, delivery_fee_kobo, preorder, service fields, expires_at
- **listing_images**, **saved_items**, **search_logs**

## Social
- **requests** (Plug Me) and **request_responses**
- **conversations**, **messages** (text|image|payment_request, read_at), **blocks**
- **notifications**, **notification_prefs**, **push_subscriptions**
- **reports**, **announcements**

## Commerce
- **orders**: public_id, buyer_id, shop_id, listing_id, status, quantity, unit price, discounts, item_paid, delivery_fee, buyer_total, commission_bps, commission, seller_amount, provider_fee, protected, fulfilment, booking_at, stage timestamps
- **order_events** (append-only), **payments**, **webhook_events** (idempotency), **ledger_entries** (append-only), **payouts**, **refunds**, **disputes**, **reviews**

## Growth / admin
- **promo_codes**, **promo_redemptions**, **plans**, **subscriptions**, **boosts**
- **settings**, **banned_items**, **policies**
- **activity_log** (append-only), **jobs**, **analytics_events**

Row-level security is enabled on every table by an Alembic migration (PostgreSQL only). The API uses a privileged role and enforces authorisation itself; RLS blocks direct anon/PostgREST access as a second layer, with owner-scoped read policies on messages, orders and notifications.
