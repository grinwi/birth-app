/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true
  },
  async rewrites() {
    return [
      { source: '/api-py/health', destination: '/api/health' },
      { source: '/api-py/people', destination: '/api/people' },
      { source: '/api-py/people-plain', destination: '/api/people_plain' },
      { source: '/api-py/people/:index', destination: '/api/people_index?index=:index' },
      { source: '/api-py/json', destination: '/api/json' },
      { source: '/api-py/auth/login', destination: '/api/auth/login' },
      { source: '/api-py/auth/invite', destination: '/api/auth/invite' },
      { source: '/api-py/auth/register', destination: '/api/auth/register' },
      { source: '/api-py/sync', destination: '/api/sync' }
    ];
  }
};

export default nextConfig;
