export type Block = { heading: string; body: string[] };

/** Starter copy for policy and marketing pages. Admin can replace policy text in Settings; legal review is an owner action. */
export const policies: Record<"terms" | "privacy" | "seller-rules", { title: string; intro: string; blocks: Block[] }> = {
  terms: {
    title: "Terms of use",
    intro: "These terms explain how Campus Plug works for buyers and sellers.",
    blocks: [
      { heading: "What Campus Plug is", body: ["Campus Plug connects students with products and services on their campus. Sellers are independent students, not employees or agents of Campus Plug."] },
      { heading: "In-app payments", body: ["When you pay inside the app, your payment is held until you confirm delivery or the confirmation window ends. Campus Plug then releases the seller's share and keeps a commission.", "Cash and direct transfers are allowed but are marked Not protected: Campus Plug cannot refund them."] },
      { heading: "Refunds and disputes", body: ["If something is wrong, report a problem from your order. Payout pauses while we review. An Admin may issue a full refund, a partial refund or release the funds to the seller."] },
      { heading: "Banned items", body: ["You may not list illegal items, weapons, drugs, counterfeit goods or anything on our banned items list. We may remove listings and suspend accounts that break these rules."] },
      { heading: "Your account", body: ["You are responsible for activity on your account. Keep your password private and never share one-time codes."] },
    ],
  },
  privacy: {
    title: "Privacy policy",
    intro: "How Campus Plug handles your information.",
    blocks: [
      { heading: "What we collect", body: ["Your name, email, phone number, campus and hall, and the activity needed to run the marketplace such as orders and messages. Sellers who verify also submit a student ID."] },
      { heading: "Your phone number", body: ["Your phone number stays hidden from other users until payment is made or both of you agree to share it."] },
      { heading: "Student ID documents", body: ["Identity documents are stored privately, shown only to reviewers through short-lived links, and every view is logged."] },
      { heading: "Private messages", body: ["Admins can open a private chat only when it has been reported or is part of a dispute. Every view is logged."] },
      { heading: "Deleting your account", body: ["You can delete your account from Account settings unless you have open orders or disputes. We keep records that the law or fraud prevention requires."] },
    ],
  },
  "seller-rules": {
    title: "Seller rules",
    intro: "Rules every seller accepts before opening a shop.",
    blocks: [
      { heading: "Be honest", body: ["Describe items accurately with real photos. Do not inflate a price before applying a discount."] },
      { heading: "Protect privacy", body: ["Never publish room numbers. Use your hall or general area only. Do not share a buyer's details."] },
      { heading: "Deliver what you promise", body: ["Accept or decline orders within the acceptance window. Orders you do not accept are cancelled and refunded automatically."] },
      { heading: "Verification", body: ["Unverified sellers can list a limited number of items and cannot receive in-app payments. Verify with your student ID to unlock payments and unlimited listings. High-value items and some categories need verification first."] },
      { heading: "Fees", body: ["Campus Plug charges a commission on the item price you receive through in-app payments, not on delivery fees. You see exactly what you will earn before you publish."] },
      { heading: "Banned items and conduct", body: ["No banned items. No harassment. Moving buyers off-platform to avoid protection is not allowed."] },
    ],
  },
};

export const steps = [
  { title: "Discover", body: "Search by item, hall or seller. Filter by price, condition, verified sellers and who is open now." },
  { title: "Chat", body: "Message the seller to agree the details. Your phone number stays private." },
  { title: "Pay safely", body: "Pay inside the app and your money is held until you confirm you got what you ordered." },
  { title: "Receive", body: "Collect from the seller or get it delivered to your hall." },
  { title: "Confirm and review", body: "Confirm delivery to release payment, then leave a review to help the next student." },
];

export const faqs = [
  { q: "How do I pay a seller?", a: "Open the chat, wait for the seller's payment request, then tap Pay. You pay through Paystack inside the app." },
  { q: "When does the seller get paid?", a: "After you confirm delivery, or automatically 48 hours after delivery if you do not raise a problem." },
  { q: "What if my order never arrives?", a: "Open the order and tap Report a problem. Payout pauses and an Admin reviews it." },
  { q: "What does Verified mean?", a: "The seller's student ID was checked by our team. Verified sellers can receive in-app payments." },
  { q: "Can I pay in cash?", a: "Yes, but cash and direct transfers are marked Not protected and cannot be refunded by Campus Plug." },
  { q: "How do I become a seller?", a: "Create an account, confirm your email, then open a shop from the Sell button. You can list in under a minute." },
  { q: "I can't find what I need.", a: "Post a Plug Me request. Matching sellers are notified and reply in chat." },
];
