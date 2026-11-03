import clsx from "clsx";
import type { HTMLAttributes } from "react";

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("rounded-card border border-line bg-white p-4 md:p-5", className)} {...rest} />;
}
