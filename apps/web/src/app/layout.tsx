import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});
const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});
export const metadata: Metadata = {
  title: {
    default: "FactoryMind AI",
    template: "%s | FactoryMind AI",
  },
  description:
    "FactoryMind AI - evidence-driven industrial intelligence platform for predictive maintenance and machine monitoring.",
};
export default function RootLayout({ children }: Readonly<LayoutProps<"/">>) {
  return (
    <html
      lang="en"
      // Browser extensions can add webcrx attributes before React hydrates.
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      {/* Grammarly injects attributes here before hydration; the escape hatch is local to this element. */}
      <body className="min-h-full" suppressHydrationWarning>{children}</body>
    </html>
  );
}
