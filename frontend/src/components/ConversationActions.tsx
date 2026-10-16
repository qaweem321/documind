"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Conversation } from "@/lib/types";
import { ConfirmButton } from "./ui";

export function DeleteConversation({ conversation }: { conversation: Conversation }) {
  const client = useQueryClient();
  const router = useRouter();
  const remove = useMutation({
    mutationFn: () => api(`/conversations/${conversation.id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["conversations"] });
      router.replace("/");
    },
  });
  return (
    <ConfirmButton
      label="Delete chat"
      title="Delete this chat?"
      message={`Are you sure? “${conversation.title}” and all its messages will be deleted. Your documents stay in the library.`}
      confirmLabel="Delete chat"
      pending={remove.isPending}
      onConfirm={() => remove.mutate()}
    />
  );
}
