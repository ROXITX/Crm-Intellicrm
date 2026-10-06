/** API requests are proxied to FastAPI so the browser stays same-origin (httpOnly refresh cookie, no CORS). */
const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";
export default {
  reactStrictMode: true,
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};
