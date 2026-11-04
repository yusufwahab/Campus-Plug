import { api } from "./api";

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/** Asks permission and registers this browser for web push. Reports why when it cannot (no keys, blocked, unsupported). */
export async function enablePush(): Promise<{ ok: boolean; message: string }> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return { ok: false, message: "This browser does not support push notifications." };
  const { key } = await api<{ key: string }>("/push/public-key");
  if (!key) return { ok: false, message: "Push is not set up on this server yet." };
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { ok: false, message: "Notifications are blocked in your browser settings." };
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) });
  const json = subscription.toJSON();
  await api("/push/subscribe", { method: "POST", body: { endpoint: json.endpoint, p256dh: json.keys?.p256dh, auth: json.keys?.auth } });
  return { ok: true, message: "Push notifications are on." };
}
