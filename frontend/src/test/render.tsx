import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { vi } from "vitest";

export function renderWithQuery(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

export const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

type Handler = (init: RequestInit) => Response | Promise<Response>;

// Answers fetch calls from a route table keyed "METHOD /api/path".
export function mockFetch(routes: Record<string, unknown | Handler>) {
  const calls: { key: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const key = `${init.method ?? "GET"} ${url.split("?")[0]}`;
      calls.push({ key, init });
      if (!(key in routes))
        return new Response(JSON.stringify({ detail: `No mock for ${key}` }), { status: 500 });
      const route = routes[key];
      if (typeof route === "function") return (route as Handler)(init);
      return new Response(JSON.stringify(route), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}
