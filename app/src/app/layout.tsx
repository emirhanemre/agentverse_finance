import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { ProvenanceProvider } from "../components/Provenance";

// Wix Madefor Display and Text, SIL Open Font License 1.1 (src/fonts/OFL-wix-madefor.txt).
// IBM Plex Mono stays for code only (OFL, src/fonts/OFL.txt). Local so builds never hit the network.
const display = localFont({
  src: [{ path: "../fonts/wix-madefor-display-latin-500-normal.woff2", weight: "500" }],
  variable: "--font-wix-display",
  display: "swap",
});

const text = localFont({
  src: [{ path: "../fonts/wix-madefor-text-latin-variable.woff2", weight: "400 600" }],
  variable: "--font-wix-text",
  display: "swap",
});

const mono = localFont({
  src: [
    { path: "../fonts/ibm-plex-mono-latin-400-normal.woff2", weight: "400" },
    { path: "../fonts/ibm-plex-mono-latin-500-normal.woff2", weight: "500" },
  ],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Pub Hedge",
  description: "Protects independent pubs against weather, sport and duty shocks.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB" className={`${display.variable} ${text.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem("pubhedge.theme.dusk")==="light")document.documentElement.dataset.theme="light"}catch(e){}`,
          }}
        />
      </head>
      <body className="font-sans">
        <ProvenanceProvider>{children}</ProvenanceProvider>
      </body>
    </html>
  );
}
