"use client";
import { Button } from "./Button";

export function EmptyState({ title, body, action }: { title: string; body: string; action?: { label: string; href: string } }) {
  return (
    <div className="mx-auto max-w-sm rounded-card border border-dashed border-line bg-white p-8 text-center">
      <h3 className="text-lg font-bold">{title}</h3>
      <p className="mt-1 text-sm text-muted">{body}</p>
      {action && (
        <Button href={action.href} className="mt-4">
          {action.label}
        </Button>
      )}
    </div>
  );
}

export function ErrorState({ message = "Something went wrong.", onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="mx-auto max-w-sm rounded-card bg-danger-bg p-8 text-center text-danger-fg">
      <h3 className="text-lg font-bold">Could not load this</h3>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
