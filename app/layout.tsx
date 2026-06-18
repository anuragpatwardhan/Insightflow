import "./globals.css";
import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "InsightFlow — Decision intelligence for KPIs",
  description: "Explainable insights, trend narratives, and a chat agent for your operational data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
