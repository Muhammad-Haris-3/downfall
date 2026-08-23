"use client";

import { usePathname } from "next/navigation";
import { Background, Footer, Header } from "./Chrome";

/**
 * Wraps every page in the header, the drifting ground and the footer.
 *
 * A client component only because the header needs the current path to mark the
 * active tab and the toggle needs localStorage. The pages themselves stay server
 * components, so the data files are read at build time and never shipped.
 */
export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname() ?? "/";
  return (
    <div style={{ position: "relative", minHeight: "100vh", overflowX: "hidden", isolation: "isolate" }}>
      <Background />
      <Header path={path.endsWith("/") ? path : path + "/"} />
      <main style={{ animation: "fade .45s ease both" }}>{children}</main>
      <Footer />
    </div>
  );
}
