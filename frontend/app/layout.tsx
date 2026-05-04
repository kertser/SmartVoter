import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartVoter — Evidence-Based Political Match",
  description:
    "Compare your policy preferences with Israeli political parties based on evidence, not slogans.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto max-w-4xl px-4 py-4 flex items-center justify-between">
            <a href="/" className="font-semibold text-slate-800 text-lg tracking-tight">
              SmartVoter
            </a>
            <nav className="flex gap-6 text-sm text-slate-500">
              <a href="/methodology" className="hover:text-slate-800 transition-colors">
                Methodology
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-10">{children}</main>
        <footer className="border-t border-slate-200 mt-20 py-8 text-center text-xs text-slate-400">
          <p>
            SmartVoter does not tell you whom to vote for. It shows similarity, disagreement,
            evidence, and uncertainty.
          </p>
        </footer>
      </body>
    </html>
  );
}

