import type { AppConfig } from "./types";

// The app's settings, fetched while the page is rendered on the server, so the first HTML
// already has the demo notice. Fetched in the browser it appeared seconds later on slow phones
// and pushed the page down. Returns null if the backend is unreachable: the browser then
// fetches the settings itself.
export async function loadConfig(): Promise<AppConfig | null> {
  try {
    const response = await fetch(`${process.env.BACKEND_URL}/api/config`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2000),
    });
    return response.ok ? ((await response.json()) as AppConfig) : null;
  } catch {
    return null;
  }
}
