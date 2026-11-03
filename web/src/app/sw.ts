/// <reference lib="webworker" />
import { defaultCache } from "@serwist/next/worker";
import type { PrecacheEntry, SerwistGlobalConfig } from "serwist";
import { Serwist } from "serwist";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}
declare const self: ServiceWorkerGlobalScope;

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching: defaultCache,
  fallbacks: { entries: [{ url: "/offline", matcher: ({ request }) => request.destination === "document" }] },
});

serwist.addEventListeners();

// Web push: show the notification payload sent by the API.
self.addEventListener("push", (event) => {
  const data = event.data?.json() as { title: string; body: string; url?: string } | undefined;
  if (!data) return;
  event.waitUntil(self.registration.showNotification(data.title, { body: data.body, data: { url: data.url ?? "/" }, icon: "/icons/icon-192.png" }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data as { url: string }).url;
  event.waitUntil(self.clients.openWindow(url));
});
