import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Server Search | Cross-Server Search Platform",
  description:
    "Search across logs, containers, apps, programs, documents, and more across all your servers.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-transparent text-white antialiased min-h-screen">
        {children}
      </body>
    </html>
  );
}
