let backendUrl = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
if (backendUrl && !backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
  backendUrl = `https://${backendUrl}`;
}

const nextConfig = {
  reactStrictMode: false,
  async rewrites() {
    return [
      {
        source: '/docs',
        destination: `${backendUrl}/docs`,
      },
      {
        source: '/redoc',
        destination: `${backendUrl}/redoc`,
      },
      {
        source: '/openapi.json',
        destination: `${backendUrl}/openapi.json`,
      },
      {
        source: '/api/backend/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
