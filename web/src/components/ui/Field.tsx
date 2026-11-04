import clsx from "clsx";
import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const control =
  "w-full min-h-11 rounded-input border border-line bg-white px-4 text-base text-ink placeholder:text-muted " +
  "focus-visible:border-ink disabled:opacity-50";

type Common = { label: string; error?: string; hint?: string };

function Wrap({ id, label, error, hint, children }: Common & { id: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-h`} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-e`} role="alert" className="text-xs font-medium text-danger-fg">
          {error}
        </p>
      )}
    </div>
  );
}

const describe = (id: string, error?: string, hint?: string) => (error ? `${id}-e` : hint ? `${id}-h` : undefined);

export const Input = forwardRef<HTMLInputElement, Common & InputHTMLAttributes<HTMLInputElement> & { trailing?: ReactNode }>(function Input(
  { label, error, hint, className, trailing, ...rest },
  ref,
) {
  const id = useId();
  return (
    <Wrap id={id} label={label} error={error} hint={hint}>
      <div className="relative">
        <input
          id={id}
          ref={ref}
          aria-invalid={!!error}
          aria-describedby={describe(id, error, hint)}
          className={clsx(control, error && "border-danger-fg", trailing && "pr-12", className)}
          {...rest}
        />
        {trailing && <div className="absolute inset-y-0 right-0 flex items-center">{trailing}</div>}
      </div>
    </Wrap>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, Common & TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { label, error, hint, className, ...rest },
  ref,
) {
  const id = useId();
  return (
    <Wrap id={id} label={label} error={error} hint={hint}>
      <textarea
        id={id}
        ref={ref}
        rows={4}
        aria-invalid={!!error}
        aria-describedby={describe(id, error, hint)}
        className={clsx(control, "py-3", error && "border-danger-fg", className)}
        {...rest}
      />
    </Wrap>
  );
});

export const Select = forwardRef<HTMLSelectElement, Common & SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { label, error, hint, className, children, ...rest },
  ref,
) {
  const id = useId();
  return (
    <Wrap id={id} label={label} error={error} hint={hint}>
      <select
        id={id}
        ref={ref}
        aria-invalid={!!error}
        aria-describedby={describe(id, error, hint)}
        className={clsx(control, error && "border-danger-fg", className)}
        {...rest}
      >
        {children}
      </select>
    </Wrap>
  );
});
