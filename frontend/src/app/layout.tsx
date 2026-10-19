import type { Metadata } from "next";
import { Providers } from "@/components/Providers";
import { Sidebar } from "@/components/Sidebar";
import { loadConfig } from "@/lib/server-config";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "DocuMind", template: "%s · DocuMind" },
  description: "Chat with your documents. Every answer cites the passages it comes from.",
  icons: { icon: "/favicon.svg" },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const config = await loadConfig();
  return (
    <html lang="en">
      <body>
        <Providers config={config}>
          <div className="md:flex">
            <Sidebar />
            <main className="min-w-0 flex-1">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
