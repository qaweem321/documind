"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { use } from "react";
import { ChatView } from "@/components/ChatView";
import { DeleteConversation } from "@/components/ConversationActions";
import { ErrorBox, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { ConversationDetail } from "@/lib/types";

export default function ChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const conversation = useQuery({
    queryKey: ["conversation", id],
    queryFn: () => api<ConversationDetail>(`/conversations/${id}`),
    staleTime: Infinity,
    gcTime: 0,
  });

  if (conversation.isPending) {
    return (
      <div className="p-8">
        <Spinner label="Loading chat..." />
      </div>
    );
  }
  if (conversation.error) {
    const missing =
      conversation.error instanceof ApiError &&
      (conversation.error.status === 404 || conversation.error.status === 422);
    return (
      <div className="mx-auto max-w-xl space-y-4 p-8">
        {missing ? (
          <h1 className="text-xl font-semibold">This chat doesn&apos;t exist (any more).</h1>
        ) : (
          <ErrorBox error={conversation.error} />
        )}
        <Link href="/" className="btn-primary">
          Start a new chat
        </Link>
      </div>
    );
  }
  return (
    <ChatView
      key={id}
      initial={conversation.data}
      actions={<DeleteConversation conversation={conversation.data} />}
    />
  );
}
