import type { ReactNode } from "react";

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-extrabold md:text-3xl">{title}</h1>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function SearchBar({ value, onChange, label = "Search" }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <div className="mb-3">
      <label htmlFor="admin-search" className="sr-only">
        {label}
      </label>
      <input
        id="admin-search"
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={label}
        className="min-h-11 w-full rounded-full border border-line bg-white px-5 text-sm md:max-w-sm"
      />
    </div>
  );
}
