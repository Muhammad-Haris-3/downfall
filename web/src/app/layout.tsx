import type { Metadata } from "next";
import "./globals.css";
import Shell from "@/components/Shell";

export const metadata: Metadata = {
  title: "Downfall — an empty dock records no demand",
  description:
    "A station with no bikes records no demand. Downfall measures when every " +
    "station in New York's bike share becomes unusable, and what that hides.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light">
      <head>
        {/* Applied before first paint, so a reader who chose dark never sees a
            white flash on the way to it. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('downfall-theme');" +
              "document.documentElement.setAttribute('data-theme',t==='dark'?'dark':'light')}catch(e){}",
          }}
        />
      </head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
