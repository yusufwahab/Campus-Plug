import Link from "next/link";

export function LogoMark({ className = "size-9" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 40 40" role="img" aria-label="Campus Plug">
      <rect width="40" height="40" rx="11" fill="#163A2C" />
      <path d="M14 9v7M26 9v7" stroke="#C9F26C" strokeWidth="3" strokeLinecap="round" />
      <path d="M11 16h18v4a9 9 0 0 1-9 9 9 9 0 0 1-9-9z" fill="#C9F26C" />
      <path d="M20 29v4" stroke="#C9F26C" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex min-h-11 items-center gap-2" aria-label="Campus Plug home">
      <LogoMark />
      <span className="font-heading text-lg font-extrabold tracking-tight">Campus Plug</span>
    </Link>
  );
}
