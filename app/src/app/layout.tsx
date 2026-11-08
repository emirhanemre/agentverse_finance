import type { Metadata } from "next";
import "./globals.css";
import "./fonts.css";

export const metadata: Metadata = {
  title: "Pub Hedge",
  description:
    "Local weather exposure analysis and human-approved paper trading.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en-GB"
      className={"plex-sans-variable plex-mono-variable"}
      suppressHydrationWarning
    >
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{if(localStorage.getItem("pubhedge.theme")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}`,
          }}
        />
      </head>
      <body className="font-sans">{children}</body>
    </html>
  );
}
