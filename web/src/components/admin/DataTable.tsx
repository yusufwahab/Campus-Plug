"use client";
import clsx from "clsx";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";

export type Column<T> = { key: string; header: string; render: (row: T) => ReactNode; className?: string };

type Props<T> = {
  label: string;
  rows: T[] | undefined;
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  empty?: { title: string; body: string };
  page?: number;
  pageSize?: number;
  total?: number;
  onPage?: (page: number) => void;
  /** Mobile card title column key (defaults to the first column). */
  cardTitle?: string;
  actions?: (row: T) => ReactNode;
};

/**
 * Cards on mobile; a real table with sticky header on tablet and desktop.
 * The table scrolls sideways only inside its own labelled region, never the page.
 */
export function DataTable<T>({ label, rows, columns, rowKey, loading, error, onRetry, empty, page = 1, pageSize = 20, total, onPage, cardTitle, actions }: Props<T>) {
  if (loading) {
    return (
      <div role="status" aria-label="Loading" className="space-y-2">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-14" />
        ))}
      </div>
    );
  }
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (!rows?.length) return <EmptyState title={empty?.title ?? "Nothing here yet"} body={empty?.body ?? "Records appear here when they exist."} />;

  const lastPage = total ? Math.max(1, Math.ceil(total / pageSize)) : page + (rows.length === pageSize ? 1 : 0);
  const titleCol = columns.find((c) => c.key === cardTitle) ?? columns[0];

  return (
    <div className="space-y-3">
      <ul className="space-y-2 md:hidden" aria-label={`${label} (cards)`}>
        {rows.map((row) => (
          <li key={rowKey(row)}>
            <Card className="space-y-2">
              <div className="font-semibold">{titleCol.render(row)}</div>
              <dl className="space-y-1 text-sm">
                {columns
                  .filter((c) => c !== titleCol)
                  .map((c) => (
                    <div key={c.key} className="flex justify-between gap-3">
                      <dt className="shrink-0 text-muted">{c.header}</dt>
                      <dd className="min-w-0 break-words text-right">{c.render(row)}</dd>
                    </div>
                  ))}
              </dl>
              {actions && <div className="flex flex-wrap gap-2 pt-1">{actions(row)}</div>}
            </Card>
          </li>
        ))}
      </ul>

      <div role="region" aria-label={`${label} table`} tabIndex={0} className="hidden max-h-[70dvh] overflow-auto rounded-card border border-line bg-white md:block">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">{label}</caption>
          <thead className="sticky top-0 z-10 bg-ground">
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col" className={clsx("whitespace-nowrap px-4 py-3 font-semibold", c.className)}>
                  {c.header}
                </th>
              ))}
              {actions && (
                <th scope="col" className="px-4 py-3 font-semibold">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={rowKey(row)} className="border-t border-line">
                {columns.map((c) => (
                  <td key={c.key} className={clsx("px-4 py-3 align-middle", c.className)}>
                    {c.render(row)}
                  </td>
                ))}
                {actions && (
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">{actions(row)}</div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {onPage && (page > 1 || lastPage > page) && (
        <nav aria-label={`${label} pagination`} className="flex items-center justify-between gap-2">
          <Button variant="tertiary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
            Previous
          </Button>
          <span className="text-sm text-muted">
            Page {page}
            {total ? ` of ${lastPage}` : ""}
          </span>
          <Button variant="tertiary" disabled={page >= lastPage} onClick={() => onPage(page + 1)}>
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}
