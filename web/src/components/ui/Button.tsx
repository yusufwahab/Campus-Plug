import clsx from "clsx";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "tertiary" | "danger";

const base =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-sm font-semibold transition " +
  "active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100";

const variants: Record<Variant, string> = {
  primary: "bg-lime text-ink hover:bg-lime-dark",
  secondary: "bg-ink text-white hover:bg-forest",
  tertiary: "border-2 border-ink bg-transparent text-ink hover:bg-ink/5",
  danger: "bg-danger-fg text-white hover:opacity-90",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  loading?: boolean;
  href?: string;
  children: ReactNode;
};

export function Button({ variant = "primary", loading, href, className, children, disabled, type = "button", ...rest }: Props) {
  const cls = clsx(base, variants[variant], className);
  if (href) {
    return (
      <Link href={href} className={cls}>
        {children}
      </Link>
    );
  }
  return (
    <button type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading && <Spinner />}
      {children}
    </button>
  );
}
