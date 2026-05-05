import type { Metadata } from "next";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { NavHeader, NavFooter } from "@/components/NavHeader";

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
    <html lang="en" suppressHydrationWarning>
      {/* suppressHydrationWarning prevents false positives caused by browser
          extensions (e.g. Honey, LastPass) that inject DOM nodes between the
          server render and client hydration. React 19 / Next.js 15 best practice. */}
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased" suppressHydrationWarning>
        <I18nProvider>
          <NavHeader />
          <main className="mx-auto max-w-4xl px-4 py-10">{children}</main>
          <NavFooter />
        </I18nProvider>
      </body>
    </html>
  );
}
