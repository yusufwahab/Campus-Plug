import type { ReactNode } from "react";
import { Card } from "@/components/ui/Card";

export function AuthCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-md py-6 md:py-12">
      <Card className="p-6 md:p-8">
        <h1 className="text-2xl font-extrabold">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        <div className="mt-6">{children}</div>
      </Card>
    </div>
  );
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-input bg-danger-bg px-4 py-3 text-sm font-medium text-danger-fg">
      {message}
    </p>
  );
}
