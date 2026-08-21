import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Fully static. There is no API and no database because neither would do
  // anything a build step cannot: the trip archive changes once a month and the
  // outage record is committed to the repository anyway. See SRS 8.1.
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
