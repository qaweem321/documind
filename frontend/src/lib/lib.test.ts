import { describe, expect, it } from "vitest";
import { sse, streamOf } from "@/test/render";
import { AnswerDraft, citationNumbers } from "./answer";
import { errorMessage } from "./api";
import { formatBytes, formatDate, plural } from "./format";
import { readEvents } from "./sse";

async function collect(stream: ReadableStream<Uint8Array>) {
  const events = [];
  for await (const event of readEvents(stream)) events.push(event);
  return events;
}

describe("readEvents", () => {
  it("parses events split across network chunks", async () => {
    const raw = sse("text", { block: 0, text: "Hello" }) + sse("done", { messageId: "m1" });
    const events = await collect(streamOf(raw.slice(0, 13), raw.slice(13, 40), raw.slice(40)));
    expect(events).toEqual([
      { event: "text", data: { block: 0, text: "Hello" } },
      { event: "done", data: { messageId: "m1" } },
    ]);
  });

  it("keeps multi-byte characters split between chunks", async () => {
    const bytes = new TextEncoder().encode(sse("text", { block: 0, text: "café “quoted”" }));
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, 40));
        controller.enqueue(bytes.slice(40));
        controller.close();
      },
    });
    const [event] = await collect(stream);
    expect(event?.data).toEqual({ block: 0, text: "café “quoted”" });
  });
});

describe("AnswerDraft", () => {
  it("groups text and citations by block and numbers sources by first citation", () => {
    const draft = new AnswerDraft();
    draft.addText(0, "Yes. ");
    draft.addText(1, "Within 10 days");
    draft.addCitation(1, { sourceIndex: 4, citedText: "10 business days" });
    draft.addText(2, " and a box");
    draft.addCitation(2, { sourceIndex: 1, citedText: "prepaid box" });
    draft.addCitation(2, { sourceIndex: 4, citedText: "again" });
    const message = draft.toMessage("m1");
    expect(message.content).toBe("Yes. Within 10 days and a box");
    expect([...citationNumbers(message.segments!)]).toEqual([
      [4, 1],
      [1, 2],
    ]);
  });

  it("shows the error as the content when nothing was written", () => {
    const draft = new AnswerDraft();
    draft.error = "Claude declined to answer this question.";
    expect(draft.toMessage("m").content).toBe("(Claude declined to answer this question.)");
  });
});

describe("format", () => {
  it("uses unambiguous UTC dates", () => {
    expect(formatDate("2026-10-11T23:30:00-05:00")).toBe("Oct 12, 2026");
  });
  it("formats sizes and plurals", () => {
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(3 * 1024 * 1024)).toBe("3.0 MB");
    expect(plural(1, "page")).toBe("1 page");
    expect(plural(3, "page")).toBe("3 pages");
  });
});

describe("errorMessage", () => {
  it("reads FastAPI error bodies", () => {
    expect(errorMessage({ detail: "Conversation not found" }, 404)).toBe("Conversation not found");
    expect(errorMessage({ detail: [{ msg: "String should have at least 1 character" }] }, 422)).toBe(
      "String should have at least 1 character",
    );
    expect(errorMessage(null, 502)).toMatch(/server/);
  });
});
