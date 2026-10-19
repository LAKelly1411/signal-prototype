import type { Metadata } from "next";
import "@/styles/pa-brand.css";

export const metadata: Metadata = {
  title: "Sector Signal",
  description: "Sector signals, scored for newsworthiness.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
