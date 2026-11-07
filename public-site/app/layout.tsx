import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Revenant — The Complete Native Map Atlas",
  description: "Explore every Revenant level at its original resolution. Pan, zoom, and download lossless maps captured from the original game.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
