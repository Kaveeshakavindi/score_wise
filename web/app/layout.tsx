import type { Metadata } from "next";
import { Outfit, Reenie_Beanie } from "next/font/google";
import "./globals.css";

// design.md §1 — Outfit is the primary body/UI font; Reenie Beanie is the
// sparing cursive accent (single words/short phrases only, never body text).
const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  weight: ["300", "400", "500", "600"],
});
const reenieBeanie = Reenie_Beanie({
  subsets: ["latin"],
  variable: "--font-reenie-beanie",
  weight: "400",
});

export const metadata: Metadata = {
  title: "ScoreWise",
  description: "A short, timed GCE A/L practice test with an AI tutor for every question you miss.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} ${reenieBeanie.variable} font-sans antialiased`}>
        {children}

        {/* design.md §4 — global grain overlay: fixed, full-viewport SVG
            noise film sitting over every screen equally, applied once here
            (not per-screen) so it's consistent across the whole app. */}
        <svg
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 z-50 h-full w-full"
          style={{ mixBlendMode: "overlay", opacity: 0.35 }}
        >
          <filter id="grain">
            <feTurbulence type="fractalNoise" baseFrequency="0.65" numOctaves={3} stitchTiles="stitch" />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
      </body>
    </html>
  );
}
