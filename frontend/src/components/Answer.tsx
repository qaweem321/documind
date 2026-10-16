"use client";

import { citationNumbers } from "@/lib/answer";
import type { Segment } from "@/lib/types";

// An answer as text segments, each followed by numbered markers for the passages it cites.
export function Answer({
  segments,
  onCite,
}: {
  segments: Segment[];
  onCite: (sourceIndex: number, citedText: string) => void;
}) {
  const numbers = citationNumbers(segments);
  return (
    <div className="leading-relaxed whitespace-pre-wrap">
      {segments.map((segment, i) => (
        <span key={i}>
          {segment.text}
          {dedupe(segment.citations).map((citation) => (
            <button
              key={citation.sourceIndex}
              type="button"
              onClick={() => onCite(citation.sourceIndex, citation.citedText)}
              className="mx-0.5 inline-flex h-5 min-w-5 -translate-y-0.5 items-center justify-center rounded bg-teal-100 px-1 align-baseline text-xs font-semibold text-teal-800 hover:bg-teal-200 dark:bg-teal-900 dark:text-teal-100"
              aria-label={`Source ${numbers.get(citation.sourceIndex)}`}
              title={citation.citedText}
            >
              {numbers.get(citation.sourceIndex)}
            </button>
          ))}
        </span>
      ))}
    </div>
  );
}

function dedupe<T extends { sourceIndex: number }>(citations: T[]): T[] {
  return [...new Map(citations.map((c) => [c.sourceIndex, c])).values()];
}
