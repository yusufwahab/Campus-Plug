import { Bell, BarChart3, Boxes, ClipboardList, Flag, Gavel, Home, Inbox, LayoutDashboard, Megaphone, MessageCircle, Package, Percent, Receipt, Settings, ShieldCheck, ShoppingBag, Star, Store, Tag, UserCircle, Users, Wallet, ScrollText, MapPin, UsersRound, Banknote, Crown, FileDown } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon };

export const publicMobileNav: NavItem[] = [
  { href: "/", label: "Home", icon: Home },
  { href: "/requests", label: "Requests", icon: Inbox },
  { href: "/messages", label: "Messages", icon: MessageCircle },
  { href: "/orders", label: "Orders", icon: ShoppingBag },
  { href: "/account", label: "Account", icon: UserCircle },
];

export const publicDesktopLinks: NavItem[] = [
  { href: "/requests", label: "Requests", icon: Inbox },
  { href: "/messages", label: "Messages", icon: MessageCircle },
  { href: "/orders", label: "Orders", icon: ShoppingBag },
];

export const sellerNav: NavItem[] = [
  { href: "/seller", label: "Overview", icon: LayoutDashboard },
  { href: "/seller/listings", label: "Listings", icon: Package },
  { href: "/seller/orders", label: "Orders", icon: ClipboardList },
  { href: "/seller/messages", label: "Messages", icon: MessageCircle },
  { href: "/seller/earnings", label: "Earnings", icon: Wallet },
  { href: "/seller/promotions", label: "Promotions", icon: Percent },
  { href: "/seller/reviews", label: "Reviews", icon: Star },
  { href: "/seller/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/seller/verification", label: "Verification", icon: ShieldCheck },
  { href: "/seller/settings", label: "Shop Settings", icon: Settings },
  { href: "/", label: "Back to Marketplace", icon: Store },
];

/** Seller mobile bottom bar; everything else sits under More. */
export const sellerMobileHrefs = ["/seller", "/seller/listings", "/seller/messages", "/seller/orders", "/seller/earnings"];

export const adminNav: NavItem[] = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/sellers", label: "Sellers", icon: Store },
  { href: "/admin/verification", label: "Verification", icon: ShieldCheck },
  { href: "/admin/listings", label: "Listings", icon: Boxes },
  { href: "/admin/categories", label: "Categories", icon: Tag },
  { href: "/admin/orders", label: "Orders", icon: ClipboardList },
  { href: "/admin/payments", label: "Payments", icon: Receipt },
  { href: "/admin/payouts", label: "Payouts", icon: Banknote },
  { href: "/admin/commission", label: "Commission", icon: Percent },
  { href: "/admin/promos", label: "Promo codes", icon: Tag },
  { href: "/admin/plans", label: "Plans", icon: Crown },
  { href: "/admin/sponsored", label: "Sponsored", icon: Megaphone },
  { href: "/admin/reports", label: "Reports", icon: Flag },
  { href: "/admin/disputes", label: "Disputes", icon: Gavel },
  { href: "/admin/campuses", label: "Campuses", icon: MapPin },
  { href: "/admin/team", label: "Team", icon: UsersRound },
  { href: "/admin/announcements", label: "Announcements", icon: Bell },
  { href: "/admin/settings", label: "Settings", icon: Settings },
  { href: "/admin/activity-log", label: "Activity log", icon: ScrollText },
  { href: "/admin/exports", label: "Exports", icon: FileDown },
];
