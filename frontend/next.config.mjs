/** @type {import('next').NextConfig} */
const backendApiUrl = (
  process.env.BACKEND_API_URL
  || process.env.NEXT_PUBLIC_API_BASE_URL
  || "http://localhost:8000"
).replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendApiUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
