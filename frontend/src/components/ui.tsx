"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
    >
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span role="status" className="muted inline-flex items-center gap-2 text-sm">
      <span className="size-4 animate-spin rounded-full border-2 border-stone-300 border-t-teal-700" />
      {label}
    </span>
  );
}

// Destructive actions ask "Are you sure?" first. Escape or Cancel closes the dialog.
export function ConfirmButton({
  label,
  title,
  message,
  confirmLabel,
  pending,
  onConfirm,
  className = "btn-secondary",
}: {
  label: ReactNode;
  title: string;
  message: ReactNode;
  confirmLabel: string;
  pending: boolean;
  onConfirm: () => void;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    cancel.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && !pending && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, pending]);

  return (
    <>
      <button type="button" className={className} disabled={pending} onClick={() => setOpen(true)}>
        {label}
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/50 p-4">
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            className="card w-full max-w-md p-6 shadow-xl"
          >
            <h2 id="confirm-title" className="text-lg font-semibold">
              {title}
            </h2>
            <div className="muted mt-2 text-sm">{message}</div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                ref={cancel}
                type="button"
                className="btn-secondary"
                disabled={pending}
                onClick={() => setOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger"
                disabled={pending}
                onClick={() => {
                  onConfirm();
                  setOpen(false);
                }}
              >
                {pending ? "Deleting..." : confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
