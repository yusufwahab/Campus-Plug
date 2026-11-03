"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

type InstallEvent = Event & { prompt: () => Promise<void> };

/** Offers the PWA install prompt where the browser supports it (Android/desktop Chrome). */
export function InstallPrompt() {
  const [event, setEvent] = useState<InstallEvent | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setEvent(e as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  if (!event) return null;
  return (
    <div className="fixed inset-x-4 bottom-20 z-40 flex items-center justify-between gap-3 rounded-card bg-ink p-4 text-white md:bottom-6 md:left-auto md:max-w-sm">
      <p className="text-sm font-semibold">Install Campus Plug on your phone</p>
      <div className="flex gap-2">
        <Button variant="tertiary" className="border-white text-white hover:bg-white/10" onClick={() => setEvent(null)}>
          Later
        </Button>
        <Button
          onClick={async () => {
            await event.prompt();
            setEvent(null);
          }}
        >
          Install
        </Button>
      </div>
    </div>
  );
}
