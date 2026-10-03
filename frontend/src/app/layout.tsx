import type { Metadata } from "next";
import { Outfit, Geist_Mono } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://pitchprep-1.onrender.com"),
  title: { default: "PitchPrep | Walk into every pitch prepared", template: "%s | PitchPrep" },
  description: "Research a company, check the sources, and prepare a more relevant first email with PitchPrep.",
  openGraph: {
    type: "website",
    siteName: "PitchPrep",
    title: "PitchPrep | Walk into every pitch prepared",
    description: "Research a company, check the sources, and prepare a more relevant first email with PitchPrep.",
    images: [{ url: "/Thumbnail.png", width: 1672, height: 941, alt: "PitchPrep prospect brief research assistant" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "PitchPrep | Walk into every pitch prepared",
    description: "Research a company, check the sources, and prepare a more relevant first email with PitchPrep.",
    images: ["/Thumbnail.png"],
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${outfit.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full"><a className="skip-link" href="#main">Skip to content</a>{children}</body>
    </html>
  );
}
