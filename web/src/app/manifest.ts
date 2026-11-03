import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Campus Plug",
    short_name: "Campus Plug",
    description: "Trusted products and services on your campus.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#F4F6EF",
    theme_color: "#163A2C",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
