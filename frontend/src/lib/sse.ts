import { ApiError, errorMessage } from "./api";
import type { Source } from "./types";

export type AnswerEvent =
  | { event: "sources"; data: Source[] }
  | { event: "text"; data: { block: number; text: string } }
  | { event: "citation"; data: { block: number; sourceIndex: number; citedText: string } }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { messageId: string } };

// Splits a server-sent event stream into events. Events can arrive split across network chunks,
// so text is buffered until a blank line ends each one.
export async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<AnswerEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    // stream: true keeps a multi-byte character split across chunks intact.
    buffer += decoder.decode(value, { stream: !done });
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const raw = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const fields = Object.fromEntries(
        raw.split("\n").map((line) => {
          const colon = line.indexOf(": ");
          return [line.slice(0, colon), line.slice(colon + 2)];
        }),
      );
      if (fields.event && fields.data !== undefined) {
        yield { event: fields.event, data: JSON.parse(fields.data) } as AnswerEvent;
      }
    }
    if (done) return;
  }
}

export async function* ask(
  conversationId: string,
  content: string,
  signal?: AbortSignal,
): AsyncGenerator<AnswerEvent> {
  const response = await fetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ content }),
    signal,
  });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, errorMessage(data, response.status));
  }
  yield* readEvents(response.body);
}
