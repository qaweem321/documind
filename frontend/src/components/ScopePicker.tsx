"use client";

import { useState } from "react";
import { useDocuments } from "@/lib/queries";

// Which documents a chat searches: all of them (null) or a chosen few.
export function ScopePicker({
  value,
  onChange,
  disabled,
}: {
  value: string[] | null;
  onChange: (ids: string[] | null) => void;
  disabled?: boolean;
}) {
  const documents = useDocuments();
  const [open, setOpen] = useState(false);
  const ready = documents.data?.filter((d) => d.status === "ready") ?? [];
  const label =
    value === null
      ? "All documents"
      : value.length === 1
        ? (ready.find((d) => d.id === value[0])?.title ?? "1 document")
        : `${value.length} documents`;

  const toggle = (id: string) => {
    const current = value ?? ready.map((d) => d.id);
    const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
    onChange(next.length === 0 || next.length === ready.length ? null : next);
  };

  return (
    <div className="relative">
      <button
        type="button"
        className="btn-secondary max-w-64"
        disabled={disabled || ready.length === 0}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span className="muted">Searching:</span> <span className="truncate">{label}</span>
      </button>
      {open && (
        <div className="card absolute right-0 z-20 mt-1 max-h-80 w-72 overflow-y-auto p-2 shadow-lg">
          <button
            type="button"
            className="w-full rounded px-2 py-1.5 text-left text-sm hover:bg-stone-100 dark:hover:bg-stone-800"
            onClick={() => onChange(null)}
          >
            {value === null ? "✓ " : ""}All documents
          </button>
          {ready.map((d) => (
            <label
              key={d.id}
              className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-stone-100 dark:hover:bg-stone-800"
            >
              <input
                type="checkbox"
                className="accent-teal-700"
                checked={value === null || value.includes(d.id)}
                onChange={() => toggle(d.id)}
              />
              <span className="truncate">{d.title}</span>
            </label>
          ))}
          <button type="button" className="btn-secondary mt-2 w-full" onClick={() => setOpen(false)}>
            Done
          </button>
        </div>
      )}
    </div>
  );
}
