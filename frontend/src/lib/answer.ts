import type { Citation, Message, Segment, Source } from "./types";

// Each source cited in an answer gets a number in order of first citation: [1], [2], ...
export function citationNumbers(segments: Segment[]): Map<number, number> {
  const numbers = new Map<number, number>();
  for (const segment of segments) {
    for (const citation of segment.citations) {
      if (!numbers.has(citation.sourceIndex)) numbers.set(citation.sourceIndex, numbers.size + 1);
    }
  }
  return numbers;
}

// Builds an answer from streamed events, the same way the server stores it.
export class AnswerDraft {
  private blocks = new Map<number, Segment>();
  sources: Source[] = [];
  error: string | null = null;

  addText(block: number, text: string) {
    this.segment(block).text += text;
  }

  addCitation(block: number, citation: Citation) {
    this.segment(block).citations.push(citation);
  }

  get segments(): Segment[] {
    return [...this.blocks.entries()]
      .sort(([a], [b]) => a - b)
      .map(([, s]) => ({ ...s, citations: [...s.citations] }));
  }

  toMessage(id: string): Message {
    const segments = this.segments;
    return {
      id,
      role: "assistant",
      content: segments.map((s) => s.text).join("") || (this.error ? `(${this.error})` : ""),
      segments,
      sources: this.sources,
      createdAt: new Date().toISOString(),
    };
  }

  private segment(block: number): Segment {
    let segment = this.blocks.get(block);
    if (!segment) {
      segment = { text: "", citations: [] };
      this.blocks.set(block, segment);
    }
    return segment;
  }
}
