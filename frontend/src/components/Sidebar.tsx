"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useConversations } from "@/lib/queries";
import { ThemeSelect } from "./ThemeSelect";

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-semibold tracking-tight">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/favicon.svg" alt="" className="size-7" />
      DocuMind
    </span>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const conversations = useConversations();
  const [open, setOpen] = useState(false);
  const linkClass = (active: boolean) =>
    `block truncate rounded-md px-2.5 py-1.5 text-sm ${
      active
        ? "bg-teal-50 font-medium text-teal-800 dark:bg-teal-950 dark:text-teal-200"
        : "hover:bg-stone-100 dark:hover:bg-stone-800"
    }`;

  return (
    <aside className="border-b border-stone-200 bg-white md:flex md:h-screen md:w-64 md:shrink-0 md:flex-col md:border-r md:border-b-0 dark:border-stone-800 dark:bg-stone-900">
      <div className="flex items-center justify-between px-4 py-3">
        <Link href="/" aria-label="DocuMind home">
          <Logo />
        </Link>
        <button
          type="button"
          className="btn-secondary md:hidden"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>
      <nav
        className={`${open ? "block" : "hidden"} min-h-0 flex-1 flex-col px-3 pb-3 md:flex`}
        onClick={() => setOpen(false)}
      >
        <Link href="/" className="btn-primary mb-2 w-full">
          New chat
        </Link>
        <Link href="/documents" className={linkClass(pathname === "/documents")}>
          Library
        </Link>
        <p className="muted mt-4 mb-1 px-2.5 text-xs font-semibold tracking-wide uppercase">Chats</p>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
          {conversations.data?.length === 0 && <p className="muted px-2.5 text-sm">No chats yet.</p>}
          {conversations.data?.map((c) => (
            <Link
              key={c.id}
              href={`/chat/${c.id}`}
              className={linkClass(pathname === `/chat/${c.id}`)}
              title={c.title}
            >
              {c.title}
            </Link>
          ))}
        </div>
        {/* Changing the theme must not close the mobile menu like a link click does. */}
        <div
          className="mt-3 border-t border-stone-200 pt-3 dark:border-stone-800"
          onClick={(e) => e.stopPropagation()}
        >
          <ThemeSelect />
        </div>
      </nav>
    </aside>
  );
}
