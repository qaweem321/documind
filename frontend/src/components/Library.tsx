"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type DragEvent } from "react";
import { api } from "@/lib/api";
import { formatBytes, formatDate, plural } from "@/lib/format";
import { useConfig, useDocuments } from "@/lib/queries";
import type { Doc, UploadResult } from "@/lib/types";
import { ConfirmButton, ErrorBox, Spinner } from "./ui";

const STATUS_STYLE: Record<Doc["status"], string> = {
  ready: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  processing: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};
const STATUS_LABEL: Record<Doc["status"], string> = {
  ready: "Ready",
  processing: "Processing...",
  failed: "Failed",
};

function DeleteDocument({ document }: { document: Doc }) {
  const client = useQueryClient();
  const remove = useMutation({
    mutationFn: () => api(`/documents/${document.id}`, { method: "DELETE" }),
    onSettled: () => client.invalidateQueries({ queryKey: ["documents"] }),
  });
  return (
    <ConfirmButton
      label="Delete"
      title={`Delete “${document.title}”?`}
      message="Are you sure? It is removed from the library and from future searches. Past answers keep their quotes."
      confirmLabel="Delete document"
      pending={remove.isPending}
      onConfirm={() => remove.mutate()}
    />
  );
}

export function Library() {
  const client = useQueryClient();
  const config = useConfig();
  const documents = useDocuments();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const upload = useMutation({
    mutationFn: (files: File[]) => {
      const form = new FormData();
      for (const file of files) form.append("files", file);
      return api<UploadResult[]>("/documents", { form });
    },
    onSettled: () => client.invalidateQueries({ queryKey: ["documents"] }),
  });
  const accept = config.data?.acceptedExtensions.join(",") ?? ".pdf,.md,.markdown,.txt";

  const send = (files: FileList | null) => {
    if (files && files.length > 0 && !upload.isPending) upload.mutate([...files]);
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    send(event.dataTransfer.files);
  };
  const problems = upload.data?.filter((r) => r.error || r.duplicate) ?? [];

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Library</h1>
      <p className="muted mt-1 text-sm">Documents DocuMind searches when you ask a question.</p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`mt-6 rounded-xl border-2 border-dashed p-8 text-center transition ${
          dragging
            ? "border-teal-600 bg-teal-50 dark:bg-teal-950/40"
            : "border-stone-300 dark:border-stone-700"
        }`}
      >
        <p className="font-medium">Drop files here</p>
        <p className="muted mt-1 text-sm">
          PDF, Markdown or text, up to {config.data?.maxUploadMb ?? 20} MB each. Scanned PDFs need OCR first.
        </p>
        <input
          ref={input}
          type="file"
          multiple
          accept={accept}
          className="hidden"
          aria-label="Choose files"
          onChange={(e) => send(e.target.files)}
        />
        <button
          type="button"
          className="btn-primary mt-4"
          disabled={upload.isPending}
          onClick={() => input.current?.click()}
        >
          {upload.isPending ? "Uploading..." : "Choose files"}
        </button>
      </div>

      <div className="mt-4 space-y-2">
        <ErrorBox error={upload.error} />
        {problems.map((r) => (
          <p
            key={r.filename}
            role="status"
            className={`text-sm ${r.error ? "text-red-700 dark:text-red-400" : "muted"}`}
          >
            {r.filename}: {r.error ?? "already in the library."}
          </p>
        ))}
      </div>

      <section className="mt-8">
        {documents.isPending && <Spinner label="Loading documents..." />}
        <ErrorBox error={documents.error} />
        {documents.data?.length === 0 && (
          <p className="muted py-8 text-center">No documents yet. Upload a few to start asking questions.</p>
        )}
        {documents.data && documents.data.length > 0 && (
          <ul className="card divide-y divide-stone-100 dark:divide-stone-800">
            {documents.data.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <a
                    href={`/api/documents/${d.id}/file`}
                    className="block truncate font-medium hover:underline"
                    title={d.filename}
                  >
                    {d.title}
                  </a>
                  <p className="muted text-xs">
                    {d.filename} · {formatBytes(d.sizeBytes)}
                    {d.pageCount ? ` · ${plural(d.pageCount, "page")}` : ""}
                    {d.status === "ready" ? ` · ${plural(d.chunkCount, "passage")}` : ""} · added{" "}
                    {formatDate(d.createdAt)}
                  </p>
                  {d.error && <p className="mt-1 text-xs text-red-700 dark:text-red-400">{d.error}</p>}
                </div>
                <div className="flex items-center gap-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[d.status]}`}>
                    {STATUS_LABEL[d.status]}
                  </span>
                  <DeleteDocument document={d} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
