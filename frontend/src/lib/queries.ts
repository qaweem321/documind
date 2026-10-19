import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { AppConfig, Conversation, Doc } from "./types";

export const CONFIG_KEY = ["config"];

// Usually already filled in by the server render (see Providers).
export const useConfig = () =>
  useQuery({ queryKey: CONFIG_KEY, queryFn: () => api<AppConfig>("/config"), staleTime: Infinity });

export const useConversations = () =>
  useQuery({ queryKey: ["conversations"], queryFn: () => api<Conversation[]>("/conversations") });

// Polls every 2 seconds while any document is still being processed.
export const useDocuments = () =>
  useQuery({
    queryKey: ["documents"],
    queryFn: () => api<Doc[]>("/documents"),
    refetchInterval: (query) => (query.state.data?.some((d) => d.status === "processing") ? 2000 : false),
  });
