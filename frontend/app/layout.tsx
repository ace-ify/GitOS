import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GitOS | Graph-Powered Defense & Intelligence Layer for GitHub",
  description: "Protecting maintainers from AI slop, mapping multi-hop blast radius, and equipping contributors with pre-flight impact intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0a0d14] text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
