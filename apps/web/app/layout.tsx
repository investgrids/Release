import type { Metadata } from "next";
import "./globals.css";

import { SiteHeader } from "@/components/SiteHeader";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "IG - Market Intelligence",
  description: "Event → Impact → Companies → Story"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100">
        <SiteHeader />
        <div className="mx-auto grid max-w-[1600px] gap-6 px-6 py-6 xl:grid-cols-[240px_1fr_260px]">
          <Sidebar />
          {children}
        </div>
      </body>
    </html>
  );
}
