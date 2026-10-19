"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { CONFIG_KEY } from "@/lib/queries";
import type { AppConfig } from "@/lib/types";

export function Providers({ children, config }: { children: ReactNode; config: AppConfig | null }) {
  const [client] = useState(() => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
        },
      },
    });
    if (config) queryClient.setQueryData(CONFIG_KEY, config);
    return queryClient;
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
