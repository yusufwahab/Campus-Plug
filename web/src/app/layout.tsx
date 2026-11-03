import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Providers } from "./providers";
import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: { default: "Campus Plug - trusted products and services on your campus", template: "%s | Campus Plug" },
  description: "Discover students selling food, fashion, gadgets and services at UNILAG. Chat, pay safely and review.",
  applicationName: "Campus Plug",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Campus Plug", statusBarStyle: "default" },
  openGraph: { siteName: "Campus Plug", type: "website", locale: "en_NG" },
};

export const viewport: Viewport = { themeColor: "#163A2C", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-full focus:bg-lime focus:px-4 focus:py-2">
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
