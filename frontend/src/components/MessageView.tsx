"use client";

import { useState } from "react";
import { citationNumbers } from "@/lib/answer";
import type { Message } from "@/lib/types";
import { Answer } from "./Answer";
import { SourceList } from "./SourceList";

export function MessageView({ message, streaming = false }: { message: Message; streaming?: boolean }) {
  const [selected, setSelected] = useState<{ sourceIndex: number; citedText: string } | null>(null);
  const [showSources, setShowSources] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl bg-teal-700 px-4 py-2.5 whitespace-pre-wrap text-white">
          {message.content}
        </p>
      </div>
    );
  }

  const segments = message.segments ?? [{ text: message.content, citations: [] }];
  const sources = message.sources ?? [];
  const numbers = citationNumbers(segments);
  const open = showSources || selected !== null;

  return (
    <div className="card p-4">
      {segments.every((s) => !s.text) && streaming ? (
        <p className="muted animate-pulse">Reading your documents...</p>
      ) : (
        <Answer
          segments={segments}
          onCite={(sourceIndex, citedText) => {
            setSelected({ sourceIndex, citedText });
            setShowSources(true);
          }}
        />
      )}
      {sources.length > 0 && (
        <div className="mt-3 border-t border-stone-100 pt-3 dark:border-stone-800">
          <button
            type="button"
            className="text-sm font-medium text-teal-700 hover:underline dark:text-teal-400"
            aria-expanded={open}
            onClick={() => {
              setShowSources(!open);
              setSelected(null);
            }}
          >
            {open ? "Hide sources" : `Sources (${numbers.size} cited, ${sources.length} searched)`}
          </button>
          {open && (
            <div className="mt-3">
              <SourceList sources={sources} numbers={numbers} selected={selected} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
