import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";

/** Shared body for the branded 404, 500, offline and access-denied pages. */
export function StatusPage({ code, title, body, actions }: { code: string; title: string; body: string; actions?: ReactNode }) {
  return (
    <main id="main" className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-6 text-center">
      <Logo />
      <p className="mt-10 font-heading text-6xl font-extrabold text-forest">{code}</p>
      <h1 className="mt-2 text-2xl font-bold">{title}</h1>
      <p className="mt-2 text-muted">{body}</p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">{actions ?? <Button href="/">Back to marketplace</Button>}</div>
    </main>
  );
}
