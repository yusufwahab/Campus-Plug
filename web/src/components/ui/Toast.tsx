"use client";
import clsx from "clsx";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

type Tone = "success" | "error" | "info";
type ToastItem = { id: number; tone: Tone; message: string };

const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => undefined);

export function useToast() {
  return useContext(ToastContext);
}

const tones: Record<Tone, string> = {
  success: "bg-verified-bg text-verified-fg",
  error: "bg-danger-bg text-danger-fg",
  info: "bg-info-bg text-info-fg",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((message: string, tone: Tone = "success") => {
    const id = Date.now() + Math.random();
    setItems((cur) => [...cur, { id, tone, message }]);
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), 4000);
  }, []);

  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-24 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6">
        {items.map((t) => (
          <div key={t.id} role="status" className={clsx("pointer-events-auto rounded-full px-5 py-3 text-sm font-semibold shadow-lg", tones[t.tone])}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
