import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Downfall — the demand that was never recorded",
  description:
    "A station with no bikes records no demand. Downfall measures when every " +
    "station in New York's bike share becomes unusable, and what that hides.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site">
          <div className="wrap">
            <span className="name">Downfall</span>
            <nav>
              <a href="/">Network</a>
              <a href="/conditions/">Conditions</a>
              <a href="/method/">Method</a>
              <a href="https://github.com/Muhammad-Haris-3/downfall">Source</a>
            </nav>
          </div>
        </header>
        {children}
        <footer className="site">
          <div className="wrap">
            Muhammad Haris Khokhar ·{" "}
            <a href="https://github.com/Muhammad-Haris-3/downfall">source and data</a>{" "}
            · Trip data: Citi Bike system data. Availability: GBFS.
          </div>
        </footer>
      </body>
    </html>
  );
}
