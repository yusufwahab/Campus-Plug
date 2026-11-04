"use client";
import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useState } from "react";
import type { InputHTMLAttributes } from "react";
import { Input } from "./Field";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label: string; error?: string; hint?: string };

/** A password field with a button to show or hide what was typed. Hidden by default. */
export const PasswordInput = forwardRef<HTMLInputElement, Props>(function PasswordInput(props, ref) {
  const [visible, setVisible] = useState(false);
  return (
    <Input
      {...props}
      ref={ref}
      type={visible ? "text" : "password"}
      trailing={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="grid size-11 place-items-center rounded-input text-muted hover:text-ink"
        >
          {visible ? <EyeOff className="size-5" aria-hidden="true" /> : <Eye className="size-5" aria-hidden="true" />}
        </button>
      }
    />
  );
});
