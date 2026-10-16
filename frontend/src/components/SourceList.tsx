"use client";

import type { Source } from "@/lib/types";

// Where the cited text appears in the passage. Line breaks and repeated spaces may differ
// between the two, so any run of whitespace matches any other.
export function findQuote(text: string, quote: string): [number, number] | null {
  const words = quote.replace(/…$/, "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return null;
  const pattern = new RegExp(words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+"));
  const match = pattern.exec(text);
  return match ? [match.index, match.index + match[0].length] : null;
}

// The passage text with the cited part highlighted.
export function Highlighted({ text, highlight }: { text: string; highlight: string | null }) {
  const range = highlight ? findQuote(text, highlight) : null;
  if (!range) return <>{text}</>;
  const [start, end] = range;
  return (
    <>
      {text.slice(0, start)}
      <mark className="rounded bg-amber-200 px-0.5 text-stone-900 dark:bg-amber-700 dark:text-white">
        {text.slice(start, end)}
      </mark>
      {text.slice(end)}
    </>
  );
}

export function sourceLabel(source: Source): string {
  return source.page ? `${source.documentTitle}, p. ${source.page}` : source.documentTitle;
}

export function SourceList({
  sources,
  numbers,
  selected,
}: {
  sources: Source[];
  numbers: Map<number, number>;
  selected: { sourceIndex: number; citedText: string } | null;
}) {
  // Cited passages first, in citation order, then the rest that were retrieved.
  const ordered = [...sources].sort((a, b) => (numbers.get(a.index) ?? 99) - (numbers.get(b.index) ?? 99));
  return (
    <ol className="space-y-2">
      {ordered.map((source) => {
        const number = numbers.get(source.index);
        const isSelected = selected?.sourceIndex === source.index;
        return (
          <li
            key={source.index}
            id={`source-${source.chunkId}`}
            className={`rounded-lg border p-3 text-sm ${
              isSelected
                ? "border-teal-500 bg-teal-50/60 dark:bg-teal-950/40"
                : "border-stone-200 dark:border-stone-800"
            }`}
          >
            <p className="mb-1 flex items-center gap-2 text-xs font-medium">
              {number ? (
                <span className="rounded bg-teal-100 px-1.5 text-teal-800 dark:bg-teal-900 dark:text-teal-100">
                  {number}
                </span>
              ) : (
                <span className="muted">Not cited</span>
              )}
              <a className="truncate hover:underline" href={`/api/documents/${source.documentId}/file`}>
                {sourceLabel(source)}
              </a>
            </p>
            <p className="muted whitespace-pre-wrap">
              <Highlighted text={source.content} highlight={isSelected ? selected.citedText : null} />
            </p>
          </li>
        );
      })}
    </ol>
  );
}
