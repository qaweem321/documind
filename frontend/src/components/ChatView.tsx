"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { AnswerDraft } from "@/lib/answer";
import { api } from "@/lib/api";
import { useConfig, useDocuments } from "@/lib/queries";
import { ask } from "@/lib/sse";
import type { Conversation, ConversationDetail, Message } from "@/lib/types";
import { MessageView } from "./MessageView";
import { ScopePicker } from "./ScopePicker";
import { ErrorBox } from "./ui";

const EXAMPLES = [
  "What does the company pay for when working from home?",
  "How long do I have to submit an expense?",
  "What should I do if I lose my laptop?",
];

export function ChatView({ initial, actions }: { initial: ConversationDetail | null; actions?: ReactNode }) {
  const client = useQueryClient();
  const router = useRouter();
  const config = useConfig();
  const documents = useDocuments();
  const [conversation, setConversation] = useState<Conversation | null>(initial);
  const [messages, setMessages] = useState<Message[]>(initial?.messages ?? []);
  const [scope, setScope] = useState<string[] | null>(initial?.documentIds ?? null);
  const [draft, setDraft] = useState<Message | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<unknown>(null);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const pending = draft !== null;

  // Braces matter: newer browsers return a Promise from scrollIntoView, and an arrow function
  // without them would hand it to React as the effect's cleanup.
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [messages, draft]);
  useEffect(() => () => abort.current?.abort(), []);

  const readyCount = documents.data?.filter((d) => d.status === "ready").length ?? 0;

  async function changeScope(ids: string[] | null) {
    setScope(ids);
    if (conversation)
      await api(`/conversations/${conversation.id}`, { method: "PATCH", body: { documentIds: ids } }).catch(
        setError,
      );
  }

  async function send(question: string) {
    if (!question.trim() || pending) return;
    setError(null);
    setInput("");
    const answer = new AnswerDraft();
    let created: Conversation | null = null;
    setDraft(answer.toMessage("draft"));
    setMessages((m) => [
      ...m,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: question,
        segments: null,
        sources: null,
        createdAt: new Date().toISOString(),
      },
    ]);
    try {
      let current = conversation;
      if (!current) {
        current = await api<Conversation>("/conversations", { body: { documentIds: scope } });
        setConversation(current);
        created = current;
      }
      abort.current = new AbortController();
      for await (const event of ask(current.id, question, abort.current.signal)) {
        if (event.event === "sources") answer.sources = event.data;
        else if (event.event === "text") answer.addText(event.data.block, event.data.text);
        else if (event.event === "citation")
          answer.addCitation(event.data.block, {
            sourceIndex: event.data.sourceIndex,
            citedText: event.data.citedText,
          });
        else if (event.event === "error") answer.error = event.data.message;
        else if (event.event === "done") {
          setMessages((m) => [...m, answer.toMessage(event.data.messageId)]);
          setDraft(null);
          if (answer.error) setError(new Error(answer.error));
          break;
        }
        setDraft(answer.toMessage("draft"));
      }
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) setError(err);
      if (answer.segments.length > 0) setMessages((m) => [...m, answer.toMessage(`partial-${Date.now()}`)]);
    } finally {
      setDraft(null);
      abort.current = null;
      void client.invalidateQueries({ queryKey: ["conversations"] });
      // A new chat moves to its own URL once the answer is complete: changing the URL earlier
      // would remount the page and cut the stream off. The chat page then loads it from the server.
      if (created) router.replace(`/chat/${created.id}`);
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(input);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send(input);
    }
  };

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col md:h-screen">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-4 py-3 dark:border-stone-800">
        <h1 className="min-w-0 truncate font-semibold">{conversation?.title ?? "New chat"}</h1>
        <div className="flex flex-wrap gap-2">
          <ScopePicker value={scope} onChange={changeScope} disabled={pending} />
          {actions}
        </div>
      </header>
      {config.data?.demoMode && (
        <p className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          Demo mode: no Anthropic API key is set, so answers quote the best passages instead of being written
          by Claude.
        </p>
      )}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
          {messages.length === 0 && !pending && (
            <div className="py-10 text-center">
              <h2 className="text-2xl font-semibold tracking-tight">Ask your documents</h2>
              {documents.isSuccess && readyCount === 0 ? (
                <p className="muted mt-2">
                  Your library is empty.{" "}
                  <Link
                    href="/documents"
                    className="font-medium text-teal-700 hover:underline dark:text-teal-400"
                  >
                    Add PDFs, Markdown or text files
                  </Link>{" "}
                  to get started.
                </p>
              ) : (
                <>
                  <p className="muted mt-2">
                    Answers cite the passages they come from. Click a number to see the source.
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-2">
                    {EXAMPLES.map((example) => (
                      <button
                        key={example}
                        type="button"
                        className="btn-secondary"
                        onClick={() => void send(example)}
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
          {messages.map((message) => (
            <MessageView key={message.id} message={message} />
          ))}
          {draft && <MessageView message={draft} streaming />}
          <ErrorBox error={error} />
          <div ref={bottom} />
        </div>
      </div>
      <form
        onSubmit={onSubmit}
        className="border-t border-stone-200 bg-white p-3 dark:border-stone-800 dark:bg-stone-900"
      >
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <label htmlFor="question" className="sr-only">
            Question
          </label>
          <textarea
            id="question"
            rows={1}
            maxLength={4000}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={
              readyCount === 0 ? "Add documents to the library first" : "Ask a question about your documents"
            }
            disabled={readyCount === 0}
            className="max-h-40 min-h-11 flex-1 resize-y rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 disabled:opacity-60 dark:border-stone-700 dark:bg-stone-950"
          />
          {pending ? (
            <button type="button" className="btn-secondary" onClick={() => abort.current?.abort()}>
              Stop
            </button>
          ) : (
            <button type="submit" className="btn-primary" disabled={!input.trim() || readyCount === 0}>
              Ask
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
