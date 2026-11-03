Build Campus Plug: Full Product Prompt
You are the lead engineer, product designer and QA owner for Campus Plug. Build a complete, working, responsive production-grade product from an empty repository. Do not reuse the old Lovable build.

1. How you must work
   Autonomy
   Work through every phase in order without asking for approval between phases.
   After a phase passes its checks, commit it and start the next phase immediately.
   Do not stop to ask preference questions. Choose the safest reasonable option, record it in docs/DECISIONS.md, and continue.
   Do not call the work finished until every section of this prompt is implemented and the Definition of Done passes.
   If you run low on context, update docs/PROGRESS.md with exactly what is done and next, then continue from it.
   Choosing the safest option
   When something is unclear, prefer the option that:

Protects people's money, identity documents and private messages.
Can be reversed or changed later through Admin settings.
Follows this prompt and the provider's current official documentation.
Is the simplest option that fully meets the requirement.
Hard safety limits
These limits override the autonomy above:

Never use live payment keys, make a real charge, or send a real payout.
Never commit secrets. Keep .env files out of Git and provide complete .env.example files.
Never enter personal credentials or create external accounts on the owner's behalf.
Never force-push, rewrite shared history, or delete production data.
Never run tests or seed scripts against a live database or live payment account.
Never message real users or send bulk messages.
Never disable tests, security checks, row-level security or TLS to get something working.
Never claim something works unless you ran it. Report failures and skipped checks honestly.
When credentials or owner actions are missing
Do not stop the build.

Put each external service behind an adapter.
Provide a clearly labelled local test implementation that lets the complete user flow run.
Add a feature flag and the required environment variables.
Record the exact steps for the owner in docs/OWNER_ACTIONS.md.
The owner must handle these items, so list them there:

creating Supabase, Paystack or Flutterwave, Vercel, Render and messaging accounts
adding environment variables and live credentials
confirming with the payment provider and a legal or tax adviser that holding funds, commission and refunds are permitted as implemented, and reviewing the terms, privacy policy and seller rules
final production launch and switching payments to live mode 2. The product
Campus Plug connects students with trusted products and services on their campus. It launches at the University of Lagos (UNILAG) and can expand to other campuses from Admin settings.

Core loop: a buyer discovers a seller, chats, pays or arranges the deal, receives the order, confirms it and leaves a review. The platform automatically takes its commission on in-app payments.

Launch rules

All categories are available: Food, Fashion, Beauty, Gadgets, Services, Accessories, Academic and Others. Admin can edit them.
Multi-campus support is built in. Only UNILAG is enabled at launch.
Locations use a campus plus hall or general area, without maps. Seed these UNILAG locations: Madam Tinubu Hall (MTH), Makama Bida, Fagunwa, Eni-Njoku, Sodehinde, Femi Gbajabiamila, El-Kanemi, Saburi Biobaku, Kofo Ademola, Queen Amina, Honours, UNILAG Women Society (ULWS) Female Hostel, King Jaja, Mariere, Queen Moremi, On Campus and Off Campus. 3. Required stack
Frontend: Next.js (App Router), TypeScript, Tailwind CSS, TanStack Query, React Hook Form and Zod.
PWA: web app manifest, service worker via Serwist, install prompt, offline fallback page and web push.
Backend: Python, FastAPI, Pydantic, SQLAlchemy 2 and Alembic. All business logic lives here. Do not put business logic in Next.js API routes.
Database: Supabase PostgreSQL through its connection pooler, with row-level security enabled as a second layer of protection.
Login, files and live updates: Supabase Auth, Storage and Realtime.
Payments: Paystack test mode first, behind a provider adapter that can also support Flutterwave.
Scheduled work: database-backed jobs run by Render cron jobs. Do not require Redis.
Hosting: Next.js on Vercel and FastAPI on Render, using Render's native Python runtime.
Local development: must work on Windows without Docker. Use a Python virtual environment, Node.js and a hosted Supabase development project.
Repository: a monorepo with web/, api/ and docs/, plus GitHub Actions CI.
Use current stable versions and check official documentation for provider APIs. Generate the frontend API client from FastAPI's OpenAPI schema.

4. Roles and permissions
   There are exactly three account roles, and permissions are enforced by FastAPI and the database, not only hidden in the interface.

Role Access
Buyer Browse, chat, post requests, order, pay, review, report and dispute.
Seller Everything a buyer can do, plus a shop, listings, promotions, orders and earnings. One account can buy and sell.
Admin Full platform control. Every action is logged.
Admin can assign two limited add-on permissions to normal accounts:

Verifier: can review assigned seller verification submissions. Cannot approve themselves or see anything else in Admin.
Hall Rep: can onboard sellers, vouch for them and see their hall's request queue. Cannot see student IDs, approve sellers or remove listings.
Guests can browse and share public listings and shops, but must sign in to chat, order, post requests, report, save items or sell.

Model permissions so a Super Admin role can be added later. Support at least two Admins, and require two-step sign-in for Admin accounts.

5. Design system
   Use this exact visual direction for the whole product:

Colours: Ink #10251D, Forest #163A2C, Plug Lime #C9F26C, Ground #F4F6EF, White #FFFFFF, Line #DDE3D6, Muted #56675E.
Category tints: peach #FFD9C7, lilac #E3D8FF, sky #CFE6FF, butter #FFE99A, mint #CDEFD8.
Status colours (background/text): verified #E6F8BE/#163A2C, pending #FFEBC2/#6B4200, information #D9ECFF/#0F4C81, danger #FFE0D7/#A32A12.
Fonts: Bricolage Grotesque for headings, prices and shop names; DM Sans for everything else.
Shape: fully rounded buttons, 20px card corners, 14-16px input corners.
Primary buttons: Plug Lime with Ink text. Secondary buttons: Ink with white text. Tertiary buttons: transparent with an Ink outline.
Logo: a green rounded square with a simple plug icon.
Personality: confident, clean and student-friendly. Avoid gradients, emoji as icons and generic template layouts.
Build reusable design tokens and components first. Pages must use them instead of one-off styles.

6. Responsive rules
   Every page, navigation item, modal, table and form must work and look deliberately designed on:

Mode Widths Layout
Mobile 360-767px Single column, bottom navigation, sticky primary action, bottom-sheet modals
Tablet 768-1023px Two-column content where useful, navigation rail in dashboards, centred modals
Desktop 1024px and wider Top navigation on public pages, sidebar in dashboards, multi-column content, centred modals
Navigation

Public mobile: Home, Requests, Messages, Orders and Account.
Public desktop and tablet: logo, search, campus and location selector, Requests, Messages, Orders, notifications, Sell and account menu.
Seller mobile: Home, Listings, Messages, Orders and Earnings, with other items under More.
Seller desktop and tablet: Overview, Listings, Orders, Messages, Earnings, Promotions, Reviews, Verification, Shop Settings, and Back to Marketplace.
Admin mobile: menu drawer. Admin desktop and tablet: sidebar with every Admin section.
Component behaviour

Lists: 2 columns on mobile, 3 on tablet, 4-5 on desktop.
Listing page: stacked on mobile with sticky Message and Buy actions; gallery plus sticky purchase panel on desktop.
Chat: separate list and thread screens on mobile; two panes on tablet and desktop.
Admin tables: cards on mobile; tables with sticky headers, search, filters and pagination on larger screens.
Dashboards must never scroll horizontally except inside a labelled table container.
Touch targets are at least 44px, with visible keyboard focus. Text contrast meets WCAG AA. 7. Every page to build
Public
/ landing and marketplace home: hero, search, location selector, categories, Open Now, Near You, New Listings, Popular, "Plug Me" prompt and footer.
/search: results and filters for type, category, hall, price, condition, verified sellers, and open now.
/categories/[slug]: category browsing.
/listing/[id]: product or service details, gallery, seller trust details, reviews, Message, Buy or Book, Save, Share and Report.
/shop/[slug]: public shop with Products, Services and Reviews tabs and Share.
/how-it-works, /sell, /help, /contact, /terms, /privacy and /seller-rules.
Branded 404, 500, offline and access-denied pages.
Public listing and shop pages must render on the server with correct metadata, including Open Graph images, so WhatsApp link previews and search engines show the correct name, price and image.

Account and buyer
/login, /signup, /forgot-password, /reset-password and /verify-phone.
/onboarding: choose campus, location and interests.
/account: profile, security, notification preferences and account deletion.
/saved, /notifications, /requests, /requests/new, /requests/[id].
/messages and /messages/[id].
/checkout/[id] and /checkout/[id]/result.
/orders, /orders/[id], /orders/[id]/review and /orders/[id]/problem.
/reports to track reports made by the user.
Seller
/seller/start: create shop and accept seller rules.
/seller: overview with setup checklist, earnings, tasks, orders, messages and stats.
/seller/listings, /seller/listings/new and /seller/listings/[id]/edit.
/seller/orders and /seller/orders/[id].
/seller/messages and /seller/earnings.
/seller/promotions: seller buyer codes, applied Admin codes, boosts and premium plans.
/seller/reviews, /seller/analytics, /seller/verification and /seller/settings (shop details, payout details and holiday mode).
Hall Rep and Verifier
/rep: sellers onboarded, seller vouching and hall requests.
/verify: verification queue and review screen.
Admin
/admin: overview, alerts and revenue.
/admin/users, /admin/users/[id].
/admin/sellers and /admin/verification.
/admin/listings and /admin/categories.
/admin/orders and /admin/orders/[id].
/admin/payments, /admin/payouts and /admin/commission.
/admin/promos, /admin/plans and /admin/sponsored.
/admin/reports and /admin/disputes.
/admin/campuses for campuses and locations.
/admin/team for Admins, Verifiers and Hall Reps.
/admin/announcements, /admin/settings, /admin/activity-log and CSV exports. 8. Buttons, modals and interface states
Every button must perform a real action or navigate somewhere real. No dead links, placeholder buttons or "coming soon" features.

Every action must show: default, hover, focus, active, disabled, loading, success and error behaviour. Prevent double submission. Destructive and money-related actions require clear confirmation.

Every data screen must include: loading skeleton, empty state with a helpful next step, error state with retry, and offline message where relevant.

Modals must close with Esc and a visible close button, trap focus, return focus when closed, and keep unsaved form data safe. Build at least these:

Sign-in prompt, location selector, search filters, share, image viewer and report
Confirm delete, pause, cancel, decline, sign out and account deletion
Promo code creation, listing preview and boost purchase
Payment request, delivery choice and order confirmation
Review, dispute, response to dispute and refund decision
Verification approve, reject and request changes
Admin warning, suspension, ban, badge removal, permission change, commission change and announcement
Use toast messages for quick results, and inline messages for form errors.

9. Feature requirements
   Platform IDs
   Generate readable unique IDs: CP-P-48213 (product), CP-S-10762 (service), CP-SL-2045 (seller), CP-O-90317 (order), CP-D-1184 (dispute).

Admins can search by ID, and buyers see order IDs on receipts.

Seller journey and verification
Sign up and confirm phone number.
Create shop and accept seller rules.
See a checklist: add a listing, verify identity, add payout details, share shop.
List immediately with an "Unverified" label and an Admin-configurable listing limit. Unverified sellers cannot receive in-app payments.
Submit student ID, location and payout details.
A Verifier or Admin approves, rejects or requests changes with a reason.
Approval unlocks the badge, in-app payments and unlimited listings.
Changing payout details triggers another review before the next payout.
Trust levels: Phone Confirmed, Verified Student and Trusted Seller. Trusted Seller is earned automatically from confirmed deals and good ratings using Admin-configurable thresholds.

Protection rules

Nobody can verify themselves.
Identity documents use a private bucket, short-lived links and logged views.
High-value items above an Admin-set price, plus Admin-selected categories, require verification before listing.
Non-student sellers are disabled by default. Admin can enable a separate reviewed vendor type.
Public listings must never show exact room numbers, and the listing form warns sellers not to add them.
Listings
All listings: title, type, category, description, images, price or price range, negotiable option, campus, general location, status and platform ID.

Products: condition, quantity, variants, pickup or delivery, delivery fee, and pre-order flag.

Services: starting price or packages, availability, duration, service location, portfolio images, and optional booking deposit.

Statuses: Draft, Active, Paused, Sold Out, Expired and Removed.

Behaviour:

Sellers can publish in under one minute using a mobile-friendly form.
A payout preview shows the buyer price, commission and seller payout before publishing.
Images are compressed before upload and have an Admin-defined maximum count.
Admin sets the free listing period and renewal rules. Sellers get a one-tap "still available?" check.
Holiday mode pauses a seller's shop.
Discovery and "Plug Me"
Search products, services, sellers and platform IDs, with filters, sorting and recent searches.
Prioritise location, availability, verification, ratings and response speed. Label sponsored results clearly.
Buyers can post a "Plug Me" request with category, description, budget, location and deadline. Matching sellers get notified and can respond in chat. Hall Reps can see requests in their hall.
Record searches with no results, and offer "Ask campus for this".
Chat
Real-time one-to-one chat linked to a listing or order, with images, read receipts, block and report.
Sellers send a structured payment request with the agreed price in chat, and the buyer opens checkout from it.
Phone numbers stay hidden until payment or until both people agree to share.
Admin can open private chats only when they have been reported or are part of a dispute. Each view is logged.
Payments, commission and payouts
Money rules

Store amounts as integer kobo.
Admin sets a default commission rate. Seed it at 20%. Admin can override it by category, seller or plan, and rate changes apply only to new orders.
Commission is calculated on what the buyer pays for the item after seller discounts. It is not charged on delivery fees.
The platform absorbs the payment provider fee from its commission share by default, through an Admin setting.
Each order permanently saves its price, discounts, commission rate, commission amount, seller amount and fees.
Every money movement goes into an append-only ledger.
Worked examples your tests must prove

Case Buyer pays Platform Seller
₦10,000, no discount, 20% commission ₦10,000 ₦2,000 ₦8,000
10% seller discount, 20% commission ₦9,000 ₦1,800 ₦7,200
10% seller discount, commission reduced to 10% ₦9,000 ₦900 ₦8,100
Payment flow

Buyer pays through the provider checkout.
FastAPI verifies the signed webhook and the transaction before updating anything. Webhooks must be safe to receive twice.
Funds are recorded as held until the buyer confirms delivery or the confirmation window ends.
The seller share is released, the commission is recorded for the platform, and the payout runs through the provider adapter.
Check the provider's current documentation for how to support this. If holding funds cannot be supported safely in test mode, keep the same user flow through the adapter, add an Admin-controlled instant-split fallback, and record the limitation in docs/OWNER_ACTIONS.md.

Other rules

Cash or direct transfer deals are allowed, are marked "Not protected" and can be recorded by both parties.
A full refund returns the commission. Partial refunds reduce it proportionally.
Sellers see gross sales, discounts, commission, net earnings, held funds, processing payouts and paid payouts.
Buyers see the final price and receipt, but not the platform's commission.
Orders and disputes
Order stages: Pending Payment, Paid, Accepted, Preparing, Ready or Out for Delivery, Delivered, Confirmed, Paid Out, Cancelled, Refunded and Disputed.

Enforce allowed changes in the backend. Use these Admin-configurable defaults:

Seller acceptance window: 2 hours, then automatic cancellation and refund.
Buyer confirmation window: 48 hours after delivery, then automatic confirmation unless disputed.
Delivery is arranged by the seller, with pickup or seller delivery options.

Service orders support booking time, optional deposit, cancellation rules and no-show reporting.

Disputes: the buyer reports a problem, the payout pauses, the seller responds with evidence within a set time, and an Admin issues a full refund, partial refund or release. All steps are recorded and both parties are told the result.

Promotions and premium plans
Admin to seller: commission discount codes and premium plan discounts.
Seller to buyer: percentage or fixed discounts on chosen items or the whole shop.
Admin to buyer: platform-funded campaign codes where the seller still gets their normal payout.
All codes support expiry dates, usage limits, minimum spend and eligibility.
Allow one buyer code per order. Sellers cannot use their own codes. Flag suspicious price rises before discounts.
Admin creates premium plans, pricing, benefits and commission rates. Sellers can buy, renew and cancel plans.
Sellers can buy boosts. Admin can approve and manage sponsored placement.
Reviews and reports
Only completed orders can be reviewed. Sellers can reply once.
For off-platform contact, send a "Did you buy from this seller?" prompt after 24 hours. Mark reviews from those as "Unconfirmed deal", with a lower ranking weight.
Users can report listings, users, messages and reviews. Admin can hide content, warn, suspend, ban and record reasons.
Add a published banned-items list. Add extra review for pre-orders and paid digital courses.
Notifications
Build an event-driven notification system with in-app, web push and email channels, plus a WhatsApp or SMS adapter behind a feature flag.

Cover new messages, payment requests, orders, reminders, payouts, verification, reports, disputes, promotions, expiring listings and announcements. Users control optional notifications, but essential order and security messages stay on.

Admin settings
Admin must be able to change these without code: commission rules, fee handling, promo codes, plans, boosts, categories, campuses, locations, listing limits, renewal periods, time windows, trust thresholds, feature flags, banned items, announcements and policy text.

Every Admin action records who did it, when, what changed and why in an unchangeable activity log.

Analytics
Track: searches and empty searches, listing views, contacts, chats, requests and responses, orders, confirmed deals, reviews, repeat buyers, active sellers, reports, disputes, revenue and commission. Show them in Admin and relevant summaries in the seller dashboard, with date and campus filters and CSV export.

10. Technical quality
    Security: server-side validation everywhere; authorisation checks on every endpoint; row-level security on every exposed table; rate limits for login, chat, reports and payments; secure upload checks; webhook signature checks; dependency checks; safe logging without secrets or IDs.
    Performance: good performance on mid-range phones and weak networks, optimised images, pagination, database indexes and no blocking background work during requests.
    PWA: installable on Android and iPhone, cached app shell, offline page and clear retry behaviour. Payments and money actions always require a connection.
    Accessibility: semantic HTML, keyboard support, labelled inputs and WCAG AA contrast.
    SEO: server-rendered public pages, metadata, sitemap, robots file and structured data.
    Data: soft-delete user-generated content where records must be retained. Account deletion must be blocked while orders or disputes are open.
    Code quality: typed code, feature-based modules, formatting and linting, clear migrations and no dead code.
    Required tests

pytest: permissions, state changes, commission calculations, promo rules, webhooks, refunds, payouts and scheduled jobs.
Frontend unit and component tests with Vitest.
Playwright end-to-end tests at 390px, 768px and 1440px for every core journey.
Automated accessibility checks on key pages.
CI must run linting, type checks, tests, migration checks and production builds.
Seed data: one clearly fake data set for local and staging only, containing an Admin, Verifier, Hall Rep, buyers, verified and unverified sellers, listings in all categories, chats, orders in every stage, promos, plans, reports and disputes. Put test logins in docs/SEED_ACCOUNTS.md and never seed them in production.

11. Build phases
    Complete each phase, run its checks, fix failures, update docs/PROGRESS.md, commit it, then continue automatically.

Phase Build Must pass before moving on 0. Plan Requirements, screen list, data model, API plan, repo and CI Documents match this prompt and CI runs

1. Design system Tokens, components, layouts, navigation and PWA shell Components work at all three widths
2. Accounts and roles Login, phone step, onboarding, permissions and protected routes Each role is blocked from others' data
3. Marketplace Campuses, categories, shops, listings, images, search and public pages A seller publishes and a guest finds the listing and sees correct metadata
4. Verification and Admin Trust levels, Verifier and Hall Rep tools, moderation, Admin settings and activity log Full verification and moderation journeys pass
5. Chat and notifications Real-time chat, payment requests, "Plug Me" and notifications Buyer and seller journey works live in two sessions
6. Payments and orders Checkout, ledger, webhooks, order stages, payouts, refunds and disputes Worked examples and all paid, cancelled, refunded and disputed journeys pass in test mode
7. Promotions and growth Promo codes, plans, boosts, reviews, analytics, sharing and marketing pages Discounts and paid upgrades calculate correctly
8. Hardening Full responsive audit, accessibility, security, performance and PWA review No dead buttons, broken layouts or failed critical tests
9. Deployment readiness Vercel and Render configuration, staging setup, runbook and owner documents Production builds pass and setup steps have been tested as far as available credentials allow
10. Definition of Done
    The work is done only when:

Every page, navigation item, button and modal in this prompt works.
Mobile, tablet and desktop layouts are tested at 390px, 768px and 1440px, with no accidental horizontal scrolling.
Buyer, seller, Verifier, Hall Rep and Admin journeys pass end to end in automated tests.
A complete order works from discovery to chat, payment, delivery, confirmation, payout and review in test mode.
Commission, discounts, refunds, disputes and payouts match the rules and worked examples.
Admin can change settings without code, and those changes affect only new orders where required.
Permissions and private-data protections are tested.
All tests, linting, type checks, migrations and production builds pass, using the actual command output as evidence.
No placeholder content, unexplained TODO notes, dead links or fake features remain outside clearly labelled test adapters and seed data.
A new developer on Windows can run the app locally from the README without Docker. 13. Required documents and final report
Keep these up to date:

README.md: local setup, tests and deployment.
docs/PROGRESS.md: phase status and evidence.
docs/DECISIONS.md: every decision made without the owner, with reasons.
docs/OWNER_ACTIONS.md: everything only the owner can do, in order.
docs/API.md, docs/DATA_MODEL.md and docs/RUNBOOK.md.
docs/SEED_ACCOUNTS.md: test accounts only.
When finished, report:

What was built, phase by phase.
The exact commands you ran and their results.
Anything not fully verified, and why.
Any test adapters still active.
The owner actions required before going live, including live payment credentials and legal review.
Begin Phase 0 now and continue through Phase 9 without waiting for approval.
