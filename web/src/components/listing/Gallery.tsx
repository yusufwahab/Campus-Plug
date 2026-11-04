"use client";
import clsx from "clsx";
import Image from "next/image";
import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { assetUrl } from "@/lib/api";

type Img = { id: number; url: string };

export function Gallery({ images, title, tint }: { images: Img[]; title: string; tint: string }) {
  const [index, setIndex] = useState(0);
  const [viewer, setViewer] = useState(false);

  if (!images.length) {
    return (
      <div className={clsx("grid aspect-square place-items-center rounded-card font-heading text-8xl font-extrabold text-ink/25", tint)} role="img" aria-label={`${title} (no photo yet)`}>
        {title.charAt(0).toUpperCase()}
      </div>
    );
  }
  const current = images[index];
  return (
    <div className="space-y-3">
      <button type="button" onClick={() => setViewer(true)} aria-label="Open image viewer" className="relative block aspect-square w-full overflow-hidden rounded-card bg-line">
        <Image src={assetUrl(current.url)!} alt={`${title}, photo ${index + 1} of ${images.length}`} fill unoptimized priority sizes="(min-width:1024px) 50vw, 100vw" className="object-cover" />
      </button>
      {images.length > 1 && (
        <ul className="flex gap-2 overflow-x-auto" aria-label="Photos">
          {images.map((img, i) => (
            <li key={img.id}>
              <button type="button" onClick={() => setIndex(i)} aria-label={`Show photo ${i + 1}`} aria-current={i === index} className={clsx("relative block size-16 overflow-hidden rounded-input border-2", i === index ? "border-ink" : "border-transparent")}>
                <Image src={assetUrl(img.url)!} alt="" fill unoptimized sizes="64px" className="object-cover" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <Modal open={viewer} title={title} onClose={() => setViewer(false)}>
        <div className="relative aspect-square w-full overflow-hidden rounded-card bg-line">
          <Image src={assetUrl(current.url)!} alt={title} fill unoptimized sizes="100vw" className="object-contain" />
        </div>
        {images.length > 1 && (
          <div className="mt-3 flex justify-between">
            <button type="button" className="min-h-11 rounded-full border-2 border-ink px-4 text-sm font-semibold" onClick={() => setIndex((index + images.length - 1) % images.length)}>
              Previous
            </button>
            <button type="button" className="min-h-11 rounded-full border-2 border-ink px-4 text-sm font-semibold" onClick={() => setIndex((index + 1) % images.length)}>
              Next
            </button>
          </div>
        )}
      </Modal>
    </div>
  );
}
