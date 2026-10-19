import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery, sse, streamOf } from "@/test/render";
import type { Source } from "@/lib/types";
import { ChatView } from "./ChatView";
import { Library } from "./Library";
import { Providers } from "./Providers";
import { Highlighted } from "./SourceList";
import { ConfirmButton } from "./ui";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn() }) }));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const source: Source = {
  index: 0,
  chunkId: 11,
  documentId: "d1",
  documentTitle: "Remote Work Policy",
  page: null,
  content: "Laptops are company property and must be returned within 10 business days after your last day.",
  score: 0.03,
};
const config = {
  demoMode: false,
  model: "claude-opus-5-5",
  maxUploadMb: 20,
  acceptedExtensions: [".md", ".pdf", ".txt"],
};
const readyDoc = {
  id: "d1",
  title: "Remote Work Policy",
  filename: "remote.md",
  contentType: "text/markdown",
  sizeBytes: 2048,
  pageCount: null,
  chunkCount: 4,
  status: "ready",
  error: null,
  createdAt: "2026-10-16T08:00:00Z",
};

describe("ChatView", () => {
  it("streams an answer with numbered citations that open the highlighted source", async () => {
    const calls = mockFetch({
      "GET /api/config": config,
      "GET /api/documents": [readyDoc],
      "POST /api/conversations": {
        id: "c1",
        title: "New chat",
        documentIds: null,
        createdAt: "",
        updatedAt: "",
      },
      "POST /api/conversations/c1/messages": () =>
        new Response(
          streamOf(
            sse("sources", [source]),
            sse("text", { block: 0, text: "You have " }),
            sse("citation", { block: 1, sourceIndex: 0, citedText: "returned within 10 business days" }),
            sse("text", { block: 1, text: "10 business days" }),
            sse("text", { block: 2, text: "." }),
            sse("done", { messageId: "m2" }),
          ),
          { headers: { "content-type": "text/event-stream" } },
        ),
    });
    renderWithQuery(<ChatView initial={null} />);

    const box = await screen.findByLabelText("Question");
    await waitFor(() => expect(box).toBeEnabled());
    await userEvent.type(box, "When do I return my laptop?{Enter}");

    expect(await screen.findByText("10 business days")).toBeInTheDocument();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/chat/c1"));
    expect(calls.filter((c) => c.key === "POST /api/conversations/c1/messages")).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Source 1" }));
    const mark = await screen.findByText("returned within 10 business days");
    expect(mark.tagName).toBe("MARK");
    expect(screen.getByText("Remote Work Policy")).toHaveAttribute("href", "/api/documents/d1/file");
  });

  it("points to the library when no document is ready, and shows the demo banner", async () => {
    mockFetch({ "GET /api/config": { ...config, demoMode: true }, "GET /api/documents": [] });
    renderWithQuery(<ChatView initial={null} />);
    expect(await screen.findByRole("link", { name: /Add PDFs, Markdown or text files/ })).toHaveAttribute(
      "href",
      "/documents",
    );
    expect(screen.getByText(/Demo mode/)).toBeInTheDocument();
    expect(screen.getByLabelText("Question")).toBeDisabled();
  });

  it("shows the demo notice at once when the server passed the settings in", () => {
    mockFetch({ "GET /api/documents": [readyDoc] });
    render(
      <Providers config={{ ...config, demoMode: true, model: null }}>
        <ChatView initial={null} />
      </Providers>,
    );
    expect(screen.getByText(/Demo mode/)).toBeInTheDocument();
  });

  it("shows server errors such as the rate limit", async () => {
    mockFetch({
      "GET /api/config": config,
      "GET /api/documents": [readyDoc],
      "POST /api/conversations/c1/messages": () =>
        new Response(JSON.stringify({ detail: "Too many questions. Wait a minute and try again." }), {
          status: 429,
        }),
    });
    renderWithQuery(
      <ChatView
        initial={{
          id: "c1",
          title: "Old chat",
          documentIds: null,
          createdAt: "",
          updatedAt: "",
          messages: [],
        }}
      />,
    );
    const box = await screen.findByLabelText("Question");
    await waitFor(() => expect(box).toBeEnabled());
    await userEvent.type(box, "Hi{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many questions");
  });

  it("says so when the answer stream breaks off before it's done", async () => {
    mockFetch({
      "GET /api/config": config,
      "GET /api/documents": [readyDoc],
      "POST /api/conversations/c1/messages": () =>
        new Response(streamOf(sse("sources", [source]), sse("text", { block: 0, text: "You have" })), {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        }),
    });
    renderWithQuery(
      <ChatView
        initial={{
          id: "c1",
          title: "Old chat",
          documentIds: null,
          createdAt: "",
          updatedAt: "",
          messages: [],
        }}
      />,
    );
    const box = await screen.findByLabelText("Question");
    await waitFor(() => expect(box).toBeEnabled());
    await userEvent.type(box, "Hi{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("The answer was cut off");
    expect(screen.getByText("You have")).toBeInTheDocument();
  });
});

describe("Library", () => {
  it("uploads files and reports per-file problems", async () => {
    const calls = mockFetch({
      "GET /api/config": config,
      "GET /api/documents": [readyDoc],
      "POST /api/documents": [
        {
          filename: "a.pdf",
          document: null,
          duplicate: false,
          error: "This file has a .pdf name but isn't a PDF.",
        },
        { filename: "remote.md", document: readyDoc, duplicate: true, error: null },
      ],
    });
    renderWithQuery(<Library />);
    expect(await screen.findByText("Remote Work Policy")).toBeInTheDocument();
    expect(screen.getByText(/4 passages · added Oct 16, 2026/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Choose files"), {
      target: { files: [new File(["x"], "a.pdf"), new File(["# R"], "remote.md")] },
    });
    expect(await screen.findByText(/a.pdf: This file has a .pdf name/)).toBeInTheDocument();
    expect(screen.getByText("remote.md: already in the library.")).toBeInTheDocument();
    const upload = calls.find((c) => c.key === "POST /api/documents");
    expect((upload?.init.body as FormData).getAll("files")).toHaveLength(2);
  });

  it("asks before deleting a document", async () => {
    const calls = mockFetch({
      "GET /api/config": config,
      "GET /api/documents": [readyDoc],
      "DELETE /api/documents/d1": () => new Response(null, { status: 204 }),
    });
    renderWithQuery(<Library />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent("Are you sure?");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete document" }));
    await waitFor(() => expect(calls.some((c) => c.key === "DELETE /api/documents/d1")).toBe(true));
  });
});

describe("small pieces", () => {
  it("highlights the cited text, and shows the passage as-is when it can't be found", () => {
    const { container, rerender } = render(
      <Highlighted text="One. Two three. Four." highlight="Two three." />,
    );
    expect(container.querySelector("mark")).toHaveTextContent("Two three.");
    rerender(
      <Highlighted text={"## Team events\n\nEach team (a+b)."} highlight="## Team events Each team (a+b)." />,
    );
    expect(container.querySelector("mark")).toHaveTextContent("Each team (a+b).");
    rerender(<Highlighted text="One. Two three. Four." highlight="missing" />);
    expect(container.querySelector("mark")).toBeNull();
  });

  it("cancels a confirmation without running the action", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmButton
        label="Delete"
        title="Sure?"
        message="Are you sure?"
        confirmLabel="Yes"
        pending={false}
        onConfirm={onConfirm}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
