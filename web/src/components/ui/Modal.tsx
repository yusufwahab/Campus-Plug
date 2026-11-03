"use client";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Button } from "./Button";

type Props = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  /** When true, closing asks for confirmation so unsaved form data is not lost by accident. */
  dirty?: boolean;
};

/**
 * Native <dialog> opened with showModal(): the browser traps focus, closes on Esc and
 * restores focus to the opener. Bottom sheet below 768px, centred card above.
 */
export function Modal({ open, title, onClose, children, dirty = false }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  function requestClose() {
    if (dirty && !confirmDiscard) {
      setConfirmDiscard(true);
      return;
    }
    setConfirmDiscard(false);
    onClose();
  }

  return (
    <dialog
      ref={ref}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        requestClose();
      }}
      onClick={(e) => e.target === ref.current && requestClose()}
      className="m-0 mt-auto w-full max-w-none rounded-t-[28px] bg-white p-0 text-ink backdrop:bg-ink/50 md:m-auto md:max-w-lg md:rounded-card"
    >
      {open && (
        <div className="max-h-[85dvh] overflow-y-auto p-5 pb-safe md:p-6">
          <div className="mb-4 flex items-start justify-between gap-4">
            <h2 className="text-xl font-bold">{title}</h2>
            <button
              type="button"
              onClick={requestClose}
              aria-label="Close"
              className="grid size-11 shrink-0 place-items-center rounded-full hover:bg-ground"
            >
              <X className="size-5" aria-hidden="true" />
            </button>
          </div>
          {confirmDiscard && (
            <div role="alert" className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-input bg-pending-bg p-3 text-sm text-pending-fg">
              <span>Discard your changes?</span>
              <span className="flex gap-2">
                <Button variant="tertiary" onClick={() => setConfirmDiscard(false)}>
                  Keep editing
                </Button>
                <Button
                  variant="danger"
                  onClick={() => {
                    setConfirmDiscard(false);
                    onClose();
                  }}
                >
                  Discard
                </Button>
              </span>
            </div>
          )}
          {children}
        </div>
      )}
    </dialog>
  );
}

type ConfirmProps = {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
};

export function ConfirmModal({ open, title, body, confirmLabel, destructive, loading, onConfirm, onClose }: ConfirmProps) {
  return (
    <Modal open={open} title={title} onClose={onClose}>
      <p className="text-sm text-muted">{body}</p>
      <div className="mt-6 flex flex-col-reverse gap-2 md:flex-row md:justify-end">
        <Button variant="tertiary" onClick={onClose}>
          Cancel
        </Button>
        <Button variant={destructive ? "danger" : "secondary"} loading={loading} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
