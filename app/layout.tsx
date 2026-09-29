import type { Metadata } from "next";
import "./globals.css";
import LayoutShell from "@/components/LayoutShell";

export const metadata: Metadata = {
  title: "Lead-AI — Enterprise Sales Dashboard",
  description: "AI-powered B2B sales intelligence platform. Discover companies, manage clients, and close deals faster.",
  keywords: ["CRM", "sales", "AI", "B2B", "leads", "outreach", "Lead-AI"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <meta name="google-site-verification" content="jtIJi8jc4K9UhS-lTwQx04gXrtCb8G6x7zpEh4gMZFE" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
        />
      </head>
      <body className="font-sans text-on-surface antialiased bg-background">
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  );
}
